"""Bounded image-to-PDF bundles; never submits a print job or alters sources."""
from __future__ import annotations

import hashlib
from io import BytesIO
import math
import os
from pathlib import Path
import re
import tempfile
import warnings

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter, Transformation

from .files import inspect_file


MAX_BYTES = 25 * 1024 * 1024
MAX_PAGES = 50
MAX_IMAGE_PIXELS = 25_000_000
MAX_TOTAL_PIXELS = 125_000_000
MAX_TOTAL_SOURCE_BYTES = 100 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP"}
_PAPERS = {
    "iso_a4_210x297mm": (210 * 72 / 25.4, 297 * 72 / 25.4),
    "na_letter_8.5x11in": (612.0, 792.0),
}
_MARGIN = 5 * 72 / 25.4


def validate_bundle_paper(path: Path, media: str, orientation: str = "portrait") -> None:
    """Reject paper changes before submission; never rewrite or rescale output."""
    if not isinstance(media, str) or media not in _PAPERS:
        raise ValueError("合并打印需要打印机明确声明 A4 或 Letter 默认纸张，未提交任务")
    if not isinstance(orientation, str) or orientation not in ("portrait", "landscape"):
        raise ValueError("合并打印的页面方向无效，未提交任务")
    paper = _PAPERS[media]
    if orientation == "landscape":
        paper = paper[::-1]
    try:
        path = Path(path)
        if not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError("合并打印 PDF 为空或超过安全大小，未提交任务")
        with path.open("rb") as handle:
            reader = PdfReader(handle, strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
                raise ValueError("合并打印 PDF 加密或页数不符合限制，未提交任务")
            for page in reader.pages:
                box = tuple(float(value) for value in page.mediabox)
                rotation = page.rotation
                if (not all(math.isfinite(value) for value in box)
                        or box[0] != 0 or box[1] != 0
                        or abs(box[2] - paper[0]) > 0.01 or abs(box[3] - paper[1]) > 0.01
                        or not isinstance(rotation, int) or isinstance(rotation, bool) or rotation != 0):
                    raise ValueError("合并打印的纸张与打印机当前默认纸张不一致，未提交任务；请重新发送并确认")
    except ValueError:
        raise
    except Exception:
        raise ValueError("合并打印 PDF 纸张校验失败，未提交任务") from None


def _arguments(sources, max_bytes, max_pages, media, orientation, dpi, copies, duplex):
    if (not isinstance(sources, list) or not sources
            or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES
            or type(max_pages) is not int or not 1 <= max_pages <= MAX_PAGES
            or type(dpi) is not int or dpi not in (150, 300)
            or type(copies) is not int or not 1 <= copies <= 5
            or not isinstance(orientation, str) or orientation not in ("portrait", "landscape")
            or type(duplex) is not bool):
        raise ValueError("合并打印参数无效，请检查文件、页数、大小和份数限制")
    pages_per_copy = len(sources) + (len(sources) % 2 if duplex else 0)
    if pages_per_copy * copies > max_pages:
        raise ValueError("合并打印的总页数（含每份末尾空白页）超过上限")
    if media is None:
        media = "iso_a4_210x297mm"
    if not isinstance(media, str) or media not in _PAPERS:
        raise ValueError("图片合并目前支持 A4 或 Letter 纸张，请检查打印机默认纸张")
    paper = _PAPERS[media]
    return (paper[::-1] if orientation == "landscape" else paper), pages_per_copy


def _sources(sources, destination, max_bytes):
    result, identifiers, paths, total_bytes = [], set(), set(), 0
    for source in sources:
        if (not isinstance(source, dict)
                or not isinstance(source.get("id"), str) or not _ID.fullmatch(source["id"])
                or not isinstance(source.get("filename"), str) or not source["filename"]
                or not isinstance(source.get("sha256"), str) or not _DIGEST.fullmatch(source["sha256"])
                or source.get("format") not in _FORMATS
                or type(source.get("size")) is not int or not 0 < source["size"] <= max_bytes
                or not isinstance(source.get("path"), (str, Path))):
            raise ValueError("合并打印只支持已校验的单张图片，文件记录不完整")
        path = Path(source["path"])
        if path.is_symlink() or not path.is_file():
            raise ValueError("合并打印的原始图片不存在或不是普通文件")
        resolved = path.resolve()
        if source["id"] in identifiers or resolved in paths:
            raise ValueError("合并打印包含重复文件，请重新选择图片")
        if resolved == destination:
            raise ValueError("合并目标不能覆盖原始图片")
        identifiers.add(source["id"])
        paths.add(resolved)
        total_bytes += source["size"]
        if total_bytes > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("合并图片的总文件大小超过安全上限，请分批打印")
        result.append((source, resolved))
    return result


def _snapshot(source, path, max_bytes):
    with path.open("rb") as handle:
        content = handle.read(max_bytes + 1)
    if (len(content) != source["size"] or not 0 < len(content) <= max_bytes
            or hashlib.sha256(content).hexdigest() != source["sha256"]):
        raise ValueError("合并图片内容与收件记录不一致，已停止打印准备")
    return content


def _image_page(content, format, paper, dpi):
    width, height = paper
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(content)) as image:
            if (image.format != _FORMATS[format] or getattr(image, "n_frames", 1) != 1
                    or not 0 < image.width * image.height <= MAX_IMAGE_PIXELS or max(image.size) > 16000):
                raise ValueError("合并图片格式、帧数或分辨率不符合限制")
            source_pixels = image.width * image.height
            # Apply rotation before fit, then reduce the raster before creating
            # RGBA/RGB copies. Never keep full-size RGB canvases for all pages.
            image.load()
            ImageOps.exif_transpose(image, in_place=True)
            scale = min((width - 2 * _MARGIN) / image.width, (height - 2 * _MARGIN) / image.height)
            draw_width, draw_height = image.width * scale, image.height * scale
            bounds = (max(1, math.ceil(draw_width * dpi / 72)), max(1, math.ceil(draw_height * dpi / 72)))
            image.thumbnail(bounds, Image.Resampling.LANCZOS)
            rendered_pixels = image.width * image.height
            rgba = image.convert("RGBA")
            rgb = Image.new("RGB", image.size, "white")
            try:
                with rgba.getchannel("A") as alpha:
                    rgb.paste(rgba, mask=alpha)
                output = BytesIO()
                rgb.save(output, format="PDF", resolution=dpi, quality=95)
                return output.getvalue(), (draw_width, draw_height), source_pixels, rendered_pixels
            finally:
                rgba.close()
                rgb.close()


def build_image_bundle(sources: list[dict], destination: Path, max_bytes: int, max_pages: int,
                       media: str | None = None, *, orientation: str = "portrait",
                       dpi: int = 150, copies: int = 1,
                       duplex: bool = True) -> dict:
    """Make complete, ordered paper-size pages, including copy-boundary blanks.

    Sources require id/path/filename/sha256/format/size. One image becomes one
    page; an odd duplex copy gets one trailing blank. Complete copies are then
    repeated in the PDF, allowing exactly one backend job with device copies=1.
    Every page uses the selected paper orientation; source images remain
    upright after EXIF correction and fit fully without cropping.
    The returned metadata uses inspect_file's actual output page count/hash.
    """
    paper, pages_per_copy = _arguments(sources, max_bytes, max_pages, media, orientation, dpi, copies, duplex)
    temporary = None
    writer = master = None
    try:
        destination = Path(destination)
        if destination.is_symlink() or destination.exists() or not destination.parent.is_dir():
            raise ValueError("合并目标已存在或目录不可用，不能覆盖现有文件")
        resolved_destination = destination.resolve()
        checked = _sources(sources, resolved_destination, max_bytes)
        master = PdfWriter()
        source_pixels = rendered_pixels = encoded_bytes = 0
        for source, path in checked:
            content = _snapshot(source, path, max_bytes)
            encoded, draw, pixels, rendered = _image_page(content, source["format"], paper, dpi)
            source_pixels += pixels
            rendered_pixels += rendered
            encoded_bytes += len(encoded)
            if source_pixels > MAX_TOTAL_PIXELS or rendered_pixels > MAX_TOTAL_PIXELS:
                raise ValueError("合并图片总像素超过安全上限，请分批打印")
            if encoded_bytes > max_bytes:
                raise ValueError("合并 PDF 超过大小上限，请缩小图片或分批打印")
            reader = PdfReader(BytesIO(encoded), strict=True)
            image_page = reader.pages[0]
            page = master.add_blank_page(width=paper[0], height=paper[1])
            # Use exact point dimensions for the image and paper. The raster's
            # rounding must not stretch its original aspect ratio in the PDF.
            transform = (Transformation()
                         .scale(draw[0] / float(image_page.mediabox.width), draw[1] / float(image_page.mediabox.height))
                         .translate((paper[0] - draw[0]) / 2, (paper[1] - draw[1]) / 2))
            page.merge_transformed_page(image_page, transform)
            del content, encoded, reader, image_page
        if duplex and len(sources) % 2:
            master.add_blank_page(width=paper[0], height=paper[1])
        writer = PdfWriter()
        for _ in range(copies):
            for page in master.pages:
                writer.add_page(page)
        if len(writer.pages) != pages_per_copy * copies:
            raise ValueError("合并 PDF 页数校验失败，未提交打印")
        fd, name = tempfile.mkstemp(prefix=".bundle-", suffix=".pdf", dir=destination.parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as handle:
            writer.write(handle)
            handle.flush()
            os.fsync(handle.fileno())
        metadata = inspect_file(temporary, destination.name, max_bytes, max_pages)
        if (metadata["format"] != "pdf" or metadata["pages"] != pages_per_copy * copies
                or metadata["orientation"] != orientation or metadata["orientation_mixed"]):
            raise ValueError("合并 PDF 最终校验失败，未提交打印")
        # The queue exclusively owns this opaque destination. Check again after
        # preparation so existing outputs or source files are never replaced.
        if destination.exists() or destination.is_symlink():
            raise ValueError("合并目标已存在，不能覆盖现有文件")
        os.replace(temporary, destination)
        temporary = None
        return metadata
    except ValueError:
        raise
    except Exception:
        raise ValueError("图片合并准备失败，请检查图片格式、目录和文件大小") from None
    finally:
        if writer is not None:
            writer.close()
        if master is not None:
            master.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
