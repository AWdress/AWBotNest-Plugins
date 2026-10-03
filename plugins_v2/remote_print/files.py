"""打印文件的受限识别；不执行上传文件、不根据用户文件名生成存储路径。"""
from __future__ import annotations

import hashlib
import re
import warnings
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


FORMATS = {"pdf", "png", "jpg", "jpeg", "webp", "bmp"}


def safe_name(name: str) -> str:
    name = re.split(r"[/\\]", str(name))[-1]
    return re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:160] or "document"


def inspect_file(path: Path, name: str, max_bytes: int, max_pages: int) -> dict:
    size = path.stat().st_size
    if not 0 < size <= max_bytes:
        raise ValueError("文件为空或超过大小上限")
    with path.open("rb") as handle:
        magic = handle.read(16)
    if magic.startswith(b"%PDF-"):
        try:
            with path.open("rb") as handle:
                reader = PdfReader(handle, strict=True)
                if reader.is_encrypted:
                    raise ValueError("不支持加密 PDF，请先解除密码")
                pages = len(reader.pages)
                if not 1 <= pages <= max_pages:
                    raise ValueError("PDF 页数超过上限或没有页面")
        except ValueError:
            raise
        except Exception:
            raise ValueError("PDF 损坏或无法读取，请重新导出") from None
        kind = "pdf"
    else:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    kind = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "BMP": "bmp"}.get(image.format, "")
                    if not kind or getattr(image, "n_frames", 1) != 1:
                        raise ValueError("仅支持 PDF 和单张 JPG、PNG、WebP、BMP 图片")
                    if image.width * image.height > 25_000_000 or max(image.size) > 16_000:
                        raise ValueError("图片分辨率过大，请缩小后重试")
                    image.verify()
            pages = 1
        except ValueError:
            raise
        except Exception:
            raise ValueError("图片损坏或格式不支持，请发送 PDF 或常见图片") from None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    filename = safe_name(name)
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension != kind and not (kind == "jpg" and extension == "jpeg"):
        filename = f"{Path(filename).stem}.{kind}"
    return {"filename": filename, "format": kind, "pages": pages, "size": size, "sha256": digest.hexdigest()}
