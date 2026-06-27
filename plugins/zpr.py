# =============================================================================
# AWBotNest 插件：P站图片（zpr）
#
# 由 /zpr、/zp（及 .zpr、.zp）命令触发，从 lolicon API 拉取二次元图片发出。
#   /zpr [关键词] [数量] [r18]   —— 以图片形式发送（带遮罩）
#   /zp  [关键词] [数量] [r18]   —— 额外再以原图文件形式发送
# r18: 0=非R18(默认) 1=R18 2=混合
#
# 平台禁止 import pyrogram，故不用 InputMediaPhoto，改为逐张 send_photo；
# 图片先下载到临时目录再发送，发送完清理。
# =============================================================================

import contextlib
import re
import shutil
import tempfile
from pathlib import Path

import httpx

__plugin__ = {
    "name": "P站图片",
    "id": "zpr",
    "version": "1.0.0",
    "author": "AW",
    "description": "发送 /zpr [关键词] [数量] [r18] 获取二次元图片；/zp 同时附带原图文件。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "default_num": {
            "type": "slider", "default": 3, "label": "默认数量", "min": 1, "max": 10, "step": 1,
            "section": "参数", "help": "命令未带数量时取几张。",
        },
        "max_num": {
            "type": "slider", "default": 6, "label": "最大数量", "min": 1, "max": 20, "step": 1,
            "section": "参数", "help": "单次最多取几张（防止刷屏/超时）。",
        },
        "allow_r18": {
            "type": "boolean", "default": False, "label": "允许 R18",
            "section": "参数", "help": "关闭时，命令里的 r18 参数会被强制按 0(非R18) 处理。",
        },
        "spoiler": {
            "type": "boolean", "default": True, "label": "图片加遮罩",
            "section": "参数", "help": "以剧透遮罩形式发送图片，点开才显示。",
        },
    },
}

_API = "https://api.lolicon.app/setu/v2"
_IMG_HOST = "i.pixiv.re"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36 Edg/106.0.1370.42"
    )
}


def _matches(text: str):
    """匹配 /zpr /zp .zpr .zp，返回 (是否命中, 是否原图文件模式)。"""
    m = re.match(r"^[/\.](zp[r]?)(?:\s|$)", text or "", re.IGNORECASE)
    if not m:
        return False, False
    cmd = m.group(1).lower()
    return True, (cmd == "zp")  # zp = 原图文件模式


def _parse_args(text: str):
    """解析 关键词 / 数量 / r18。"""
    parts = (text or "").split()
    tag, number, r18 = "", None, 0
    args = parts[1:]
    if len(args) > 0:
        tag = args[0]
    if len(args) > 1 and args[1].isdigit():
        number = int(args[1])
    if len(args) > 2 and args[2].isdigit() and 0 <= int(args[2]) <= 2:
        r18 = int(args[2])
    return tag, number, r18


async def _fetch_images(tmp_dir: Path, r18: int, num: int, size: str, tag: str, log):
    """请求 API 并把图片下载到 tmp_dir，返回本地文件路径列表。"""
    try:
        async with httpx.AsyncClient() as session:
            resp = await session.get(
                _API, params={"num": num, "r18": r18, "size": size, "tag": tag},
                headers=_HEADERS, timeout=10,
            )
        if resp.status_code != 200:
            log.error("[zpr] API 状态码 %s", resp.status_code)
            return []
        result = resp.json().get("data", [])
    except Exception as e:  # noqa: BLE001
        log.error("[zpr] 请求/解析失败: %r", e)
        return []

    paths = []
    for i, item in enumerate(result):
        url = item.get("urls", {}).get(size, "").replace("i.pixiv.re", _IMG_HOST)
        if not url:
            continue
        file_path = tmp_dir / f"{item.get('pid', i)}_{i}.jpg"
        try:
            async with httpx.AsyncClient() as getter:
                img = await getter.get(url, headers=_HEADERS, timeout=10)
            if img.status_code != 200:
                continue
            file_path.write_bytes(img.content)
            paths.append(file_path)
        except Exception:  # noqa: BLE001
            continue
    return paths


async def setup(ctx):
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-14)
    async def zpr(client, message):
        hit, as_file = _matches(message.text or "")
        if not hit:
            return

        cfg = ctx.config
        tag, number, r18 = _parse_args(message.text or "")
        num = number or int(cfg.get("default_num", 3) or 3)
        num = max(1, min(num, int(cfg.get("max_num", 6) or 6)))
        if not cfg.get("allow_r18", False):
            r18 = 0
        size = "original" if as_file else "regular"
        spoiler = bool(cfg.get("spoiler", True))

        try:
            code_message = await message.edit(".")
        except Exception:
            code_message = message

        tmp_dir = Path(tempfile.mkdtemp(prefix="zpr_"))
        try:
            with contextlib.suppress(Exception):
                await message.edit("..")
            paths = await _fetch_images(tmp_dir, r18, num, size, tag, ctx.log)
            if not paths:
                return await message.edit("出错了，没有纸片人看了。")

            with contextlib.suppress(Exception):
                await message.edit("...")
            reply_to = message.reply_to_message_id
            try:
                for p in paths:
                    await client.send_photo(
                        message.chat.id, str(p),
                        has_spoiler=spoiler, reply_to_message_id=reply_to,
                    )
                if as_file:
                    for p in paths:
                        await client.send_document(
                            message.chat.id, str(p), reply_to_message_id=reply_to,
                        )
            except Exception as e:  # noqa: BLE001
                name = e.__class__.__name__
                if "MEDIA_FORBIDDEN" in str(e).upper() or "Forbidden" in name:
                    return await message.edit("此群组不允许发送媒体。")
                ctx.log.error("[zpr] 发送失败: %r", e)
                return await message.edit(f"发生错误：{name}")

            with contextlib.suppress(Exception):
                await code_message.delete()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def teardown(ctx):
    pass
