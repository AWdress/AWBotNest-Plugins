"""Outbound-only Windows print receiver. No inbound listener or shell printing."""

from __future__ import annotations

import argparse
import copy
import ctypes
from ctypes import wintypes
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit
import warnings

VERSION = "0.0.5"
FORMATS = ("pdf", "png", "jpg", "jpeg", "webp", "bmp")
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_PAGE_PIXELS = 25_000_000
MAX_DOCUMENT_PIXELS = 60_000_000
MAX_PAGES = 50
MAX_COPIES = 10
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")
SHA_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class AgentError(Exception):
    """A deliberately generic, safe-to-display failure."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default repeats user arguments, which can accidentally contain secrets.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid command-line arguments. Use --help for supported options.\n")


class PrintError(AgentError):
    def __init__(self, status: str, spool_id: int | None = None):
        super().__init__("Printer submission failed; inspect the Windows print queue.")
        self.status = status
        self.spool_id = spool_id


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


class Config:
    def __init__(self, path: Path):
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise AgentError("Cannot read the configuration JSON.") from None
        if not isinstance(value, dict):
            raise AgentError("Configuration must be a JSON object.")
        self.token = value.get("token")
        if not isinstance(self.token, str) or not 32 <= len(self.token) <= 512:
            raise AgentError("Configure a device token of at least 32 characters.")
        if any(ord(char) < 33 or ord(char) > 126 for char in self.token):
            raise AgentError("The device token must contain printable ASCII without spaces.")
        self.device_id = value.get("device_id")
        if not isinstance(self.device_id, str) or not ID_RE.fullmatch(self.device_id):
            raise AgentError("Configure a device_id using letters, digits, underscores or hyphens.")
        self.allow_insecure = value.get("allow_insecure_localhost", False)
        self.allow_virtual = value.get("allow_virtual_printers", False)
        if type(self.allow_insecure) is not bool or type(self.allow_virtual) is not bool:
            raise AgentError("Configuration switches must be true or false.")
        self.server_url = self._server_url(value.get("server_url"))
        self.allowed = value.get("allowed_printers")
        if (not isinstance(self.allowed, list) or not 1 <= len(self.allowed) <= 32
                or any(not isinstance(name, str) or not name.strip() or len(name) > 256
                       or any(ord(c) < 32 for c in name) for name in self.allowed)
                or len(set(self.allowed)) != len(self.allowed)):
            raise AgentError("Configure a nonempty allowed_printers list of exact Windows names.")
        self.default = value.get("default_printer", "")
        if not isinstance(self.default, str) or (self.default and self.default not in self.allowed):
            raise AgentError("default_printer must be included in allowed_printers.")
        self.poll_seconds = value.get("poll_seconds", 5)
        self.render_dpi = value.get("render_dpi", 150)
        if not integer(self.poll_seconds, 1, 300) or not integer(self.render_dpi, 72, 200):
            raise AgentError("poll_seconds must be 1–300; render_dpi must be 72–200.")
        state_dir = value.get("state_dir")
        if state_dir is not None:
            if not isinstance(state_dir, str) or not state_dir.strip():
                raise AgentError("state_dir must be a directory path.")
            self.state_dir = Path(state_dir)
            if not self.state_dir.is_absolute():
                self.state_dir = path.resolve().parent / self.state_dir
        else:
            base = os.environ.get("LOCALAPPDATA")
            if not base:
                raise AgentError("Configure state_dir when LOCALAPPDATA is unavailable.")
            self.state_dir = Path(base) / "AWRemotePrint" / self.device_id

    def _server_url(self, value):
        if not isinstance(value, str) or len(value) > 2048:
            raise AgentError("Configure an HTTPS server_url without credentials, query or fragment.")
        try:
            parsed = urlsplit(value)
            port = parsed.port
            hostname = parsed.hostname
        except ValueError:
            raise AgentError("Invalid server_url.") from None
        if (not hostname or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or any(ord(c) <= 32 for c in value)
                or "\\" in value or "%" in parsed.netloc or (port is not None and port < 1)):
            raise AgentError("server_url cannot contain credentials, query, fragment or whitespace.")
        loopback = hostname.lower() == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if parsed.scheme != "https" and not (
                parsed.scheme == "http" and loopback and self.allow_insecure):
            raise AgentError("HTTPS is required; HTTP loopback needs allow_insecure_localhost=true.")
        if parsed.path and (not parsed.path.startswith("/") or ".." in parsed.path.split("/")):
            raise AgentError("Invalid server_url path.")
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


class SingleInstance:
    def __init__(self, directory: Path):
        try:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.file = (directory / "agent.lock").open("a+b")
            if self.file.seek(0, os.SEEK_END) == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if hasattr(self, "file"):
                self.file.close()
            raise AgentError("Cannot lock local state; another receiver may be running.") from None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.file.close()


def atomic_json(path: Path, value):
    """Flush the replacement before publishing; Windows also flushes its rename."""
    fd, temporary = tempfile.mkstemp(prefix=".journal-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, ensure_ascii=False, separators=(",", ":"))
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        if os.name == "nt":
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            move = kernel.MoveFileExW
            move.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
            move.restype = wintypes.BOOL
            if not move(temporary, str(path), 0x1 | 0x8):
                raise OSError("journal rename failed")
        else:
            os.replace(temporary, path)
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class Journal:
    def __init__(self, directory: Path):
        self.path = directory / "journal.json"
        self.entries = {}
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                entries = raw["entries"]
                if raw.get("version") != 1 or not isinstance(entries, dict):
                    raise ValueError
                for job_id, entry in entries.items():
                    if (not isinstance(job_id, str) or not ID_RE.fullmatch(job_id)
                            or not isinstance(entry, dict)
                            or entry.get("phase") not in ("started", "outcome", "acknowledged")):
                        raise ValueError
                    if entry["phase"] != "acknowledged" and not valid_claim(entry.get("claim_token")):
                        raise ValueError
                    if entry["phase"] != "started" and entry.get("status") not in ("submitted", "failed", "unknown"):
                        raise ValueError
                    if entry["phase"] == "outcome" and not isinstance(entry.get("message"), str):
                        raise ValueError
                self.entries = entries
            except (OSError, ValueError, KeyError, TypeError):
                raise AgentError("Local journal is damaged; stop and review it before printing.") from None

    def _write(self, entries):
        try:
            atomic_json(self.path, {"version": 1, "entries": entries})
        except OSError:
            raise AgentError("Cannot durably save the local journal; printing stopped.") from None
        self.entries = entries

    def started(self, job_id, claim):
        entries = copy.deepcopy(self.entries)
        entries[job_id] = {"phase": "started", "claim_token": claim}
        self._write(entries)

    def outcome(self, job_id, claim, status, message, spool_id=None):
        entries = copy.deepcopy(self.entries)
        entry = {"phase": "outcome", "claim_token": claim, "status": status, "message": message}
        if spool_id is not None:
            entry["spool_id"] = spool_id
        entries[job_id] = entry
        self._write(entries)

    def acknowledge(self, job_id):
        entries = copy.deepcopy(self.entries)
        entry = entries[job_id]
        entries[job_id] = {"phase": "acknowledged", "status": entry["status"]}
        self._write(entries)

    def recover(self):
        for job_id, entry in list(self.entries.items()):
            if entry["phase"] == "started":
                self.outcome(job_id, entry["claim_token"], "unknown",
                             "Previous attempt interrupted; inspect the Windows print queue.")


def valid_claim(value):
    return (isinstance(value, str) and 32 <= len(value) <= 512
            and all(33 <= ord(char) <= 126 for char in value))


class API:
    def __init__(self, config: Config):
        try:
            import httpx
        except ImportError:
            raise AgentError("Install the receiver requirements before connecting.") from None
        self.httpx = httpx
        self.base = config.server_url + "/api/plugin/remote_print/"
        self.client = httpx.Client(
            headers={"Authorization": "Bearer " + config.token,
                     "X-Print-Device": config.device_id},
            verify=True, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(30, connect=10, write=10, pool=10),
        )

    def close(self):
        self.client.close()

    def operation(self, **payload):
        try:
            with self.client.stream("POST", self.base + "agent", json=payload) as response:
                if response.status_code != 200:
                    raise AgentError("Server rejected the request.")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise AgentError("Server response exceeded the local limit.")
            value = json.loads(data)
            if not isinstance(value, dict) or type(value.get("ok")) is not bool:
                raise AgentError("Invalid server response.")
            return value
        except (self.httpx.HTTPError, ValueError):
            raise AgentError("Server connection or response unavailable.") from None

    def download(self, job, target: Path):
        digest = hashlib.sha256()
        size = 0
        try:
            with self.client.stream(
                    "GET", self.base + "agent_file", params={"job_id": job["id"]},
                    headers={"X-Print-Claim": job["claim_token"]}) as response:
                if response.status_code != 200:
                    raise AgentError("Server did not provide the claimed file.")
                with target.open("xb") as file:
                    for chunk in response.iter_bytes(chunk_size=64 * 1024):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES or size > job["size"]:
                            raise AgentError("Downloaded file exceeded the local limit.")
                        digest.update(chunk)
                        file.write(chunk)
        except (self.httpx.HTTPError, OSError):
            raise AgentError("File download failed.") from None
        if size != job["size"] or digest.hexdigest() != job["sha256"].lower():
            raise AgentError("Downloaded file size or checksum did not match.")


class PRINTER_INFO_4(ctypes.Structure):
    _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR),
                ("Attributes", wintypes.DWORD)]


class DOCINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR),
                ("lpszOutput", wintypes.LPCWSTR), ("lpszDatatype", wintypes.LPCWSTR),
                ("fwType", wintypes.DWORD)]


class DEVMODE_PRINTER_PREFIX(ctypes.Structure):
    """Public DEVMODEW prefix, through its printer union; private bytes stay intact."""
    _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
                ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
                ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
                ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]


class WindowsPrinter:
    def __init__(self):
        if os.name != "nt":
            raise AgentError("This receiver supports Windows only.")
        self.spool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        self.spool.EnumPrintersW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD,
                                            ctypes.c_void_p, wintypes.DWORD,
                                            ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
        self.spool.EnumPrintersW.restype = wintypes.BOOL
        self.spool.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.spool.GetDefaultPrinterW.restype = wintypes.BOOL
        self.spool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
        self.spool.OpenPrinterW.restype = wintypes.BOOL
        self.spool.ClosePrinter.argtypes = [wintypes.HANDLE]
        self.spool.ClosePrinter.restype = wintypes.BOOL
        self.spool.DocumentPropertiesW.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.LPWSTR,
                                                  ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        self.spool.DocumentPropertiesW.restype = wintypes.LONG
        signatures = {
            "CreateDCW": ([wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p], wintypes.HDC),
            "DeleteDC": ([wintypes.HDC], wintypes.BOOL),
            "GetDeviceCaps": ([wintypes.HDC, ctypes.c_int], ctypes.c_int),
            "StartDocW": ([wintypes.HDC, ctypes.POINTER(DOCINFO)], ctypes.c_int),
            "StartPage": ([wintypes.HDC], ctypes.c_int),
            "EndPage": ([wintypes.HDC], ctypes.c_int),
            "EndDoc": ([wintypes.HDC], ctypes.c_int),
            "AbortDoc": ([wintypes.HDC], ctypes.c_int),
            "SetStretchBltMode": ([wintypes.HDC, ctypes.c_int], ctypes.c_int),
            "SetBrushOrgEx": ([wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p], wintypes.BOOL),
            "StretchDIBits": ([wintypes.HDC] + [ctypes.c_int] * 8
                              + [ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT, wintypes.DWORD], ctypes.c_int),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.gdi, name)
            function.argtypes, function.restype = args, result

    def inventory(self):
        required, returned = wintypes.DWORD(), wintypes.DWORD()
        self.spool.EnumPrintersW(2 | 4, None, 4, None, 0, ctypes.byref(required), ctypes.byref(returned))
        if required.value:
            buffer = ctypes.create_string_buffer(required.value)
            if not self.spool.EnumPrintersW(2 | 4, None, 4, buffer, len(buffer),
                                            ctypes.byref(required), ctypes.byref(returned)):
                raise AgentError("Cannot enumerate Windows printers.")
            info = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4))
            names = sorted({info[index].pPrinterName for index in range(returned.value)
                            if info[index].pPrinterName})
        elif ctypes.get_last_error() not in (0, 122):
            raise AgentError("Cannot enumerate Windows printers.")
        else:
            names = []
        size = wintypes.DWORD()
        self.spool.GetDefaultPrinterW(None, ctypes.byref(size))
        default = ""
        if size.value:
            buffer = ctypes.create_unicode_buffer(size.value)
            if self.spool.GetDefaultPrinterW(buffer, ctypes.byref(size)):
                default = buffer.value
        return names, default

    def document_settings(self, printer):
        """Use a private per-document DEVMODE copy; never call SetPrinter."""
        handle = wintypes.HANDLE()
        if not self.spool.OpenPrinterW(printer, ctypes.byref(handle), None):
            raise PrintError("failed")
        try:
            size = self.spool.DocumentPropertiesW(None, handle, printer, None, None, 0)
            if not ctypes.sizeof(DEVMODE_PRINTER_PREFIX) <= size <= 1024 * 1024:
                raise PrintError("failed")
            buffer = ctypes.create_string_buffer(size)
            if self.spool.DocumentPropertiesW(None, handle, printer, buffer, None, 2) != 1:
                raise PrintError("failed")
            mode = ctypes.cast(buffer, ctypes.POINTER(DEVMODE_PRINTER_PREFIX)).contents
            if (mode.dmSize < ctypes.sizeof(DEVMODE_PRINTER_PREFIX)
                    or mode.dmSize + mode.dmDriverExtra > size):
                raise PrintError("failed")
            mode.dmFields |= 0x100  # DM_COPIES
            mode.dmCopies = 1  # Copies are implemented by our complete-document loop.
            # Ask the driver to validate its private bytes without prompting or saving defaults.
            if (self.spool.DocumentPropertiesW(None, handle, printer, buffer, buffer, 2 | 8) != 1
                    or mode.dmCopies != 1):
                raise PrintError("failed")
            return buffer
        except PrintError:
            raise
        except Exception:
            raise PrintError("failed") from None
        finally:
            self.spool.ClosePrinter(handle)

    def print_pages(self, printer, pages, copies, job_id, stopped):
        """Only rasterized pixels reach GDI. Printer defaults are never changed."""
        from PIL import Image
        settings = self.document_settings(printer)
        hdc = self.gdi.CreateDCW("WINSPOOL", printer, None, settings)
        if not hdc:
            raise PrintError("failed")
        spool_id = None
        attempted = False
        finished = False
        try:
            width = self.gdi.GetDeviceCaps(hdc, 8)   # HORZRES (printable area)
            height = self.gdi.GetDeviceCaps(hdc, 10)  # VERTRES
            dpi_x = self.gdi.GetDeviceCaps(hdc, 88)
            dpi_y = self.gdi.GetDeviceCaps(hdc, 90)
            if min(width, height, dpi_x, dpi_y) <= 0:
                raise PrintError("failed")
            doc = DOCINFO(ctypes.sizeof(DOCINFO), "AW remote print " + job_id, None, None, 0)
            if stopped():
                raise PrintError("failed")
            attempted = True
            result = self.gdi.StartDocW(hdc, ctypes.byref(doc))
            if result <= 0:
                attempted = False
                raise PrintError("failed")
            spool_id = result
            for _ in range(copies):
                for page in pages:
                    if stopped():
                        raise PrintError("unknown", spool_id)
                    if self.gdi.StartPage(hdc) <= 0:
                        raise PrintError("unknown", spool_id)
                    with Image.open(page) as image:
                        image = image.convert("RGB")
                        try:
                            page_width, page_height = image.size
                            stride = ((page_width * 3 + 3) // 4) * 4
                            bits = image.tobytes("raw", "BGR", stride, 1)
                        finally:
                            image.close()
                    # Respect nonsquare device pixels when fitting the image.
                    scale = min(width / dpi_x / page_width, height / dpi_y / page_height)
                    out_width = max(1, int(page_width * scale * dpi_x))
                    out_height = max(1, int(page_height * scale * dpi_y))
                    bitmap = BITMAPINFO()
                    bitmap.bmiHeader = BITMAPINFOHEADER(
                        ctypes.sizeof(BITMAPINFOHEADER), page_width, -page_height, 1, 24,
                        0, len(bits), 0, 0, 0, 0)
                    self.gdi.SetStretchBltMode(hdc, 4)  # HALFTONE
                    self.gdi.SetBrushOrgEx(hdc, 0, 0, None)
                    buffer = ctypes.create_string_buffer(bits)
                    result = self.gdi.StretchDIBits(
                        hdc, (width - out_width) // 2, (height - out_height) // 2,
                        out_width, out_height, 0, 0, page_width, page_height,
                        buffer, ctypes.byref(bitmap), 0, 0x00CC0020)
                    if result in (0, -1) or self.gdi.EndPage(hdc) <= 0:
                        raise PrintError("unknown", spool_id)
            if self.gdi.EndDoc(hdc) <= 0:
                raise PrintError("unknown", spool_id)
            finished = True
            return spool_id
        except PrintError:
            raise
        except BaseException:
            raise PrintError("unknown" if attempted else "failed", spool_id) from None
        finally:
            if attempted and not finished:
                self.gdi.AbortDoc(hdc)
            self.gdi.DeleteDC(hdc)


def is_virtual(name):
    lowered = name.casefold()
    return any(part in lowered for part in ("print to pdf", "xps", "onenote", "fax", "pdf printer", "pdfcreator"))


def advertised(config, backend):
    names, default = backend.inventory()
    available = [name for name in config.allowed if name in names
                 and (config.allow_virtual or not is_virtual(name))]
    if not available:
        raise AgentError("No configured physical printer is available.")
    if config.default:
        if config.default not in available:
            raise AgentError("The configured default printer is unavailable or blocked.")
        default = config.default
    elif default not in available:
        default = available[0]
    return {"printers": available, "default_printer": default,
            "formats": list(FORMATS), "version": VERSION}


def validate_job(value, inventory):
    if not isinstance(value, dict):
        raise AgentError("Invalid job metadata.")
    job_id, claim = value.get("id"), value.get("claim_token")
    if not isinstance(job_id, str) or not ID_RE.fullmatch(job_id) or not valid_claim(claim):
        raise AgentError("Invalid claimed job identity.")
    if (not isinstance(value.get("filename"), str) or len(value["filename"]) > 255
            or not integer(value.get("size"), 1, MAX_FILE_BYTES)
            or not isinstance(value.get("sha256"), str) or not SHA_RE.fullmatch(value["sha256"])
            or value.get("format") not in FORMATS
            or not integer(value.get("copies"), 1, MAX_COPIES)
            or not integer(value.get("max_pages"), 1, MAX_PAGES)):
        raise AgentError("Job exceeds supported local limits or has invalid metadata.")
    printer = value.get("printer")
    if not isinstance(printer, str):
        raise AgentError("Invalid printer selection.")
    printer = printer or inventory["default_printer"]
    if printer not in inventory["printers"]:
        raise AgentError("The requested printer is not in the available local allowlist.")
    job = dict(value)
    job["printer"] = printer
    return job


def prepare_pages(source: Path, job, directory: Path, render_dpi):
    """Fully decode/rasterize before claiming permission to spool anything."""
    try:
        from PIL import Image, ImageOps
        import pypdfium2 as pdfium
    except ImportError:
        raise AgentError("Install the receiver requirements before printing.") from None
    Image.MAX_IMAGE_PIXELS = MAX_PAGE_PIXELS
    total_pixels = 0
    pages = []

    def save_page(image):
        nonlocal total_pixels
        width, height = image.size
        total_pixels += width * height
        if (width < 1 or height < 1 or width * height > MAX_PAGE_PIXELS
                or total_pixels > MAX_DOCUMENT_PIXELS):
            raise AgentError("Rendered document exceeds local pixel limits.")
        output = directory / ("page-" + str(len(pages) + 1) + ".bmp")
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            rgb = Image.new("RGB", image.size, "white")
            try:
                rgb.paste(rgba, mask=rgba.getchannel("A"))
                rgb.save(output, format="BMP")
            finally:
                rgba.close()
                rgb.close()
        else:
            rgb = image.convert("RGB")
            try:
                rgb.save(output, format="BMP")
            finally:
                rgb.close()
        pages.append(output)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            if job["format"] == "pdf":
                document = pdfium.PdfDocument(str(source))
                try:
                    if not 1 <= len(document) <= job["max_pages"]:
                        raise AgentError("PDF page count exceeds the job limit.")
                    for index in range(len(document)):
                        page = document[index]
                        try:
                            width, height = page.get_size()
                            scale = render_dpi / 72
                            if (not all(math.isfinite(v) and 0 < v <= 14400 for v in (width, height))
                                    or math.ceil(width * scale) * math.ceil(height * scale) > MAX_PAGE_PIXELS
                                    or total_pixels + math.ceil(width * scale) * math.ceil(height * scale)
                                    > MAX_DOCUMENT_PIXELS):
                                raise AgentError("PDF page dimensions exceed local limits.")
                            bitmap = page.render(scale=scale, rev_byteorder=True)
                            try:
                                image = bitmap.to_pil()
                                try:
                                    save_page(image)
                                finally:
                                    image.close()
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
                finally:
                    document.close()
            else:
                with Image.open(source) as image:
                    expected = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP"}
                    if image.format != expected[job["format"]] or getattr(image, "n_frames", 1) != 1:
                        raise AgentError("Image type differs from the job or has multiple frames.")
                    corrected = ImageOps.exif_transpose(image)
                    try:
                        save_page(corrected)
                    finally:
                        corrected.close()
        return pages
    except AgentError:
        raise
    except Exception:
        raise AgentError("Document could not be safely decoded or rendered.") from None


class Receiver:
    def __init__(self, config, api, journal, backend):
        self.config, self.api, self.journal, self.backend = config, api, journal, backend
        self.stop_requested = False

    def stop(self, *_):
        self.stop_requested = True

    def acknowledge(self):
        pending = [(key, value) for key, value in self.journal.entries.items() if value["phase"] == "outcome"]
        for job_id, entry in pending:
            payload = {"op": "result", "job_id": job_id, "claim_token": entry["claim_token"],
                       "status": entry["status"], "message": entry["message"]}
            if "spool_id" in entry:
                payload["spool_id"] = entry["spool_id"]
            response = self.api.operation(**payload)
            if response.get("ok") is not True:
                raise AgentError("Server did not acknowledge the durable print outcome.")
            self.journal.acknowledge(job_id)

    def process(self, value, inventory):
        if not isinstance(value, dict):
            raise AgentError("Invalid claimed job.")
        job_id, claim = value.get("id"), value.get("claim_token")
        if not isinstance(job_id, str) or not ID_RE.fullmatch(job_id) or not valid_claim(claim):
            raise AgentError("Invalid claimed job identity.")
        if job_id in self.journal.entries:
            print("Previously recorded job skipped; no repeat submission.", flush=True)
            return
        try:
            job = validate_job(value, inventory)
            with tempfile.TemporaryDirectory(prefix="work-", dir=self.config.state_dir) as temporary:
                directory = Path(temporary)
                source = directory / "document"
                self.api.download(job, source)
                pages = prepare_pages(source, job, directory, self.config.render_dpi)
                if self.stop_requested:
                    self.journal.outcome(job_id, claim, "failed", "Receiver stopped before submission.")
                    return
                # This durable marker MUST precede the start request, including retries/crashes.
                self.journal.started(job_id, claim)
                try:
                    response = self.api.operation(op="start", job_id=job_id, claim_token=claim)
                except AgentError:
                    self.journal.outcome(job_id, claim, "unknown", "Print authorization response unavailable.")
                    return
                if response.get("ok") is not True or response.get("proceed") is not True:
                    status = "failed" if response.get("ok") is False or response.get("proceed") is False else "unknown"
                    self.journal.outcome(job_id, claim, status, "Server did not authorize printing.")
                    return
                try:
                    spool_id = self.backend.print_pages(
                        job["printer"], pages, job["copies"], job_id, lambda: self.stop_requested)
                except PrintError as error:
                    self.journal.outcome(job_id, claim, error.status,
                                         "Printer submission failed; inspect the Windows print queue.", error.spool_id)
                except BaseException:
                    self.journal.outcome(job_id, claim, "unknown", "Print attempt interrupted; inspect the Windows print queue.")
                    raise
                else:
                    self.journal.outcome(job_id, claim, "submitted", "Submitted to the Windows print queue.", spool_id)
        except AgentError:
            # Never downgrade a started/unknown submission to a retryable local failure.
            if job_id not in self.journal.entries:
                self.journal.outcome(job_id, claim, "failed", "Local validation, download or rendering failed.")
            else:
                raise
        except (OSError, ValueError):
            if job_id not in self.journal.entries:
                self.journal.outcome(job_id, claim, "failed", "Local document preparation failed.")
            else:
                raise AgentError("Local failure after authorization; printing stopped.") from None

    def run(self, once=False):
        self.journal.recover()
        last_error = 0.0
        registered = False
        while not self.stop_requested:
            try:
                inventory = advertised(self.config, self.backend)
                if not registered:
                    response = self.api.operation(op="hello", **inventory)
                    if response.get("ok") is not True:
                        raise AgentError("Server authentication or device registration failed.")
                    registered = True
                    print("Receiver connected. Only explicitly allowed Windows printers can receive jobs.", flush=True)
                self.acknowledge()
                response = self.api.operation(op="poll", **inventory)
                if response.get("ok") is not True or "job" not in response:
                    raise AgentError("Server poll failed or returned an invalid response.")
                if response["job"] is not None:
                    self.process(response["job"], inventory)
                    self.acknowledge()
            except AgentError as error:
                # Journal persistence failures are fatal: continuing could lose print deduplication.
                if "journal" in str(error).lower():
                    raise
                if once:
                    raise
                if time.monotonic() - last_error >= 30:
                    print(str(error), file=sys.stderr, flush=True)
                    last_error = time.monotonic()
            if once:
                return
            deadline = time.monotonic() + self.config.poll_seconds
            while not self.stop_requested and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))


def main(argv=None):
    parser = SafeArgumentParser(description="Outbound HTTPS Windows print receiver")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list-printers", action="store_true", help="List Windows printers; no server connection or printing")
    mode.add_argument("--check", action="store_true", help="Validate configuration, printers, dependencies and server authentication; no printing")
    mode.add_argument("--once", action="store_true", help="Process at most one poll, then exit")
    args = parser.parse_args(argv)
    api = None
    try:
        backend = WindowsPrinter()
        if args.list_printers:
            names, default = backend.inventory()
            print(json.dumps({"printers": names, "default_printer": default}, ensure_ascii=False, indent=2))
            return 0
        config = Config(args.config)
        inventory = advertised(config, backend)
        try:
            import PIL
            import pypdfium2
        except ImportError:
            raise AgentError("Install the receiver requirements before connecting.") from None
        api = API(config)
        with SingleInstance(config.state_dir):
            if args.check:
                response = api.operation(op="hello", **inventory)
                if response.get("ok") is not True:
                    raise AgentError("Server authentication or device registration failed.")
                print("Check passed: configuration, dependencies, allowed printers and server connection. No printing performed.")
                return 0
            receiver = Receiver(config, api, Journal(config.state_dir), backend)
            signal.signal(signal.SIGINT, receiver.stop)
            signal.signal(signal.SIGTERM, receiver.stop)
            print("Receiver started; waiting for the server. Press Ctrl+C to stop.", flush=True)
            receiver.run(once=args.once)
            return 0
    except AgentError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception:
        # Do not expose URLs, query strings, document metadata or credentials in tracebacks.
        print("Receiver stopped after an unexpected local failure; review its journal and print queue.", file=sys.stderr)
        return 1
    finally:
        if api is not None:
            api.close()


if __name__ == "__main__":
    sys.exit(main())
