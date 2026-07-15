# =============================================================================
# AWBotNest 插件：通用抽奖（common_lottery）
#
# 自动参与 @Lottery8Bot 这类通用抽奖机器人发起的抽奖（任意群可参与，不限站点）：
# 监听抽奖消息 → 解析口令 → 按需自动加入指定群/频道 → 随机等待后发口令参与。
# 与「自动抽奖」(小菜，PT站) 不同：无抽奖ID、参与方式是发整段口令原文、可能要先加群。
#
# 用你的用户账号监听。参与/加群结果用 ctx.notify 推给平台主人。
# =============================================================================

import asyncio
import re
import time as _time
from random import randint

__plugin__ = {
    "name": "通用抽奖",
    "id": "common_lottery",
    "version": "1.0.4",
    "author": "AWdress",
    "description": "自动参与 @Lottery8Bot 等通用抽奖：解析口令、按需自动加群、随机等待后发口令。任意群可用。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "groups": {
            "type": "chat", "default": [], "label": "监听群组", "multi": True,
            "chat_types": ["group", "channel"], "section": "参数",
            "help": "勾选要参与抽奖的群/频道；留空 = 所有群都参与。",
        },
        "auto_join": {
            "type": "boolean", "default": False, "label": "自动加入要求的群/频道",
            "section": "参数", "help": "抽奖要求先加群时，是否自动加入。关闭则遇到加群要求就跳过。",
        },
        "wait_min": {
            "type": "slider", "default": 25, "label": "参与前最短等待(秒)",
            "min": 0, "max": 300, "step": 5, "section": "参数",
        },
        "wait_max": {
            "type": "slider", "default": 65, "label": "参与前最长等待(秒)",
            "min": 5, "max": 600, "step": 5, "section": "参数",
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "参与结果通知我",
            "section": "参数",
        },
    },
}

# 进行中的抽奖：key = "chat_id:message_id"（进程内）
_lottery_list: dict = {}
_added_at: dict = {}
_ENTRY_TTL = 3 * 24 * 3600
_BOT_ID = 6420220651  # @Lottery8Bot（原项目写死）


def _make_key(chat_id, message_id) -> str:
    return f"{chat_id}:{message_id}"


def _prune_stale(log) -> None:
    now = _time.time()
    stale = [k for k, ts in _added_at.items() if now - ts > _ENTRY_TTL]
    for k in stale:
        _lottery_list.pop(k, None)
        _added_at.pop(k, None)
    if stale:
        log.info("[通用抽奖] 清理 %d 个僵尸条目", len(stale))
    for k in [k for k in _added_at if k not in _lottery_list]:
        _added_at.pop(k, None)


def _parse_groups(raw) -> list:
    # chat 控件存 id 数组；兼容旧的逗号/空格分隔字符串
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except (ValueError, TypeError):
                pass
        return out
    groups = []
    for part in re.split(r"[,\s]+", str(raw or "")):
        part = part.strip()
        if not part:
            continue
        try:
            groups.append(int(part))
        except ValueError:
            pass
    return groups


def _group_allowed(cfg, chat_id) -> bool:
    groups = _parse_groups(cfg.get("groups"))
    return (not groups) or (chat_id in groups)


def _wait_range(cfg) -> tuple:
    try:
        wmin = int(cfg.get("wait_min", 25)); wmax = int(cfg.get("wait_max", 65))
    except (ValueError, TypeError):
        wmin, wmax = 25, 65
    return (wmin, wmax) if wmin <= wmax else (wmax, wmin)


def _extract_join_targets(message) -> list:
    """从抽奖消息提取需加入的群/频道（text_link entity 优先，回退正文 t.me）。"""
    targets = []
    for entity in (message.entities or []):
        # 不 import pyrogram，用 entity.type 的字符串名判断 TEXT_LINK
        etype = str(getattr(entity, "type", "")).upper()
        url = getattr(entity, "url", None)
        if "TEXT_LINK" in etype and url:
            url = url.strip()
            if "t.me/" in url and url not in targets:
                targets.append(url)
    text = message.text or message.caption or ""
    for m in re.findall(r"(https?://t\.me/[^\s)]+|t\.me/[^\s)]+)", text):
        m = m.strip()
        if m not in targets:
            targets.append(m)
    return targets


def _normalize_join_arg(link: str):
    """归一化为 join_chat 参数。返回 (arg, is_invite)。"""
    link = link.strip()
    bare = re.sub(r"^https?://", "", link)
    if re.search(r"t\.me/\+", bare) or re.search(r"t\.me/joinchat/", bare):
        return link, True
    m = re.match(r"t\.me/([A-Za-z0-9_]{4,})/?$", bare)
    if m:
        return m.group(1), False
    m = re.match(r"@?([A-Za-z0-9_]{4,})$", link)
    if m:
        return m.group(1), False
    return None, False


async def _check_joined(client, link: str, log) -> bool:
    """只读检测是否已加入（仅公开 username/链接有效）。"""
    arg, is_invite = _normalize_join_arg(link)
    if not arg or is_invite:
        return False
    try:
        member = await client.get_chat_member(arg, "me")
        # 用状态字符串名判断，避免 import ChatMemberStatus
        return str(getattr(member, "status", "")).upper().rsplit(".", 1)[-1] in ("OWNER", "ADMINISTRATOR", "MEMBER")
    except Exception as e:  # noqa: BLE001 - UserNotParticipant 等统一视为未加入
        log.debug("[通用抽奖] 成员查询失败(%s): %s", type(e).__name__, link)
        return False


async def _ensure_joined(client, link: str) -> tuple:
    """尝试加群。返回 (success, detail)。异常按类名判断处理。"""
    arg, _ = _normalize_join_arg(link)
    if not arg:
        return False, f"无法识别的链接: {link}"
    try:
        await client.join_chat(arg)
        return True, f"已加入: {link}"
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__
        if name == "UserAlreadyParticipant":
            return True, f"已在群内: {link}"
        if name == "FloodWait":
            return False, f"触发限流，跳过: {link}"
        if name in ("InviteHashExpired", "InviteHashInvalid"):
            return False, f"邀请链接失效: {link}"
        if name == "UserBannedInChannel":
            return False, f"账号被封禁: {link}"
        if name == "UsernameNotOccupied":
            return False, f"用户名不存在: {link}"
        return False, f"加群失败({name}): {link}"


def _parse_lottery(message) -> dict:
    text = message.text or message.caption or ""
    info = {}
    m = re.search(r"🎁\s*奖品内容[:：]\s*\n?\s*(.+)", text)
    if not m:
        m = re.search(r"🏛️?\s*(.+)", text)
    info["prize"] = m.group(1).strip() if m else ""
    m = re.search(r"🔑\s*抽奖口令[:：]\s*\n?\s*([\s\S]+?)(?:\n\s*[📮🎁💡😊📅]|\Z)", text)
    info["keyword"] = m.group(1).strip() if m else ""
    m = re.search(r"参与人数到达\s*(\d+)", text)
    info["target"] = int(m.group(1)) if m else None
    m = re.search(r"开奖日期.*?\n\s*(.+)", text)
    info["draw_time"] = m.group(1).strip() if m else None
    info["join_targets"] = _extract_join_targets(message)
    return info


async def setup(ctx):
    @ctx.on_message(ctx.filters.text | ctx.filters.caption, group=8)
    async def common_new_lottery(client, message):
        cfg = ctx.config
        text = message.text or message.caption or ""
        fu = message.from_user
        if not (fu and fu.is_bot and fu.id == _BOT_ID):
            return
        # 抽奖消息特征：含口令 + （人数/日期开奖）
        if "🔑" not in text or "抽奖口令" not in text:
            return
        if not ("开奖需要参与人数" in text or "开奖日期" in text):
            return
        if not _group_allowed(cfg, message.chat.id):
            return

        _prune_stale(ctx.log)
        info = _parse_lottery(message)
        if not info["keyword"]:
            ctx.log.warning("[通用抽奖] 未解析出口令，跳过 msg=%s", message.id)
            return

        key = _make_key(message.chat.id, message.id)
        notify = cfg.get("notify_owner", True)

        # 加群处理
        auto_join = bool(cfg.get("auto_join", False))
        join_details = []
        for link in info["join_targets"]:
            if await _check_joined(client, link, ctx.log):
                join_details.append(f"已在群内: {link}")
                continue
            if not auto_join:
                ctx.log.info("[通用抽奖] 需加群但未开自动加群，跳过: %s", link)
                if notify:
                    try:
                        await ctx.notify(f"通用抽奖需手动加群\n\n奖品：{info['prize']}\n\n群链接：{link}\n\n来源：{message.link}",
                                         level="info", category="通用抽奖", account=client)
                    except Exception:
                        pass
                return
            ok, detail = await _ensure_joined(client, link)
            ctx.log.info("[通用抽奖] 加群: %s", detail)
            if not ok:
                if notify:
                    try:
                        await ctx.notify(f"通用抽奖加群失败\n\n奖品：{info['prize']}\n\n详情：{detail}\n\n来源：{message.link}",
                                         level="warning", category="通用抽奖", account=client)
                    except Exception:
                        pass
                return
            join_details.append(detail)
            await asyncio.sleep(randint(2, 5))

        _lottery_list[key] = {"keyword": info["keyword"], "prize": info["prize"],
                              "chat_id": message.chat.id, "target": info["target"],
                              "draw_time": info.get("draw_time"), "won": False}
        _added_at[key] = _time.time()

        wmin, wmax = _wait_range(cfg)
        wait_time = randint(wmin, wmax)
        ctx.log.info("[通用抽奖] %ss 后参与 key=%s", wait_time, key)
        await asyncio.sleep(wait_time)
        if key not in _lottery_list:
            return

        try:
            await client.send_message(message.chat.id, info["keyword"], parse_mode=None)
            ctx.log.info("[通用抽奖] 已发口令参与: %s", key)
            if notify:
                draw = info.get("draw_time") or (f"参与人数到 {info['target']}" if info.get("target") else "")
                join_line = ("加群：" + "; ".join(join_details) + "\n\n") if join_details else ""
                try:
                    await ctx.notify(
                        f"通用抽奖参与成功\n\n奖品：{info['prize']}\n\n群组：{message.chat.title}\n\n{join_line}"
                        f"{('开奖：' + draw + chr(10)*2) if draw else ''}口令：{info['keyword']}\n\n来源：{message.link}",
                        level="success", category="通用抽奖", account=client,
                    )
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[通用抽奖] 发口令失败: %r", e)
            if notify:
                try:
                    await ctx.notify(f"通用抽奖参与失败\n\n奖品：{info['prize']}\n\n原因：{e}\n\n来源：{message.link}",
                                     level="error", category="通用抽奖", account=client)
                except Exception:
                    pass

    @ctx.on_message(ctx.filters.text | ctx.filters.caption, group=9)
    async def common_draw_result(client, message):
        cfg = ctx.config
        text = message.text or message.caption or ""
        fu = message.from_user
        if not (fu and fu.is_bot and fu.id == _BOT_ID):
            return
        if "开奖了" not in text or "本期总参与人数" not in text:
            return
        if not _group_allowed(cfg, message.chat.id):
            return
        # 开奖名单无 TGID，无法判断中奖，仅清理追踪条目
        for k in [k for k, v in _lottery_list.items() if v["chat_id"] == message.chat.id]:
            _lottery_list.pop(k, None)
            _added_at.pop(k, None)


async def teardown(ctx):
    _lottery_list.clear()
    _added_at.clear()
