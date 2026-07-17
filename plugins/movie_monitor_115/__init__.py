# =============================================================================
# AWBotNest 插件：115 频道监控（movie_monitor_115）
#
# 通用监控：监听会话里的 115 分享消息，不依赖固定频道格式——
#   1) 优先直接读取消息里写好的「TMDB ID」；
#   2) 读不到再用标题/年份走 TMDB 搜索识别；
#   3) 查 Emby 媒体库，库里没有的把 115 链接转发给 CMS 入库机器人。
# 链接支持多域名（115.com / 115cdn.com …）与「超链接」形式（藏在文字里）。
# 也支持 /getmedia 手动查 TMDB。用你的用户账号监听，参数都在配置里填。
# =============================================================================

import asyncio
import re
from collections import deque
from datetime import datetime

from ._tmdb import TmdbApi, emby_has_tmdb_id, get_emby_tmdb_ids

__plugin__ = {
    "name": "115频道监控",
    "id": "movie_monitor_115",
    "version": "1.0.12",
    "author": "AWdress",
    "description": "通用监控频道里的 115 分享，读取/识别 TMDB 后查 Emby 媒体库，缺失的转发给 CMS 入库机器人。可选电影/电视剧，默认全部。",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": [],
}

# ── 配置默认值 ──
DEFAULTS = {
    "shareswitch": False,
    "monitor_ids": "",
    "media_types": ["movie", "tv"],
    "only_complete_series": False,
    "tmdb_api_key": "",
    "tmdb_language": "zh-CN",
    "emby_url": "",
    "emby_api_key": "",
    "skip_emby_check": False,
    "cms_bot_username": "",
    "forward_label": "115 网盘",
    "forward_to_saved": False,
    "pan115_cookie": "",
}

# ── 运行态 ──
_logs = deque(maxlen=100)

# 115 分享链接
_LINK_PATTERN = re.compile(
    r"https?://(?:[\w-]*115[\w-]*\.com|anxia\.com)/s/[^\s)\]】]+", re.IGNORECASE
)
_TMDB_ID_PATTERN = re.compile(r"TMDB\s*(?:ID)?\s*[:：]\s*(\d+)", re.IGNORECASE)
_COMPLETE_PATTERN = re.compile(r"完结|全\s*\d+\s*[集話话]|全集")
_GETMEDIA_TTL = 30


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _fmt_getmedia(result, title, year, limit=8) -> str:
    yr = year if year and year != "0" else ""
    if not result:
        return f"❌ TMDB 无结果：{title} {yr}".rstrip()
    lines = [f"🔍 {title} {yr}".rstrip() + f"  ·  {len(result)} 条"]
    for it in result[:limit]:
        name = it.get("title") or it.get("name") or "?"
        date = it.get("release_date") or it.get("first_air_date") or ""
        y = date[:4] if date else "----"
        mt = "电影" if it.get("media_type") == "movie" else "剧集"
        vote = it.get("vote_average") or 0
        lines.append(f"• [{mt}] {name} ({y})  id={it.get('id')}  ⭐{vote}")
    if len(result) > limit:
        lines.append(f"… 其余 {len(result) - limit} 条略")
    return "\n".join(lines)


def _lines(raw) -> list[str]:
    return [s.strip() for s in str(raw or "").splitlines() if s.strip()]


def _normalize(raw):
    s = str(raw or "").strip().lower()
    s = re.sub(r"[\s\-_\.]+", "", s)
    return s


def _monitor_ids(cfg) -> list[int]:
    raw = cfg.get("monitor_ids", "")
    if isinstance(raw, list):
        return [int(x) for x in raw if x]
    ids = []
    for tok in re.split(r"[,，\s]+", str(raw or "").strip()):
        if tok:
            try:
                ids.append(int(tok))
            except ValueError:
                pass
    return ids


def _pan115_id(cfg):
    ck = str(cfg.get("pan115_cookie") or "").strip()
    if not ck:
        return None
    try:
        from ._pan115 import Pan115
        return Pan115(ck)
    except Exception:  # noqa: BLE001
        return None


def _msg_text(message) -> str:
    return (message.text or message.caption or "").strip()


def _extract_links(message) -> list[str]:
    text = _msg_text(message)
    found = list(_LINK_PATTERN.finditer(text))
    if found:
        return [m.group(0) for m in found]
    ents = getattr(message, "entities", []) or []
    cap_ents = getattr(message, "caption_entities", []) or []
    links = []
    for e in ents + cap_ents:
        url = getattr(e, "url", None)
        if url and _LINK_PATTERN.match(url):
            links.append(url)
    return links


def _extract_tmdb_id(text: str):
    m = _TMDB_ID_PATTERN.search(text)
    return int(m.group(1)) if m else None


def _guess_type(text: str):
    lower = text.lower()
    if any(k in lower for k in ["电影", "movie", "film"]):
        return "movie"
    if any(k in lower for k in ["剧集", "电视剧", "tv", "series"]):
        return "tv"
    return None


def _extract_title_year(text: str):
    lines = _lines(text)
    if not lines:
        return "", ""
    first = lines[0]
    year_m = re.search(r"\b(19\d{2}|20\d{2})\b", first)
    year = year_m.group(1) if year_m else ""
    title = re.sub(r"\b(19\d{2}|20\d{2})\b", "", first).strip()
    title = re.sub(r"[【\[].*?[】\]]", "", title).strip()
    return title, year


def _parse_pan115(text: str):
    lines = _lines(text)
    if not lines:
        return {}
    code = ""
    m = re.search(r"(?:提取码|访问码|口令|密码)[：:]\s*(\w+)", text, re.IGNORECASE)
    if m:
        code = m.group(1)
    return {"raw": lines[0], "access_code": code}


async def _resolve_target(client, target, ctx):
    if target == "me":
        return "me"
    if target.startswith("@"):
        try:
            chat = await client.get_chat(target)
            return chat.id
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[115监控] 解析转发目标失败 %s: %r", target, e)
            return None
    try:
        return int(target)
    except ValueError:
        return None


async def _send_links(client, cfg, links, label, ctx):
    target = cfg.get("cms_bot_username") or ""
    if cfg.get("forward_to_saved"):
        target = "me"
    if not target:
        return
    tid = await _resolve_target(client, target, ctx)
    if not tid:
        return
    text = f"{label}\n" + "\n".join(links)
    try:
        await client.send_message(tid, text)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[115监控] 转发失败: %r", e)


async def _resolve_by_search(cfg, title, year, ctx):
    if not (cfg.get("tmdb_api_key") and title):
        return None, None
    api = TmdbApi(cfg["tmdb_api_key"], cfg.get("tmdb_language", "zh-CN"))
    try:
        result = await api.multi_search(title, year)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[115监控] TMDB 搜索失败: %r", e)
        return None, None
    if not result:
        return None, None
    first = result[0]
    tmdb_id = first.get("id")
    media_type = first.get("media_type")
    return tmdb_id, media_type


async def _process(client, cfg, message, ctx):
    links = _extract_links(message)
    if not links:
        return
    text = _msg_text(message)
    tmdb_id = _extract_tmdb_id(text)
    media_type = _guess_type(text)

    if not tmdb_id:
        title, year = _extract_title_year(text)
        tmdb_id, guessed_type = await _resolve_by_search(cfg, title, year, ctx)
        if not media_type:
            media_type = guessed_type

    if not tmdb_id:
        ctx.log.info("[115监控] 未识别 TMDB: %s", text[:50])
        _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "title": text[:30], "tmdb_id": None, "action": "跳过"})
        return

    allowed = cfg.get("media_types", ["movie", "tv"])
    if media_type and media_type not in allowed:
        ctx.log.info("[115监控] 跳过类型 %s: %d", media_type, tmdb_id)
        _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "title": text[:30], "tmdb_id": tmdb_id, "action": "跳过"})
        return

    if media_type == "tv" and cfg.get("only_complete_series", False):
        if not _COMPLETE_PATTERN.search(text):
            ctx.log.info("[115监控] 剧集未完结，跳过: %d", tmdb_id)
            _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "title": text[:30], "tmdb_id": tmdb_id, "action": "跳过"})
            return

    if not cfg.get("skip_emby_check", False):
        emby_url = cfg.get("emby_url")
        emby_key = cfg.get("emby_api_key")
        if emby_url and emby_key:
            try:
                has = await emby_has_tmdb_id(emby_url, emby_key, tmdb_id)
                if has:
                    ctx.log.info("[115监控] Emby 已有 %d，跳过", tmdb_id)
                    _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "title": text[:30], "tmdb_id": tmdb_id, "action": "跳过"})
                    return
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[115监控] Emby 查询失败: %r", e)

    label = cfg.get("forward_label", "115 网盘")
    await _send_links(client, cfg, links, label, ctx)
    ctx.log.info("[115监控] 已转发 TMDB %d: %s", tmdb_id, text[:30])
    _logs.append({"time": datetime.now().strftime("%H:%M:%S"), "title": text[:30], "tmdb_id": tmdb_id, "action": "转发"})


async def _cmd_getmedia(client, message, ctx):
    text = message.text or ""
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        return
    query = parts[1]
    year = parts[2] if len(parts) > 2 else ""
    cfg = _effective_cfg(ctx)
    if not cfg.get("tmdb_api_key"):
        return
    api = TmdbApi(cfg["tmdb_api_key"], cfg.get("tmdb_language", "zh-CN"))
    try:
        result = await api.multi_search(query, year)
        summary = _fmt_getmedia(result, query, year)
    except Exception as e:  # noqa: BLE001
        summary = f"❌ 查询失败：{e}"
    try:
        await message.edit(f"```\n{summary}\n```")
    except Exception:
        pass
    await asyncio.sleep(_GETMEDIA_TTL)
    try:
        await message.delete()
    except Exception:
        pass


async def _cmd_find(client, message, ctx):
    text = message.text or ""
    m = re.search(r"/find\s+(\d+)", text, re.IGNORECASE)
    if not m:
        return
    tmdb_id = int(m.group(1))
    cfg = _effective_cfg(ctx)
    emby_url = cfg.get("emby_url")
    emby_key = cfg.get("emby_api_key")
    if not (emby_url and emby_key):
        return
    try:
        has = await emby_has_tmdb_id(emby_url, emby_key, tmdb_id)
        reply = f"✅ Emby 有 TMDB {tmdb_id}" if has else f"❌ Emby 无 TMDB {tmdb_id}"
    except Exception as e:  # noqa: BLE001
        reply = f"❌ 查询失败：{e}"
    try:
        await message.edit(reply)
    except Exception:
        pass
    await asyncio.sleep(_GETMEDIA_TTL)
    try:
        await message.delete()
    except Exception:
        pass


async def setup(ctx):
    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/status", methods=["GET"])
    async def _api_status(req):
        cfg = _effective_cfg(ctx)
        tmdb_ok = bool(cfg.get("tmdb_api_key"))
        emby_ok = bool(cfg.get("emby_url") and cfg.get("emby_api_key"))
        items = 0
        if emby_ok:
            try:
                ids = await get_emby_tmdb_ids(cfg["emby_url"], cfg["emby_api_key"])
                items = len(ids)
            except Exception:  # noqa: BLE001
                pass
        return {
            "tmdb_ok": tmdb_ok,
            "tmdb_status": "已配置" if tmdb_ok else "未配置",
            "emby_ok": emby_ok,
            "emby_status": "连接正常" if emby_ok else "未配置",
            "emby_items": items,
        }

    @ctx.on_api("/test", methods=["POST"])
    async def _api_test(req):
        cfg = _effective_cfg(ctx)
        msgs = []

        if cfg.get("tmdb_api_key"):
            api = TmdbApi(cfg["tmdb_api_key"], cfg.get("tmdb_language", "zh-CN"))
            try:
                await api.multi_search("复仇者联盟", "2012")
                msgs.append("TMDB: ✅")
            except Exception as e:  # noqa: BLE001
                msgs.append(f"TMDB: ❌ {e}")
        else:
            msgs.append("TMDB: 未配置")

        if cfg.get("emby_url") and cfg.get("emby_api_key"):
            try:
                await get_emby_tmdb_ids(cfg["emby_url"], cfg["emby_api_key"])
                msgs.append("Emby: ✅")
            except Exception as e:  # noqa: BLE001
                msgs.append(f"Emby: ❌ {e}")
        else:
            msgs.append("Emby: 未配置")

        ok = all("✅" in m for m in msgs)
        return {"ok": ok, "message": " | ".join(msgs)}

    @ctx.on_api("/logs", methods=["GET"])
    async def _api_logs(req):
        return {"logs": list(_logs)}

    @ctx.on_api("/update_config", methods=["POST"])
    async def _api_update_config(req):
        body = await req.json()
        # shareswitch 从 enabled 推导
        body["shareswitch"] = body.get("shareswitch", True)
        ctx.update_config(body)
        return {"ok": True}

    # ───────── 监听 115 分享消息 ─────────
    @ctx.on_message(ctx.filters.text | ctx.filters.caption, group=7)
    async def monitor_channels(client, message):
        cfg = _effective_cfg(ctx)
        if not cfg.get("shareswitch", False):
            return
        monitor_ids = _monitor_ids(cfg)
        if monitor_ids and message.chat.id not in monitor_ids:
            return
        try:
            await _process(client, cfg, message, ctx)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[115监控] 处理消息异常: %r", e)

    # ───────── 命令：/getmedia 和 /find ─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-9)
    async def commands(client, message):
        text = message.text or ""
        if re.match(r"^[/\.]getmedia(?:\s|$)", text, re.IGNORECASE):
            await _cmd_getmedia(client, message, ctx)
        elif re.match(r"^[/\.]find(?:\s|$)", text, re.IGNORECASE):
            await _cmd_find(client, message, ctx)


async def teardown(ctx):
    pass
