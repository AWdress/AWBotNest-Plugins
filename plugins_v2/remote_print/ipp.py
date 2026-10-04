"""Small IPP/1.1 client; HTTP transport always uses the platform facade.

Only Get-Printer-Attributes and Print-Job are implemented. A Print-Job is never
retried: a lost, mismatched or substituted response is an uncertain submission.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import re
import secrets
import struct
import tempfile
from urllib.parse import urlsplit, urlunsplit
import warnings


MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024
MAX_IMAGE_PIXELS = 25_000_000
VERSION = (1, 1)
PRINT_JOB = 0x0002
GET_PRINTER_ATTRIBUTES = 0x000B
_NAME = re.compile(r"^[a-z][a-z0-9-]{0,127}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_GROUPS = {0x01, 0x02, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A}
_EXPECTED_TAGS = {
    "attributes-charset": {0x47}, "attributes-natural-language": {0x48},
    "printer-name": {0x42, 0x36}, "printer-uri-supported": {0x45},
    "document-format-supported": {0x49}, "printer-state": {0x23},
    "printer-is-accepting-jobs": {0x22}, "operations-supported": {0x23},
    "copies-supported": {0x33, 0x21}, "job-id": {0x21}, "copies": {0x21},
    "document-format": {0x49},
    "print-scaling-supported": {0x44}, "print-scaling-default": {0x44},
    "print-scaling": {0x44},
}


class IPPRejected(ValueError):
    """A complete, matching IPP error response explicitly rejected the operation."""


class IPPSubmissionUnknown(RuntimeError):
    """A Print-Job may have been accepted; callers must never automatically retry."""


def _validated_url(value, schemes, description):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError(f"请配置正确的{description}")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        hostname = parsed.hostname
    except ValueError:
        raise ValueError(f"{description}格式无效") from None
    if (parsed.scheme not in schemes or not hostname or not parsed.netloc
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or not parsed.path.startswith("/")
            or any(ord(char) <= 32 or ord(char) == 127 for char in value)
            or "\\" in value or "%" in parsed.netloc or ".." in parsed.path.split("/")
            or (port is not None and port < 1)):
        raise ValueError(f"{description}必须包含主机和路径，不能包含凭据、查询参数或片段")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _encoded_value(tag, value):
    if tag in (0x21, 0x23):
        if type(value) is not int or not -(2 ** 31) <= value < 2 ** 31:
            raise ValueError("IPP 整数无效")
        return struct.pack(">i", value)
    if tag == 0x22:
        if type(value) is not bool:
            raise ValueError("IPP 布尔值无效")
        return bytes([value])
    if not isinstance(value, str):
        raise ValueError("IPP 文本属性无效")
    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > 65535 or "\x00" in value:
        raise ValueError("IPP 文本属性超出限制")
    return encoded


def encode_request(operation, request_id, operation_attributes, job_attributes=()):
    """Encode typed attributes as (value-tag, name, value-or-list) tuples."""
    if type(request_id) is not int or not 1 <= request_id <= 0x7FFFFFFF:
        raise ValueError("IPP 请求 ID 无效")
    data = bytearray(struct.pack(">BBHI", *VERSION, operation, request_id))
    for group, attributes in ((0x01, operation_attributes), (0x02, job_attributes)):
        if not attributes:
            continue
        data.append(group)
        for tag, name, values in attributes:
            if not isinstance(name, str) or not _NAME.fullmatch(name):
                raise ValueError("IPP 属性名无效")
            values = values if isinstance(values, list) else [values]
            if not values:
                raise ValueError("IPP 属性缺少值")
            for index, value in enumerate(values):
                encoded_name = name.encode("ascii") if index == 0 else b""
                encoded = _encoded_value(tag, value)
                data.extend(bytes([tag]) + struct.pack(">H", len(encoded_name)) + encoded_name)
                data.extend(struct.pack(">H", len(encoded)) + encoded)
    data.append(0x03)
    return bytes(data)


class _Parser:
    def __init__(self, data):
        self.data = data
        self.offset = 8
        self.count = 0

    def field(self):
        if self.offset + 2 > len(self.data):
            raise ValueError("IPP 响应被截断")
        size = struct.unpack_from(">H", self.data, self.offset)[0]
        self.offset += 2
        if self.offset + size > len(self.data):
            raise ValueError("IPP 响应属性被截断")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def entry(self):
        if self.offset >= len(self.data):
            raise ValueError("IPP 响应被截断")
        self.count += 1
        if self.count > 2048:
            raise ValueError("IPP 响应属性过多")
        tag = self.data[self.offset]
        self.offset += 1
        return tag, self.field(), self.field()

    @staticmethod
    def name(value):
        try:
            name = value.decode("ascii")
        except UnicodeError:
            raise ValueError("IPP 响应属性名无效") from None
        if not _NAME.fullmatch(name):
            raise ValueError("IPP 响应属性名无效")
        return name

    def collection(self, depth):
        if depth > 16:
            raise ValueError("IPP 响应集合嵌套过深")
        result, current = {}, None
        while True:
            tag, name, raw = self.entry()
            if name:
                raise ValueError("IPP 集合中的属性名无效")
            if tag == 0x37:
                if raw:
                    raise ValueError("IPP 集合结束无效")
                return result
            if tag == 0x4A:
                current = self.name(raw)
                if current in result:
                    raise ValueError("IPP 集合成员重复")
                result[current] = []
            elif current is None:
                raise ValueError("IPP 集合缺少成员名")
            else:
                result[current].append(self.value(tag, raw, depth))

    def value(self, tag, raw, depth=0):
        if tag in (0x10, 0x12, 0x13, 0x15, 0x16, 0x17):
            if raw:
                raise ValueError("IPP 空属性无效")
            return None
        if tag in (0x21, 0x23):
            if len(raw) != 4:
                raise ValueError("IPP 整数长度无效")
            return struct.unpack(">i", raw)[0]
        if tag == 0x22:
            if raw not in (b"\x00", b"\x01"):
                raise ValueError("IPP 布尔值无效")
            return raw == b"\x01"
        if tag == 0x30:
            return raw
        if tag == 0x31:
            if len(raw) != 11:
                raise ValueError("IPP 日期长度无效")
            return raw
        if tag == 0x32:
            if len(raw) != 9:
                raise ValueError("IPP 分辨率长度无效")
            x, y, unit = struct.unpack(">iiB", raw)
            if min(x, y) <= 0 or unit not in (3, 4):
                raise ValueError("IPP 分辨率无效")
            return x, y, unit
        if tag == 0x33:
            if len(raw) != 8:
                raise ValueError("IPP 范围长度无效")
            lower, upper = struct.unpack(">ii", raw)
            if lower > upper:
                raise ValueError("IPP 范围无效")
            return lower, upper
        if tag == 0x34:
            if raw:
                raise ValueError("IPP 集合起始无效")
            return self.collection(depth + 1)
        if tag in (0x35, 0x36):
            if len(raw) < 4:
                raise ValueError("IPP 带语言文本无效")
            language_size = struct.unpack_from(">H", raw)[0]
            if 2 + language_size + 2 > len(raw):
                raise ValueError("IPP 带语言文本被截断")
            text_size = struct.unpack_from(">H", raw, 2 + language_size)[0]
            if 4 + language_size + text_size != len(raw):
                raise ValueError("IPP 带语言文本长度无效")
            raw = raw[4 + language_size:]
        elif tag not in (0x41, 0x42, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49):
            raise ValueError("IPP 响应包含未知值类型")
        try:
            value = raw.decode("utf-8")
        except UnicodeError:
            raise ValueError("IPP 响应文本编码无效") from None
        if "\x00" in value:
            raise ValueError("IPP 响应文本包含空字符")
        return value


def parse_response(data, request_id):
    """Strict bounded decoder; no trailing document bytes are accepted in replies."""
    if not isinstance(data, bytes) or not 9 <= len(data) <= MAX_RESPONSE_BYTES:
        raise ValueError("IPP 响应长度无效")
    major, minor, status, actual_id = struct.unpack_from(">BBHI", data)
    if (major, minor) != VERSION or actual_id != request_id:
        raise ValueError("IPP 响应版本或请求 ID 不匹配")
    parser = _Parser(data)
    groups, current, current_group, previous, previous_tag = [], None, None, None, None
    while parser.offset < len(data):
        tag = data[parser.offset]
        if tag == 0x03:
            parser.offset += 1
            if parser.offset != len(data) or not groups:
                raise ValueError("IPP 响应结束无效")
            return {"status": status, "groups": groups}
        if tag in _GROUPS:
            parser.offset += 1
            if not groups and tag != 0x01:
                raise ValueError("IPP 响应缺少操作属性组")
            if len(groups) >= 16:
                raise ValueError("IPP 响应属性组过多")
            current = {}
            current_group = tag
            groups.append((tag, current))
            previous, previous_tag = None, None
            continue
        if current is None or tag <= 0x0F:
            raise ValueError("IPP 响应属性组无效")
        tag, name, raw = parser.entry()
        if name:
            name = parser.name(name)
            if name in current:
                raise ValueError("IPP 响应属性重复")
            current[name] = []
            previous, previous_tag = name, tag
        else:
            if previous is None or previous_tag != tag:
                raise ValueError("IPP 响应的多值属性无效")
            name = previous
        if current_group != 0x05 and name in _EXPECTED_TAGS and tag not in _EXPECTED_TAGS[name]:
            raise ValueError("IPP 响应属性类型无效")
        current[name].append(parser.value(tag, raw))
    raise ValueError("IPP 响应缺少结束标记")


def _attributes(response, group):
    values = {}
    for tag, attributes in response["groups"]:
        if tag == group:
            for name, entries in attributes.items():
                if name in values:
                    raise ValueError("IPP 响应跨组属性重复")
                values[name] = entries
    return values


def _single(attributes, name, default=None):
    values = attributes.get(name, [])
    if len(values) > 1:
        raise ValueError("IPP 响应单值属性重复")
    return values[0] if values else default


def _mime(format):
    if format == "pdf":
        return "application/pdf"
    if format in ("jpg", "jpeg", "png", "webp", "bmp"):
        return "image/jpeg"
    raise ValueError("IPP 仅支持 PDF 和常见单张图片")


class IPPPrinter:
    def __init__(self, ctx, config_getter):
        self.ctx, self.config_getter = ctx, config_getter

    def _settings(self):
        config = self.config_getter()
        url = _validated_url(config.get("ipp_url"), {"http", "https"}, "IPP HTTP 地址")
        native = config.get("ipp_printer_uri", "")
        if native:
            uri = _validated_url(native, {"ipp", "ipps"}, "打印机原生 URI")
        else:
            parts = urlsplit(url)
            uri = urlunsplit(("ipps" if parts.scheme == "https" else "ipp", parts.netloc, parts.path, "", ""))
        try:
            timeout = int(config.get("ipp_timeout_seconds", 20))
        except (TypeError, ValueError, OverflowError):
            timeout = 20
        return url, uri, max(5, min(120, timeout)), bool(native)

    @staticmethod
    def _base_attributes(uri):
        return [(0x47, "attributes-charset", "utf-8"),
                (0x48, "attributes-natural-language", "en"),
                (0x45, "printer-uri", uri)]

    async def _request(self, url, data, request_id, timeout, submitting=False):
        try:
            response = await self.ctx.http.request(
                "POST", url, content=data,
                headers={"Content-Type": "application/ipp", "Accept": "application/ipp"},
                timeout=timeout, follow_redirects=False,
            )
            if response.status_code != 200:
                raise ValueError("IPP HTTP 请求未得到成功响应")
            if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/ipp":
                raise ValueError("IPP 响应类型无效")
            raw = response.content
            if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("IPP 响应超出大小上限")
            declared = response.headers.get("content-length")
            if declared is not None and (int(declared) != len(raw) or len(raw) > MAX_RESPONSE_BYTES):
                raise ValueError("IPP 响应大小不匹配")
            result = parse_response(raw, request_id)
            charset = _single(_attributes(result, 0x01), "attributes-charset")
            if charset != "utf-8":
                raise ValueError("IPP 响应未确认 UTF-8 编码")
            return result
        except asyncio.CancelledError:
            # The queue worker records unknown after its durable start marker.
            raise
        except Exception:
            if submitting:
                raise IPPSubmissionUnknown("IPP 提交响应不确定，请核查打印机；不会自动重打") from None
            raise ValueError("IPP 探测失败，请检查打印地址、FRP 连通性和打印机") from None

    async def probe(self):
        url, initial_uri, timeout, override = self._settings()
        request_id = secrets.randbelow(0x7FFFFFFF) + 1
        requested = ["printer-name", "printer-uri-supported", "document-format-supported",
                     "printer-state", "printer-is-accepting-jobs", "operations-supported", "copies-supported",
                     "print-scaling-supported", "print-scaling-default"]
        message = encode_request(GET_PRINTER_ATTRIBUTES, request_id,
                                 self._base_attributes(initial_uri) + [(0x44, "requested-attributes", requested)])
        result = await self._request(url, message, request_id, timeout)
        if result["status"] != 0:
            raise ValueError("打印机拒绝 IPP 探测，请检查原生 URI 和 IPP 设置")
        attrs = _attributes(result, 0x04)
        uri = initial_uri
        if not override:
            advertised = attrs.get("printer-uri-supported", [])
            for candidate in advertised:
                try:
                    uri = _validated_url(candidate, {"ipp", "ipps"}, "打印机原生 URI")
                    break
                except ValueError:
                    continue
        formats = attrs.get("document-format-supported", [])
        operations = attrs.get("operations-supported", [])
        if (not formats or any(not isinstance(item, str) for item in formats)
                or any(type(item) is not int for item in operations)):
            raise ValueError("打印机的 IPP 能力信息不完整")
        ranges = []
        for entry in attrs.get("copies-supported", []):
            if isinstance(entry, tuple) and len(entry) == 2 and all(type(v) is int for v in entry) and 1 <= entry[0] <= entry[1]:
                ranges.append(entry)
            elif type(entry) is int and entry >= 1:
                ranges.append((entry, entry))
            else:
                raise ValueError("打印机份数能力无效")
        ranges = ranges or [(1, 1)]
        scaling = attrs.get("print-scaling-supported", [])
        scaling_default = _single(attrs, "print-scaling-default")
        if (any(not isinstance(item, str) or not _NAME.fullmatch(item) for item in scaling)
                or (scaling_default is not None and (not isinstance(scaling_default, str)
                    or not _NAME.fullmatch(scaling_default)
                    or (scaling and scaling_default not in scaling)))):
            raise ValueError("打印机缩放能力无效")
        state = _single(attrs, "printer-state")
        accepting = _single(attrs, "printer-is-accepting-jobs", False)
        name = _single(attrs, "printer-name", "IPP 打印机")
        if type(state) is not int or state not in (3, 4, 5) or type(accepting) is not bool or not isinstance(name, str):
            raise ValueError("打印机状态信息无效")
        name = re.sub(r"[\x00-\x1f\x7f]", "", name)[:160] or "IPP 打印机"
        return {"name": name, "uri": uri, "transport_url": url, "timeout_seconds": timeout,
                "formats": sorted(set(item.lower() for item in formats)), "state": state,
                "accepting_jobs": accepting, "operations": sorted(set(operations)),
                "copies_supported": ranges, "copies_max": max(upper for _, upper in ranges),
                "print_scaling_supported": sorted(set(scaling)), "print_scaling_default": scaling_default}

    @staticmethod
    def validate_document(format, copies, capabilities):
        mime = _mime(format)
        if mime not in capabilities.get("formats", []):
            if mime == "application/pdf":
                raise ValueError("打印机不支持原生 PDF，请先导出为 JPG；不会静默丢失 PDF 页面")
            raise ValueError("打印机不支持 JPEG 图片打印，请发送其支持的 PDF")
        if mime == "image/jpeg":
            scaling = capabilities.get("print_scaling_supported", [])
            if (not isinstance(scaling, list) or any(not isinstance(item, str) for item in scaling)
                    or "fit" not in scaling):
                raise ValueError("打印机未声明支持完整等比缩放（fit），无法保证图片不裁切；请发送 PDF")
        if PRINT_JOB not in capabilities.get("operations", []):
            raise ValueError("打印机未声明支持 IPP Print-Job")
        if capabilities.get("accepting_jobs") is not True or capabilities.get("state") not in (3, 4):
            raise ValueError("打印机当前未接受任务或已暂停，请检查打印机")
        ranges = capabilities.get("copies_supported", [(1, 1)])
        if (type(copies) is not int or copies < 1
                or not any(lower <= copies <= upper for lower, upper in ranges)):
            raise ValueError("请求份数超过打印机声明的支持范围")
        return mime

    async def _thread_call(self, function, *args):
        async def drainable():
            future = asyncio.get_running_loop().run_in_executor(None, function, *args)
            try:
                return await asyncio.shield(future)
            except asyncio.CancelledError:
                while not future.done():
                    try:
                        await asyncio.shield(future)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                # Retrieve a failed result as well; never leave an unobserved future.
                if future.done() and not future.cancelled():
                    future.exception()
                raise

        coroutine = drainable()
        try:
            task = self.ctx.create_task(coroutine, name="ipp_document_io")
        except BaseException:
            coroutine.close()
            raise
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if task.done() and not task.cancelled():
                task.exception()
            raise

    async def prepare(self, path, format, destination=None):
        destination = Path(destination) if destination is not None else None
        return await self._thread_call(self._prepare, Path(path), format, destination)

    @staticmethod
    def _prepare(path, format, destination=None):
        mime = _mime(format)
        temporary = None
        try:
            if not 0 < path.stat().st_size <= MAX_FILE_BYTES:
                raise ValueError("IPP 文件为空或超过 25 MiB 上限")
            if format == "pdf":
                with path.open("rb") as file:
                    if not file.read(8).startswith(b"%PDF-"):
                        raise ValueError("PDF 文件内容无效")
                return path, mime
            from PIL import Image, ImageOps
            expected = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP"}
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    if (image.format != expected[format] or getattr(image, "n_frames", 1) != 1
                            or image.width * image.height > MAX_IMAGE_PIXELS or max(image.size) > 16000):
                        raise ValueError("IPP 图片格式、帧数或像素数量不符合限制")
                    image.load()  # Verify actual pixels, not just an image header.
                    if format in ("jpg", "jpeg") and image.getexif().get(274, 1) == 1:
                        return path, mime
                    destination = destination or path.with_suffix(".ipp.jpg")
                    if destination.resolve() == path.resolve():
                        raise ValueError("转换目标不能覆盖原始文件")
                    corrected = ImageOps.exif_transpose(image)
                    try:
                        rgba = corrected.convert("RGBA")
                        rgb = Image.new("RGB", corrected.size, "white")
                        try:
                            rgb.paste(rgba, mask=rgba.getchannel("A"))
                            fd, name = tempfile.mkstemp(prefix=".ipp-", suffix=".jpg", dir=destination.parent)
                            temporary = Path(name)
                            with os.fdopen(fd, "wb") as file:
                                rgb.save(file, format="JPEG", quality=95, dpi=(150, 150))
                        finally:
                            rgba.close()
                            rgb.close()
                    finally:
                        corrected.close()
            if not 0 < temporary.stat().st_size <= MAX_FILE_BYTES:
                raise ValueError("转换后的 JPEG 超过 25 MiB 上限，请缩小图片")
            os.replace(temporary, destination)
            temporary = None
            return destination, mime
        except ValueError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise ValueError("IPP 文档准备失败，请检查文件格式和大小") from None

    @staticmethod
    def _read_document(path):
        with Path(path).open("rb") as file:
            data = file.read(MAX_FILE_BYTES + 1)
        if not 0 < len(data) <= MAX_FILE_BYTES:
            raise ValueError("IPP 文件为空或超过 25 MiB 上限")
        return data

    async def print_job(self, path, mime, title, copies, capabilities):
        if mime not in ("application/pdf", "image/jpeg"):
            raise ValueError("IPP 提交格式不支持")
        self.validate_document("pdf" if mime == "application/pdf" else "jpg", copies, capabilities)
        if not isinstance(title, str) or not _JOB_ID.fullmatch(title):
            raise ValueError("IPP 任务名称必须使用安全的任务 ID")
        url = _validated_url(capabilities.get("transport_url"), {"http", "https"}, "IPP HTTP 地址")
        uri = _validated_url(capabilities.get("uri"), {"ipp", "ipps"}, "打印机原生 URI")
        timeout = capabilities.get("timeout_seconds", 20)
        if type(timeout) is not int or not 5 <= timeout <= 120:
            raise ValueError("IPP 超时设置无效")
        try:
            document = await self._thread_call(self._read_document, path)
        except (OSError, ValueError):
            raise ValueError("IPP 提交前无法读取受限文档") from None
        request_id = secrets.randbelow(0x7FFFFFFF) + 1
        attributes = self._base_attributes(uri) + [
            (0x42, "requesting-user-name", "AWBotNest"),
            (0x42, "job-name", "AWBotNest " + title),
            (0x22, "ipp-attribute-fidelity", True),
            (0x49, "document-format", mime),
        ]
        job_attributes = [(0x21, "copies", copies)]
        if mime == "image/jpeg":
            # IPP fit preserves the whole image and its aspect ratio within the
            # printable area; a device default such as auto/fill may crop it.
            job_attributes.append((0x44, "print-scaling", "fit"))
        message = encode_request(PRINT_JOB, request_id, attributes, job_attributes)
        result = await self._request(url, message + document, request_id, timeout, submitting=True)
        status = result["status"]
        if 0x0400 <= status <= 0x05FF:
            raise IPPRejected("打印机明确拒绝 IPP 任务，请检查格式、份数或打印机状态")
        if status != 0:
            raise IPPSubmissionUnknown("打印机忽略或替换了请求参数，结果待核查；不会自动重打")
        try:
            job_attrs = _attributes(result, 0x02)
            if (_attributes(result, 0x05) or _single(job_attrs, "copies", copies) != copies
                    or _single(job_attrs, "document-format", mime) != mime
                    or (mime == "image/jpeg" and _single(job_attrs, "print-scaling", "fit") != "fit")):
                raise ValueError
            spool_id = _single(job_attrs, "job-id")
            if type(spool_id) is not int or not 1 <= spool_id <= 0x7FFFFFFF:
                raise ValueError
        except ValueError:
            raise IPPSubmissionUnknown("打印机未返回明确任务 ID，结果待核查；不会自动重打") from None
        return {"spool_id": spool_id}
