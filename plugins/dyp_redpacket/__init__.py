# =============================================================================
# AWBotNest 插件：癫影积分红包（dyp_redpacket）
#
# 监控「癫影小助手」在癫影积分红包固定群发的积分红包，逐个点击未抢的数字按钮，
# 抢到一格即停（/已抢的、含中文的管理员按钮自动跳过）。
#
# 从原「抢红包(red_packet)」插件拆出独立维护。拼手气红包见 hdsky_redpacket，
# 口令红包见 yingchao_redpacket，三者互不影响。
#
# 注意：本插件用「用户账号」监听并点击红包（scope=user）。发包 bot 与群组按原项目写死。
# =============================================================================
from __future__ import annotations

import asyncio
import time as _time

from . import _ocr
from ._records import Records, parse_keywords, to_float
from ._snatch import classify_packet, extract_text, find_numbered_buttons, is_snatch_success

__plugin__ = {
    "name": "癫影积分红包",
    "id": "dyp_redpacket",
    "version": "1.1.2",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "监控癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过），抢到一格即停。雷包文本防护始终生效；可选OCR识别配图兜底防伪装。发包bot/群组内置写死。",
    "requirements": [
        "rapidocr_onnxruntime>=1.3",  # OCR配图兜底（雷包检测第二层）。缺失时降级为纯文本判定，不影响基础抢包。
    ],
    "config_schema": {
        "dyp_enabled": {
            "type": "boolean", "default": False, "label": "启用癫影积分红包",
            "section": "癫影积分红包",
            "help": "癫影小助手发的积分红包，逐个点击未抢数字按钮（1~9 已抢的跳过）。",
        },
        "dyp_delay": {
            "type": "slider", "default": 0, "label": "点击延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True},
        },
        "dyp_mine_detection": {
            "type": "boolean", "default": True, "label": "雷包OCR兜底",
            "section": "癫影积分红包", "show_if": {"dyp_enabled": True},
            "help": "雷包文本防护始终生效(命中雷包关键词必跳，不受此开关控制)。本开关只控制额外的「OCR识别配图」兜底——防对方把文本洗得和红包一样。开(推荐)：文本认不出时识图再判，仍认不出则保守跳过；关：只靠文本判定。",
        },
        "dyp_mine_keywords": {
            "type": "text", "default": "雷包,不是红包,剩余雷位,踩雷,扣除积分,扣除,雷位,中雷,炸弹",
            "label": "雷包关键词(命中即跳)", "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True},
            "help": "逗号或换行分隔。消息文本或配图文字命中其中任一 → 判定雷包、整包跳过。始终生效(不受OCR兜底开关影响)，优先级最高。",
        },
        "dyp_normal_keywords": {
            "type": "text", "default": "分值,份数,余位,正常奖励,领取积分",
            "label": "正常红包放行词", "section": "癫影积分红包",
            "show_if": {"dyp_enabled": True, "dyp_mine_detection": True},
            "help": "逗号或换行分隔。仅当未命中雷包词、且命中其中任一放行词时才抢。两者都没命中时按「保守跳过」处理。",
        },
        "dyp_mine_failclosed": {
            "type": "boolean", "default": True, "label": "识别不出时保守跳过",
            "section": "癫影积分红包", "show_if": {"dyp_enabled": True, "dyp_mine_detection": True},
            "help": "开(推荐)：既没命中雷包词也没命中放行词时，跳过不抢，避免踩雷。关：识别不出时照常抢(可能踩雷)。",
        },
        "notify_owner": {
            "type": "boolean", "default": True, "label": "抢包结果通知我",
            "section": "通用", "help": "抢到/未抢到时用机器人通知平台主人。",
        },
    },
}

# 按钮点击去重（进程内，TTL 清理）：key = "acct:chat:msg" → 时间戳
_clicked: dict[str, float] = {}
_CLICKED_TTL = 3600

# 发包机器人 / 癫影群（原项目写死，非可配）
_DYP_BOT_ID = 8704462066        # 癫影小助手（积分红包）
_DYP_GROUP_ID = -1003907877852  # 癫影积分红包固定群


def _prune_clicked() -> None:
    now = _time.time()
    for k in [k for k, ts in _clicked.items() if now - ts > _CLICKED_TTL]:
        _clicked.pop(k, None)


def _click_once(client, message) -> bool:
    """点击去重：返回 True 表示首次（可点击），False 表示已点过。"""
    me = getattr(client, "me", None)
    acct_id = me.id if me else id(client)
    key = f"{acct_id}:{message.chat.id}:{message.id}"
    _prune_clicked()
    if key in _clicked:
        return False
    _clicked[key] = _time.time()
    return True


async def setup(ctx):
    records = Records(ctx.kv, ctx.log)

    # ───────── 逐格点击 ─────────
    @ctx.on_message(ctx.filters.group, group=-9)
    async def on_dyp_packet(client, message):
        cfg = ctx.config
        if not cfg.get("dyp_enabled", False):
            return
        fu = message.from_user
        if not (fu and getattr(fu, "is_bot", False) and fu.id == _DYP_BOT_ID):
            return
        if message.chat.id != _DYP_GROUP_ID:
            return
        # 该 bot 在该群只发红包，故匹配「红包」即可（含 积分红包 / 红包 / 雷包文案的「这不是红包」）。
        # 放宽到「红包」是为了让雷包消息也能进入下方检测被显式跳过+通知，而非因不含「积分红包」被静默漏过。
        if "红包" not in extract_text(message):
            return
        if not _click_once(client, message):
            return

        # ───────── 雷包文本防护（始终生效，不受开关控制，等同老版"靠文本排除"）─────────
        mine_kw = parse_keywords(cfg.get("dyp_mine_keywords", ""))
        normal_kw = parse_keywords(cfg.get("dyp_normal_keywords", ""))
        caption = extract_text(message)
        verdict = classify_packet(caption, mine_kw, normal_kw)
        if verdict == "mine":
            ctx.log.info("[癫影积分红包] 文本判定为雷包，跳过 msg=%s", message.id)
            records.add_history({"type": "癫影积分红包", "group_id": message.chat.id, "result": "雷包跳过", "ok": False})
            if cfg.get("notify_owner", True):
                await _notify(ctx, client,
                    f"癫影积分红包-雷包跳过\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{getattr(message,'link','')}",
                    level="warning")
            return

        # ───────── OCR 配图兜底 + 保守跳过（受开关控制，防对方把文本洗得和红包一样）─────────
        # 仅在文本未能确认为正常红包时才动用 OCR（正常红包文本已含放行词，无需识图）。
        if cfg.get("dyp_mine_detection", True) and verdict != "normal":
            img = await _download_image(client, message, ctx.log)
            ocr_text = await _ocr.recognize_text(img, ctx.log) if img else ""
            verdict = classify_packet(f"{caption}\n{ocr_text}", mine_kw, normal_kw)
            if verdict == "mine":
                ctx.log.info("[癫影积分红包] OCR判定为雷包，跳过 msg=%s", message.id)
                records.add_history({"type": "癫影积分红包", "group_id": message.chat.id, "result": "雷包跳过", "ok": False})
                if cfg.get("notify_owner", True):
                    await _notify(ctx, client,
                        f"癫影积分红包-雷包跳过(OCR)\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{getattr(message,'link','')}",
                        level="warning")
                return
            if verdict == "unknown" and cfg.get("dyp_mine_failclosed", True):
                ctx.log.info("[癫影积分红包] 无法确认红包类型(保守跳过) msg=%s caption=%r ocr=%r",
                             message.id, caption[:50], ocr_text[:50])
                records.add_history({"type": "癫影积分红包", "group_id": message.chat.id, "result": "类型不明跳过", "ok": False})
                if cfg.get("notify_owner", True):
                    await _notify(ctx, client,
                        f"癫影积分红包-类型不明跳过(保守)\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n未能确认是否正常红包，已跳过\n\n{getattr(message,'link','')}",
                        level="warning")
                return

        delay = to_float(cfg.get("dyp_delay", 0))
        if delay > 0:
            await asyncio.sleep(delay)

        positions = find_numbered_buttons(message)
        if not positions:
            ctx.log.debug("[癫影积分红包] 无可点按钮 msg=%s", message.id)
            return
        ctx.log.info("[癫影积分红包] 找到 %d 个未抢按钮，逐格尝试", len(positions))

        for idx, (row, col) in enumerate(positions, start=1):
            try:
                result = await message.click(x=col, y=row, timeout=10)
                rtext = getattr(result, "text", None) or getattr(result, "message", None) or ""
                rstr = rtext or str(result)
                ctx.log.info("[癫影积分红包] 第%d格(行%d列%d) 结果=%r", idx, row, col, rstr)
                if is_snatch_success(rstr):
                    records.add_history({"type": "癫影积分红包", "group_id": message.chat.id, "result": rstr, "ok": True})
                    if cfg.get("notify_owner", True):
                        await _notify(ctx, client,
                            f"癫影积分红包-已抢\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n{rstr}\n\n{getattr(message,'link','')}",
                            level="success")
                    return
                await asyncio.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[癫影积分红包] 第%d格点击异常: %r", idx, e)
                await asyncio.sleep(0.3)
        # 全部试完未抢到
        if cfg.get("notify_owner", True):
            await _notify(ctx, client,
                f"癫影积分红包-未抢到\n\n{getattr(message.chat,'title','')} ({message.chat.id})\n\n所有格子均已被抢完",
                level="info")

    ctx.log.info("[癫影积分红包] 已加载")


async def _notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="癫影积分红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def _download_image(client, message, log=None) -> bytes:
    """下载红包配图字节（photo 或 image/* 文档）。失败返回空 bytes。"""
    media = getattr(message, "photo", None)
    if not media:
        doc = getattr(message, "document", None)
        mt = getattr(doc, "mime_type", None) if doc else None
        if doc and mt and mt.startswith("image/"):
            media = doc
    if not media:
        return b""
    try:
        data = await client.download_media(message, in_memory=True)
        if data is None:
            return b""
        if hasattr(data, "getvalue"):
            return data.getvalue()
        if hasattr(data, "getbuffer"):
            return bytes(data.getbuffer())
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
    except Exception as e:  # noqa: BLE001
        if log:
            log.debug("[癫影积分红包] 图片下载失败: %r", e)
    return b""


async def teardown(ctx):
    _clicked.clear()
