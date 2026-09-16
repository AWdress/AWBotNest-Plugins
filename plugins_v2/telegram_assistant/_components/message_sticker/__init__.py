"""Render a replied Telegram message as a native static sticker."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any

from telethon import types


__plugin__ = {
    "id": "message_sticker",
    "name": "消息贴图",
    "version": "1.0.0",
    "author": "AWdress",
    "scope": "user",
    "plugin_api_version": 2,
    "requirements": ["Pillow>=10.0"],
    "render_mode": "schema",
    "description": "把被回复消息的头像、昵称和正文生成 Telegram 原生贴纸。",
    "config_schema": {
        "command": {"type": "string", "default": ".贴图", "label": "触发命令"},
        "delete_command": {"type": "boolean", "default": True, "label": "成功后删除命令"},
    },
}


_NAME_COLORS = (
    (255, 103, 201, 255),
    (99, 208, 255, 255),
    (130, 226, 168, 255),
    (255, 189, 92, 255),
    (190, 145, 255, 255),
)
_FONT_ROOTS = (
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/truetype/wqy"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/System/Library/Fonts"),
)


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    names = (
        ("msyhbd.ttc", "NotoSansCJK-Bold.ttc", "wqy-microhei.ttc", "DejaVuSans-Bold.ttf")
        if bold
        else ("msyh.ttc", "NotoSansCJK-Regular.ttc", "wqy-microhei.ttc", "DejaVuSans.ttf")
    )
    for root in _FONT_ROOTS:
        for name in names:
            path = root / name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_width(draw, text: str, font) -> float:
    try:
        return float(draw.textlength(text, font=font))
    except AttributeError:
        left, _, right, _ = draw.textbbox((0, 0), text, font=font)
        return float(right - left)


def _fit_line(draw, text: str, font, width: int) -> str:
    value = str(text or "").strip()
    if _text_width(draw, value, font) <= width:
        return value
    suffix = "…"
    while value and _text_width(draw, value + suffix, font) > width:
        value = value[:-1]
    return (value + suffix) if value else suffix


def _wrap(draw, text: str, font, width: int, max_lines: int = 9) -> list[str]:
    lines: list[str] = []
    paragraphs = str(text or "").replace("\r", "").split("\n")
    overflow = False
    for paragraph_index, paragraph in enumerate(paragraphs):
        paragraph = re.sub(r"[\t ]+", " ", paragraph).strip()
        if not paragraph:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and _text_width(draw, candidate, font) > width:
                lines.append(current.rstrip())
                current = char.lstrip()
                if len(lines) >= max_lines:
                    overflow = True
                    break
            else:
                current = candidate
        if overflow:
            break
        if current or not lines:
            lines.append(current.rstrip())
        if len(lines) >= max_lines and paragraph_index < len(paragraphs) - 1:
            overflow = True
            break
    lines = lines[:max_lines] or ["…"]
    if overflow:
        lines[-1] = _fit_line(draw, lines[-1].rstrip("…") + "…", font, width)
    return lines


def _placeholder(source: Any) -> str:
    for attribute, label in (
        ("photo", "[图片]"), ("sticker", "[贴纸]"), ("video", "[视频]"),
        ("voice", "[语音]"), ("audio", "[音频]"), ("document", "[文件]"),
    ):
        if getattr(source, attribute, None):
            return label
    return "[消息]"


def _display_name(sender: Any, sender_id: Any) -> str:
    title = str(getattr(sender, "title", "") or "").strip()
    if title:
        return title
    first_name = str(getattr(sender, "first_name", "") or "").strip()
    last_name = str(getattr(sender, "last_name", "") or "").strip()
    # The timed-nickname module normally writes a clock/weather string into
    # last_name. Keep ordinary last names while excluding that generated suffix.
    normalized_last_name = unicodedata.normalize("NFKC", last_name)
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?(?:\s+.*)?", normalized_last_name):
        last_name = ""
    full_name = " ".join(part for part in (first_name, last_name) if part)
    if full_name:
        return full_name
    username = str(getattr(sender, "username", "") or "").strip()
    return f"@{username}" if username else str(sender_id or "Telegram")


def _initial(name: str) -> str:
    for char in str(name or ""):
        if char.isalnum() or ord(char) > 127:
            return char.upper()
    return "T"


def render_sticker(avatar: bytes | None, name: str, text: str, sender_key: Any = "") -> BytesIO:
    """Return a Telegram-compatible 512px WebP sticker stream."""
    from PIL import Image, ImageDraw, ImageOps

    width = 512
    outer = 12
    avatar_size = 94
    gap = 14
    bubble_x = outer + avatar_size + gap
    bubble_width = width - bubble_x - outer
    inset = 20
    name_font = _font(30, bold=True)
    probe = Image.new("RGBA", (width, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    body_font = _font(30)
    body_width = bubble_width - inset * 2
    lines = _wrap(draw, text, body_font, body_width)
    line_height = max(34, int(body_font.size * 1.22)) if hasattr(body_font, "size") else 36
    name_height = max(34, draw.textbbox((0, 0), "Ag南", font=name_font)[3])
    bubble_height = inset + name_height + 9 + line_height * len(lines) + inset
    height = max(138, min(512, max(bubble_height + outer * 2, avatar_size + outer * 2)))

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    bubble_bottom = min(height - outer, outer + bubble_height)
    draw.rounded_rectangle(
        (bubble_x, outer, width - outer, bubble_bottom),
        radius=34,
        fill=(28, 21, 39, 248),
        outline=(255, 255, 255, 24),
        width=1,
    )

    digest = hashlib.sha256(str(sender_key or name).encode("utf-8", "ignore")).digest()
    name_color = _NAME_COLORS[digest[0] % len(_NAME_COLORS)]
    avatar_bg = _NAME_COLORS[digest[1] % len(_NAME_COLORS)]
    avatar_box = (outer, outer + 6, outer + avatar_size, outer + 6 + avatar_size)
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
    avatar_image = None
    if avatar:
        try:
            avatar_image = Image.open(BytesIO(avatar)).convert("RGB")
            avatar_image = ImageOps.fit(avatar_image, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS)
        except Exception:
            avatar_image = None
    if avatar_image is not None:
        image.paste(avatar_image.convert("RGBA"), avatar_box[:2], mask)
    else:
        draw.ellipse(avatar_box, fill=avatar_bg)
        letter = _initial(name)
        initial_font = _font(44, bold=True)
        bounds = draw.textbbox((0, 0), letter, font=initial_font)
        tx = avatar_box[0] + (avatar_size - (bounds[2] - bounds[0])) / 2
        ty = avatar_box[1] + (avatar_size - (bounds[3] - bounds[1])) / 2 - bounds[1]
        draw.text((tx, ty), letter, font=initial_font, fill=(255, 255, 255, 255))
    name_text = _fit_line(draw, name, name_font, body_width)
    text_x = bubble_x + inset
    text_y = outer + inset - 3
    draw.text((text_x, text_y), name_text, font=name_font, fill=name_color)
    body_y = text_y + name_height + 9
    for line in lines:
        draw.text((text_x, body_y), line, font=body_font, fill=(250, 249, 252, 255))
        body_y += line_height

    output = BytesIO()
    image.save(output, format="WEBP", lossless=True, method=6)
    if output.tell() > 500 * 1024:
        output = BytesIO()
        image.save(output, format="WEBP", quality=88, method=6)
    output.seek(0)
    output.name = "message-sticker.webp"
    output.width = width
    output.height = height
    return output


def _command_args(text: str, configured: Any) -> str | None:
    bare = str(configured or ".贴图").strip().lstrip("/.") or "贴图"
    parts = str(text or "").strip().split(maxsplit=1)
    if not parts or parts[0].lower() not in {f".{bare}".lower(), f"/{bare}".lower()}:
        return None
    return parts[1].strip() if len(parts) > 1 else ""


async def _avatar_bytes(client, sender: Any) -> bytes | None:
    if sender is None:
        return None
    try:
        value = await client.download_profile_photo(sender, file=bytes, download_big=False)
        return bytes(value) if value else None
    except Exception:
        return None


async def setup(ctx):
    @ctx.on_message(incoming=False, outgoing=True)
    async def make_sticker(event):
        override = _command_args(event.raw_text or "", ctx.config.get("command", ".贴图"))
        if override is None:
            return
        source = await event.get_reply_message()
        if source is None:
            await event.edit("请先回复一条要生成贴图的消息")
            return
        try:
            sender = await source.get_sender()
            sender_id = getattr(source, "sender_id", None)
            name = _display_name(sender, sender_id)
            text = override or str(getattr(source, "raw_text", "") or "").strip() or _placeholder(source)
            sticker = render_sticker(await _avatar_bytes(event.client, sender), name, text, sender_id)
            attributes = [
                types.DocumentAttributeFilename(file_name="message-sticker.webp"),
                types.DocumentAttributeImageSize(w=sticker.width, h=sticker.height),
                types.DocumentAttributeSticker(alt="💬", stickerset=types.InputStickerSetEmpty()),
            ]
            await event.client.send_file(
                event.chat_id,
                sticker,
                mime_type="image/webp",
                attributes=attributes,
                force_document=False,
                allow_cache=False,
            )
            if ctx.config.get("delete_command", True):
                try:
                    await event.delete()
                except Exception as error:
                    ctx.log.debug("[消息贴图] 删除命令失败: %r", error)
            else:
                await event.edit("贴图已发送 ✓")
        except Exception as error:
            ctx.log.error("[消息贴图] 生成或发送失败: %r", error)
            await event.edit(f"贴图发送失败：{type(error).__name__}")


async def teardown(ctx):
    ctx.log.info("[消息贴图] 已停用")
