# =============================================================================
# 自动抢红包插件 - 验证码 OCR 识别（可选依赖 ddddocr / Pillow）
#
# ddddocr 是单行验证码模型，正对本场景（红包把口令渲染成扭曲验证码图）。二者均为
# 「可选」依赖：缺失时 OCR 自动降级——不抛错、不阻止插件加载，识别时返回空字符串，
# 上层逻辑会退回「复制他人已确认口令」模式（复制模式无需任何依赖即可工作）。
#
# 识别策略（多策略取最长结果，提升扭曲验证码命中率）：
#   1. 默认模型 + 原图
#   2. 默认模型 + 阈值 80 二值化预处理
#   3. 默认模型 + 阈值 110 二值化预处理
#   4. 旧版模型 + 阈值 80 预处理（若可用，与默认模型互补）
# =============================================================================
from __future__ import annotations

import asyncio
import io
import re

# ddddocr 懒加载单例。None=未初始化；False=初始化失败/不可用；object=可用实例。
_ocr_main = None
_ocr_old = None
_avail_checked = False
_avail = False


def ocr_available() -> bool:
    """ddddocr 是否可用（只检测 import，不强制初始化模型）。"""
    global _avail_checked, _avail
    if _avail_checked:
        return _avail
    _avail_checked = True
    try:
        import ddddocr  # noqa: F401
        _avail = True
    except Exception:
        _avail = False
    return _avail


def _get_main(log=None):
    global _ocr_main
    if _ocr_main is None:
        try:
            import ddddocr
            _ocr_main = ddddocr.DdddOcr(show_ad=False)
            if log:
                log.info("[抢红包OCR] ddddocr 默认模型初始化成功")
        except Exception as e:  # noqa: BLE001
            if log:
                log.warning("[抢红包OCR] ddddocr 默认模型不可用: %r", e)
            _ocr_main = False
    return _ocr_main or None


def _get_old(log=None):
    global _ocr_old
    if _ocr_old is None:
        try:
            import ddddocr
            _ocr_old = ddddocr.DdddOcr(show_ad=False, old=True)
            if log:
                log.info("[抢红包OCR] ddddocr 旧版模型初始化成功")
        except Exception:  # noqa: BLE001
            _ocr_old = False
    return _ocr_old or None


def _preprocess(img_bytes: bytes, threshold: int = 85) -> bytes:
    """二值化预处理：转灰度 → AutoContrast → 阈值二值化。Pillow 缺失时返回原图。"""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        img = ImageOps.autocontrast(img, cutoff=1)
        bw = img.point(lambda p: 0 if p < threshold else 255, "L")
        out = io.BytesIO()
        bw.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return img_bytes


def clean_code(raw: str) -> str:
    """清洗 OCR 结果：去空白、只留字母数字（验证码字符集为字母+数字）。"""
    if not raw:
        return ""
    return re.sub(r"[^0-9A-Za-z]", "", str(raw)).strip()


def _recognize_sync(img_bytes: bytes, log=None) -> str:
    """同步识别（CPU 密集，应放线程池执行）。返回最长非空清洗结果或空串。"""
    main = _get_main(log)
    if main is None:
        return ""

    candidates: list[str] = []

    def _try(model, data: bytes) -> None:
        try:
            r = model.classification(data)
            r = clean_code(r)
            if r:
                candidates.append(r)
        except Exception:  # noqa: BLE001
            pass

    # 默认模型：原图 + 两档阈值
    _try(main, img_bytes)
    p80 = _preprocess(img_bytes, 80)
    p110 = _preprocess(img_bytes, 110)
    _try(main, p80)
    _try(main, p110)

    # 旧版模型：只用预处理图（与默认模型互补）
    old = _get_old(log)
    if old is not None:
        _try(old, p80)

    return max(candidates, key=len) if candidates else ""


async def recognize(img_bytes: bytes, log=None) -> str:
    """异步识别入口。ddddocr 不可用或无图片字节时返回空串（触发降级）。"""
    if not img_bytes or not ocr_available():
        return ""
    try:
        return await asyncio.to_thread(_recognize_sync, img_bytes, log)
    except Exception as e:  # noqa: BLE001
        if log:
            log.debug("[抢红包OCR] OCR 识别异常: %r", e)
        return ""
