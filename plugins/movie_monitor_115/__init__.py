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

from ._tmdb import TmdbApi, emby_has_tmdb_id, get_emby_tmdb_ids

__plugin__ = {
    "name": "115频道监控",
    "id": "movie_monitor_115",
    "version": "1.0.11",
    "author": "AWdress",
    "description": "通用监控频道里的 115 分享，读取/识别 TMDB 后查 Emby 媒体库，缺失的转发给 CMS 入库机器人。可选电影/电视剧，默认全部。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "shareswitch": {
            "type": "boolean", "default": False, "label": "启用自动监控转发",
            "section": "功能开关", "help": "关闭后只监听不转发（/getmedia 手动查仍可用）。",
        },
        # —— 监控范围 ——
        "monitor_ids": {
            "type": "chat", "default": [], "label": "监控频道", "multi": True,
            "chat_types": ["group", "channel"], "section": "监控范围",
            "help": "从你账号的群/频道里勾选要监控的；留空=监控所有会话（凡含 115 链接就处理）。",
        },
        "media_types": {
            "type": "multiselect", "default": ["movie", "tv"], "label": "转存类型",
            "section": "监控范围",
            "options": [
                {"value": "movie", "label": "电影"},
                {"value": "tv", "label": "电视剧"},
            ],
            "help": "选择要转存的媒体类型，默认电影和电视剧全部转存。判定不出类型的消息不受此限制。",
        },
        "only_complete_series": {
            "type": "boolean", "default": False, "label": "剧集仅转存完结",
            "section": "监控范围",
            "help": "开启后电视剧只转存标注了「完结/全X集」的；关闭则不完结也转存。",
        },
        "pan115_chat_id": {
            "type": "chat", "default": 0, "label": "Pan115频道（可选）",
            "chat_types": ["group", "channel"], "section": "监控范围",
            "help": "选中的频道额外用「Pan115」特殊格式解析（按大小判定完结）。不选则统一走通用解析。",
        },
        "blockyword_list": {
            "type": "text", "default": "", "label": "屏蔽关键词",
            "section": "监控范围", "help": "一行一个。消息含这些词则不检索转发。",
        },
        # —— TMDB（无现成 TMDB ID 时用标题识别）——
        "tmdbapi": {
            "type": "password", "default": "", "label": "TMDB API Key / 令牌", "section": "TMDB",
            "help": "填 v3 API Key（32位）或 v4 读取访问令牌（eyJ开头），两种都支持。",
        },
        # —— Emby + CMS ——
        "embyserver": {
            "type": "string", "default": "", "label": "Emby 地址", "section": "Emby/CMS",
            "help": "形如 http://host:8096/ （结尾带斜杠）。",
        },
        "embyapi": {
            "type": "password", "default": "", "label": "Emby API Key", "section": "Emby/CMS",
        },
        "cmsbot": {
            "type": "string", "default": "", "label": "CMS 入库机器人", "section": "Emby/CMS",
            "help": "把缺失媒体的 115 链接发给这个机器人。填 @用户名 或数字ID；"
                    "@用户名会自动解析，若报 PeerIdInvalid 解析失败请改用数字ID。",
        },
    },
}

# 115 分享链接：兼容 115.com / 115cdn.com / 115vod.com / anxia.com 等
_LINK_PATTERN = re.compile(
    r"https?://(?:[\w-]*115[\w-]*\.com|anxia\.com)/s/[^\s)\]】]+", re.IGNORECASE
)
# 消息里写好的 TMDB ID，如「TMDB ID：260463」「TMDB：286506」
_TMDB_ID_PATTERN = re.compile(r"TMDB\s*(?:ID)?\s*[:：]\s*(\d+)", re.IGNORECASE)
# 完结标记
_COMPLETE_PATTERN = re.compile(r"完结|全\s*\d+\s*[集話话]|全集")
# /getmedia 结果消息自动删除秒数
_GETMEDIA_TTL = 30


def _fmt_getmedia(result, title, year, limit=8) -> str:
    """把 TMDB 查询结果格式化成简短摘要。"""
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
    return [x.strip() for x in str(raw or "").splitlines() if x.strip()]


def _normalize(raw):
    s = str(raw or "").strip()
    if not s:
        return None
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except ValueError:
        return None


def _monitor_ids(cfg) -> list[int]:
    """监控会话 id 列表；空表示不限会话（监控全部）。兼容 chat 控件的 id 数组与旧的多行字符串。"""
    raw = cfg.get("monitor_ids") or []
    items = raw if isinstance(raw, list) else _lines(raw)
    ids = []
    for x in items:
        try:
            ids.append(int(x))
        except (ValueError, TypeError):
            pass
    return ids


def _pan115_id(cfg):
    """chat 控件存单个 id（0=未选）；兼容旧的 @用户名/字符串。"""
    raw = cfg.get("pan115_chat_id")
    try:
        return int(raw) or None
    except (ValueError, TypeError):
        return _normalize(raw)


def _msg_text(message) -> str:
    return message.caption or message.text or ""


def _extract_links(message) -> list[str]:
    """提取消息里的 115 链接：明文 + 超链接（text_link entity 的 url）。"""
    links = list(_LINK_PATTERN.findall(_msg_text(message)))
    entities = message.caption_entities or message.entities or []
    for ent in entities:
        url = getattr(ent, "url", None)
        if url and _LINK_PATTERN.search(url):
            links.append(url)
    # 去重保序
    seen, out = set(), []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _extract_tmdb_id(text: str):
    m = _TMDB_ID_PATTERN.search(text)
    return m.group(1) if m else None


def _guess_type(text: str):
    """从文案判定媒体类型；判不定返回 None。"""
    if re.search(r"电视剧|剧集|连续剧|美剧|日剧|韩剧|国剧|港剧|台剧|番剧|综艺", text):
        return "tv"
    if re.search(r"电影|影片", text):
        return "movie"
    return None


def _extract_title_year(text: str):
    """通用提取「名称 (年份)」，自动去掉「电视剧：」「[剧集]」等前缀。"""
    for line in text.splitlines()[:6]:
        m = re.search(r"(.+?)\s*[（(](\d{4})[)）]", line)
        if not m:
            continue
        raw = m.group(1)
        raw = re.sub(r"^\s*[\[【][^\]】]*[\]】]\s*", "", raw)  # 去 [剧集] 【x】
        raw = re.sub(r"^\s*(?:电视剧|电影|剧集|连续剧|影片|动漫|番剧|综艺|剧)\s*[:：]?\s*", "", raw)
        raw = raw.strip(" ：:-·|·")
        if raw:
            return raw, m.group(2)
    return "", ""


def _parse_pan115(text: str):
    """Pan115 特殊格式：按大小判定完结。返回 (title, year, complete)。"""
    pat = r"[】](.*?)\s*\((\d+)\)" if "】" in text else r"[:] (.*?)\s*\((\d+)\)"
    ty = re.search(pat, text)
    title = year = ""
    complete = False
    if ty:
        title, year = ty.group(1).strip(), ty.group(2).strip()
    size = re.search(r"大\s*小[：:]\s*([\d.]+)\s*([TGM])", text)
    if size:
        unit_map = {"M": 1, "G": 1024, "T": 1024 ** 2}
        size_mb = float(size.group(1)) * unit_map[size.group(2)]
        complete = size_mb >= 10240 and "第" not in text
    return title, year, complete


async def _resolve_target(client, target, ctx):
    """@用户名 先 get_chat 解析一次写入会话缓存，规避 PeerIdInvalid；返回可用的 peer。"""
    if isinstance(target, str) and target.startswith("@"):
        try:
            chat = await client.get_chat(target)
            return chat.id
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("[115监控] 解析 %s 失败（建议改用数字ID）: %r", target, e)
    return target


async def _send_links(client, cfg, links, label, ctx):
    cmsbot = _normalize(cfg.get("cmsbot"))
    if cmsbot is None:
        ctx.log.warning("[115监控] 未配置 CMS 机器人，跳过发送 | %s", label)
        return
    cmsbot = await _resolve_target(client, cmsbot, ctx)
    for link in links:
        try:
            await client.send_message(cmsbot, link)
            ctx.log.info("[115监控] 已发送 [%s]: %s", label, link)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[115监控] 发送链接失败: %r", e)


async def _resolve_by_search(cfg, title, year, ctx):
    """无现成 TMDB ID 时，用标题/年份走 TMDB 搜索识别。返回 (media_type, tmdb_id) 或 None。"""
    tmdb = TmdbApi(cfg.get("tmdbapi", ""))
    results = await tmdb.search_all(title, year, ctx.log)
    if not results:
        return None
    idx = next(
        (i for i, it in enumerate(results)
         if (it.get("title") == title or it.get("name") == title)
         and ((it.get("release_date") or it.get("first_air_date") or "")[:4] == str(year))),
        next((i for i, it in enumerate(results)
              if it.get("title") == title or it.get("name") == title), 0),
    )
    media = results[idx]
    return media.get("media_type", ""), media.get("id", "")


async def _process(client, cfg, message, ctx):
    text = _msg_text(message)
    links = _extract_links(message)
    if not links:
        return

    block_words = _lines(cfg.get("blockyword_list", ""))
    if block_words and any(w in text for w in block_words):
        ctx.log.info("[115监控] 命中屏蔽词，跳过")
        return

    media_types = cfg.get("media_types") or ["movie", "tv"]
    tmdb_id = _extract_tmdb_id(text)
    mtype = _guess_type(text)
    title, year = _extract_title_year(text)
    complete = bool(_COMPLETE_PATTERN.search(text))

    pan = _pan115_id(cfg)
    if pan is not None and message.chat.id == pan:
        t2, y2, c2 = _parse_pan115(text)
        if t2:
            title, year = t2, y2
        complete = complete or c2

    label = title or (f"tmdb:{tmdb_id}" if tmdb_id else "?")

    # 类型过滤：能判定就按选择过滤；判不定不拦
    if mtype and mtype not in media_types:
        ctx.log.info("[115监控] 类型 %s 未选中，跳过 | %s", mtype, label)
        return
    # 完结过滤：仅当明确是剧集且开启了「仅完结」
    if mtype == "tv" and cfg.get("only_complete_series", False) and not complete:
        ctx.log.info("[115监控] 剧集未完结（仅转完结已开启），跳过 | %s", label)
        return

    embyserver = cfg.get("embyserver", "")
    embyapi = cfg.get("embyapi", "")
    emby_configured = bool(embyserver and embyapi)
    chat_title = getattr(message.chat, "title", None) or ""

    try:
        if tmdb_id:
            in_library = await emby_has_tmdb_id(embyserver, embyapi, tmdb_id, mtype, ctx.log)
            ctx.log.info("[115监控] TMDB=%s type=%s 库内=%s | [%s] %s",
                         tmdb_id, mtype or "?", in_library, chat_title, label)
        elif title:
            found = await _resolve_by_search(cfg, title, year, ctx)
            if not found:
                ctx.log.info("[115监控] TMDB 无结果 | %s %s", title, year)
                return
            mtype2, tid = found
            if mtype2 and mtype2 not in media_types:
                ctx.log.info("[115监控] 类型 %s 未选中(搜索)，跳过 | %s", mtype2, title)
                return
            ids = await get_emby_tmdb_ids(embyserver, embyapi, title, mtype2, ctx.log)
            in_library = bool(ids and str(tid) in ids)
            ctx.log.info("[115监控] 搜索匹配 TMDB=%s type=%s 库内=%s | %s",
                         tid, mtype2 or "?", in_library, title)
        else:
            ctx.log.info("[115监控] 无法识别标题/TMDB，跳过 | chat=%s", message.chat.id)
            return
    except Exception as e:  # noqa: BLE001
        # 只有「配置了 Emby 但查询失败」才保守跳过：无法确认是否已入库时，
        # 宁可漏转也不误转（避免库里已有的被重复推送入库）。
        if emby_configured:
            ctx.log.error("[115监控] 查 Emby 失败，跳过转发避免误入库 | %s: %r", label, e)
            return
        raise

    if in_library:
        ctx.log.info("[115监控] 已在媒体库，不转存 | %s", label)
        return
    await _send_links(client, cfg, links, label, ctx)


async def _cmd_getmedia(client, message, ctx):
    text = message.text or ""
    cfg = ctx.config
    parts = text.split()
    title = parts[1] if len(parts) >= 2 else ""
    year = parts[2] if len(parts) >= 3 else "0"
    if not title:
        return await message.edit("请提供名称，例如：.getmedia 泰坦尼克号 1997")

    await message.edit(f"🔍 查询 TMDB：{title} {year if year != '0' else ''}".rstrip() + " …")
    try:
        tmdb = TmdbApi(cfg.get("tmdbapi", ""))
        result = await tmdb.search_all(title, year, ctx.log)
        summary = _fmt_getmedia(result, title, year)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[115监控] .getmedia 失败: %r", e)
        summary = f"查询失败: {e.__class__.__name__}"

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
    kw = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) >= 2 else ""
    if not kw:
        return await message.edit("请提供关键词，例如：.find 泰坦尼克号")
    cfg = ctx.config
    monitor_ids = _monitor_ids(cfg)
    if not monitor_ids:
        return await message.edit(
            "「监控频道ID」为空（留空=监控全部会话），无法遍历搜索。\n"
            "请在配置里填入要搜索的频道ID后再用 .find。"
        )

    await message.edit(f"🔎 搜索「{kw}」…")
    found = []  # (频道名, 摘要, 链接)
    for cid in monitor_ids:
        try:
            async for msg in client.search_messages(cid, query=kw, limit=10):
                links = _extract_links(msg)
                if not links:
                    continue
                ct = getattr(msg.chat, "title", None) or str(cid)
                body = (msg.caption or msg.text or "").strip()
                snippet = body.splitlines()[0][:40] if body else ""
                for link in links:
                    found.append((ct, snippet, link))
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("[115监控] 搜索频道 %s 失败: %r", cid, e)
        if len(found) >= 15:
            break

    if not found:
        summary = f"🔎「{kw}」未找到 115 资源"
    else:
        lines = [f"🔎「{kw}」· 命中 {len(found)} 条"]
        for ct, snippet, link in found[:15]:
            lines.append(f"[{ct}] {snippet}\n{link}")
        summary = "\n".join(lines)

    try:
        await message.edit(f"```\n{summary}\n```")
    except Exception:
        pass
    await asyncio.sleep(_GETMEDIA_TTL)
    try:
        await message.delete()
    except Exception:
        pass


async def setup(ctx):
    @ctx.on_message(ctx.filters.text | ctx.filters.caption, group=7)
    async def monitor_channels(client, message):
        cfg = ctx.config
        if not cfg.get("shareswitch", False):
            return
        monitor_ids = _monitor_ids(cfg)
        # 留空=监控全部会话；填了=白名单
        if monitor_ids and message.chat.id not in monitor_ids:
            return
        try:
            await _process(client, cfg, message, ctx)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[115监控] 处理消息异常: %r", e)

    # 单一命令分发：getmedia 与 find 共用 outgoing&text 过滤器，必须放同一个
    # handler 内分发——否则同 group 内先匹配的 handler 执行后会停止传播，
    # 导致另一个命令永远收不到。
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-9)
    async def commands(client, message):
        text = message.text or ""
        if re.match(r"^[/\.]getmedia(?:\s|$)", text, re.IGNORECASE):
            await _cmd_getmedia(client, message, ctx)
        elif re.match(r"^[/\.]find(?:\s|$)", text, re.IGNORECASE):
            await _cmd_find(client, message, ctx)


async def teardown(ctx):
    pass
