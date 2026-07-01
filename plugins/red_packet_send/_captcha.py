# =============================================================================
# 发红包插件 - 验证码图片生成（防脚本）
#
# 用途：红包不再用「固定口令/贴图」参与（这两者脚本都能秒匹配），改成每次创建时
# 随机生成一张扭曲验证码图片；群友必须肉眼识别并把内容打出来才算参与，杜绝自动脚本。
#
# 纯 PIL 绘制（平台 venv 已装 Pillow，无需额外依赖，见记忆 platform-venv-image-libs）：
#   随机字符（去掉易混淆的 0/O/1/I/L）+ 逐字随机颜色/旋转/上下偏移/重叠
#   + 干扰线 + 噪点，增加 OCR 难度。PIL 缺失时 render_captcha 返回 None，
#   由上层降级为「把验证码当文本口令直接公布」（仍可玩，只是不防脚本）。
# =============================================================================
from __future__ import annotations

import os
import random
import string
import uuid
from typing import Optional

# 去掉易混淆字符：0/O、1/I/L
_CHARSET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# 字体候选（ASCII 字符任意字体都能画，优先粗体更清晰）
_FONT_PATHS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\Arial.ttf",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def generate_code(length: int = 4) -> str:
    """生成随机验证码字符串（去混淆字符集）。"""
    length = max(4, min(8, int(length)))
    return "".join(random.choice(_CHARSET) for _ in range(length))


def _load_font(size: int):
    from PIL import ImageFont
    for p in _FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def render_captcha(code: str, out_dir) -> Optional[str]:
    """把验证码渲染成扭曲图片，返回 PNG 文件路径；PIL 不可用时返回 None。

    每个字符单独渲染到透明小图后随机旋转再贴回，叠加干扰线与噪点。
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:  # noqa: BLE001
        return None

    try:
        n = max(1, len(code))
        char_w = 46
        pad = 18
        W = n * char_w + pad * 2
        H = 84

        # 浅色随机背景
        bg = (random.randint(232, 255), random.randint(232, 255), random.randint(232, 255))
        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)

        # 背景噪点
        for _ in range(int(W * H * 0.04)):
            xy = (random.randint(0, W - 1), random.randint(0, H - 1))
            c = (random.randint(150, 220), random.randint(150, 220), random.randint(150, 220))
            draw.point(xy, fill=c)

        font = _load_font(46)

        # 逐字绘制：随机深色 + 旋转 + 上下偏移 + 轻微重叠
        x = pad
        for ch in code:
            color = (random.randint(0, 110), random.randint(0, 110), random.randint(0, 110))
            layer = Image.new("RGBA", (char_w + 12, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            y = random.randint(6, 22)
            ld.text((random.randint(2, 8), y), ch, font=font, fill=color + (255,))
            angle = random.randint(-32, 32)
            layer = layer.rotate(angle, expand=0, resample=Image.BICUBIC)
            img.paste(layer, (x, 0), layer)
            x += char_w - random.randint(3, 10)

        # 干扰线（画在字上，穿过文本区）
        for _ in range(random.randint(4, 6)):
            lc = (random.randint(60, 180), random.randint(60, 180), random.randint(60, 180))
            draw.line(
                [(random.randint(0, W), random.randint(0, H)),
                 (random.randint(0, W), random.randint(0, H))],
                fill=lc, width=random.randint(1, 2),
            )

        # 干扰弧线
        for _ in range(2):
            x0, y0 = random.randint(0, W // 2), random.randint(0, H)
            x1, y1 = random.randint(W // 2, W), random.randint(0, H)
            bbox = [min(x0, x1), min(y0, y1), max(x0, x1) + 1, max(y0, y1) + 1]
            ac = (random.randint(80, 190), random.randint(80, 190), random.randint(80, 190))
            draw.arc(bbox, random.randint(0, 180), random.randint(180, 360), fill=ac, width=1)

        os.makedirs(str(out_dir), exist_ok=True)
        path = os.path.join(str(out_dir), f"captcha_{uuid.uuid4().hex}.png")
        img.save(path, "PNG")
        return path
    except Exception:  # noqa: BLE001
        return None
