# =============================================================================
# 癫影积分红包插件 - 配图文字识别（雷包防御层）
#
# 用途：癫影把雷包伪装成红包来骗自动抢包脚本。第一层防御是 caption 文本判定
# （见 _snatch.classify_packet，免费即时）；本模块是第二层——OCR 识别红包「配图」
# 里的大字，防止对方后期把 caption 文本改得和正常红包一样。
#
# 引擎优先级（都为可选依赖，缺失自动降级，不阻止插件加载）：
#   1. RapidOCR(rapidocr 2.x+) —— 中文多行场景文字，识别雷包配图的首选。
#      注意用新包名 `rapidocr`（支持 Python 3.13）；旧包 `rapidocr_onnxruntime`
#      钉死 <3.13 无法在平台(3.13)安装，已弃用。
#   2. ddddocr —— 单行验证码模型，仅作兜底（对场景文字识别率低）。
# 两者都不可用时 recognize_text() 返回空串，由上层 fail-closed 逻辑决定跳过。
# =============================================================================
from __future__ import annotations

import asyncio
import io

# RapidOCR 懒加载单例。None=未初始化；False=不可用；object=可用实例。
_rapid = None
# ddddocr 懒加载单例。
_dddd = None


def _get_rapid(log=None):
    global _rapid
    if _rapid is None:
        try:
            from rapidocr import RapidOCR
            _rapid = RapidOCR()
            if log:
                log.info("[癫影积分红包] RapidOCR 初始化成功")
        except Exception as e:  # noqa: BLE001
            if log:
                log.warning("[癫影积分红包] RapidOCR 不可用: %r", e)
            _rapid = False
    return _rapid or None


def _get_dddd(log=None):
    global _dddd
    if _dddd is None:
        try:
            import ddddocr
            _dddd = ddddocr.DdddOcr(show_ad=False)
        except Exception:  # noqa: BLE001
            _dddd = False
    return _dddd or None


def ocr_available() -> bool:
    """任一 OCR 引擎可 import 即视为可用（只检测 import，不强制初始化）。"""
    try:
        import rapidocr  # noqa: F401
        return True
    except Exception:
        pass
    try:
        import ddddocr  # noqa: F401
        return True
    except Exception:
        return False


def _to_ndarray(img_bytes: bytes):
    """bytes → numpy RGB array（RapidOCR 输入）。失败返回 None。"""
    try:
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return np.array(img)
    except Exception:
        return None


def _recognize_sync(img_bytes: bytes, log=None) -> str:
    """同步识别（CPU 密集，应放线程池）。返回识别到的全部文字拼接串。"""
    # 1) RapidOCR（首选）
    rapid = _get_rapid(log)
    if rapid is not None:
        arr = _to_ndarray(img_bytes)
        if arr is not None:
            try:
                result = rapid(arr)
                # rapidocr 2.x+ 返回 RapidOCROutput 对象，.txts 为字符串元组（可能 None）
                txts = getattr(result, "txts", None)
                if txts:
                    texts = [str(t) for t in txts if t]
                    blob = "".join(texts)
                    if blob.strip():
                        if log:
                            log.debug("[癫影积分红包] RapidOCR 文字=%r", texts)
                        return blob
            except Exception as e:  # noqa: BLE001
                if log:
                    log.debug("[癫影积分红包] RapidOCR 识别异常: %r", e)

    # 2) ddddocr 兜底（识别率低，仅聊胜于无）
    dddd = _get_dddd(log)
    if dddd is not None:
        try:
            r = dddd.classification(img_bytes)
            r = str(r).strip() if r else ""
            if r:
                if log:
                    log.debug("[癫影积分红包] ddddocr 兜底文字=%r", r)
                return r
        except Exception:  # noqa: BLE001
            pass

    return ""


async def recognize_text(img_bytes: bytes, log=None) -> str:
    """异步识别配图全部文字。无图 / 引擎不可用 / 识别失败时返回空串。"""
    if not img_bytes or not ocr_available():
        return ""
    try:
        return await asyncio.to_thread(_recognize_sync, img_bytes, log)
    except Exception as e:  # noqa: BLE001
        if log:
            log.debug("[癫影积分红包] OCR 识别异常: %r", e)
        return ""
