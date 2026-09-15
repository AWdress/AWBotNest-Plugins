"""Deterministic Emby genre/tag cover renderer (no AI or network calls)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Keep the plugin loadable while the host installs requirements.
    Image = ImageDraw = ImageFont = None


SIZE = 1024
_PALETTES = {
    'genre': ((13, 25, 48), (32, 88, 122), (92, 211, 188)),
    'tag': ((28, 18, 47), (92, 45, 103), (238, 176, 92)),
}


def _font(size: int, bold: bool = False):
    if ImageFont is None:
        raise RuntimeError('分类封面需要 Pillow 依赖，请先完成插件依赖安装')
    names = (
        'msyhbd.ttc', 'msyh.ttc', 'simhei.ttf',
        'NotoSansCJK-Bold.ttc', 'NotoSansCJK-Regular.ttc',
        'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',
    )
    roots = [Path('C:/Windows/Fonts'), Path('/usr/share/fonts/opentype/noto'), Path('/usr/share/fonts/truetype/dejavu')]
    for root in roots:
        for name in names:
            path = root / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    pass
    return ImageFont.load_default()


def _gradient(draw: ImageDraw.ImageDraw, start: Tuple[int, int, int], end: Tuple[int, int, int]) -> None:
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(round(start[i] * (1 - ratio) + end[i] * ratio) for i in range(3))
        draw.line((0, y, SIZE, y), fill=color)


def render_cover(title: str, kind: str = 'genre') -> bytes:
    """Render a square cover with exact text and return PNG bytes."""
    if Image is None or ImageDraw is None:
        raise RuntimeError('分类封面需要 Pillow 依赖，请先完成插件依赖安装')
    title = str(title or '').strip() or '未命名'
    start, end, accent = _PALETTES.get(kind, _PALETTES['genre'])
    image = Image.new('RGB', (SIZE, SIZE), start)
    draw = ImageDraw.Draw(image, 'RGBA')
    _gradient(draw, start, end)

    # Layered geometric motif keeps cards recognizable without using posters.
    draw.ellipse((-260, -220, 760, 800), fill=(*accent, 30), outline=(*accent, 120), width=3)
    draw.ellipse((390, 390, 1280, 1280), fill=(*accent, 18), outline=(*accent, 90), width=4)
    draw.rounded_rectangle((72, 72, 952, 952), radius=34, outline=(255, 255, 255, 55), width=2)
    for offset in (0, 1, 2):
        draw.line((130 + offset * 14, 835, 420 + offset * 14, 545), fill=(*accent, 90), width=5)

    label_font = _font(28, bold=True)
    title_size = 92 if len(title) <= 5 else 68 if len(title) <= 8 else 52
    title_font = _font(title_size, bold=True)
    small_font = _font(24)
    label = 'GENRE' if kind == 'genre' else 'TAG'
    draw.text((112, 126), label, font=label_font, fill=(*accent, 235), spacing=4)
    # Keep long user-created tags readable instead of letting text run out of
    # the card.  Reduce the font first, then wrap by measured pixel width.
    max_width = 780
    while title_size > 30 and (draw.textbbox((0, 0), title, font=title_font)[2] > max_width):
        title_size -= 4
        title_font = _font(title_size, bold=True)
    if draw.textbbox((0, 0), title, font=title_font)[2] > max_width:
        lines, current = [], ''
        for char in title:
            candidate = current + char
            if current and draw.textbbox((0, 0), candidate, font=title_font)[2] > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        title = '\n'.join(lines)
    bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=10, align='center')
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (SIZE - text_w) // 2
    y = 430 - text_h // 2
    # Subtle shadow improves readability on Emby dark cards.
    draw.multiline_text((x + 4, y + 6), title, font=title_font, fill=(0, 0, 0, 130), spacing=10, align='center')
    draw.multiline_text((x, y), title, font=title_font, fill=(255, 255, 255, 245), spacing=10, align='center')
    draw.text((112, 866), 'AW MEDIA COLLECTION', font=small_font, fill=(255, 255, 255, 150))

    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()
