# =============================================================================
# AWBotNest 插件：影巢答题红包（hdhive_quiz）
#
# 影巢机器人在群里发「答题红包」：消息带一道题（单选 4 项 / 判断 对错），
# 答对即可参与。本插件用你的【用户账号】监听，自动作答：
#   1. 题库命中：从社区题库仓库（默认 my-name-is-alan/hdhive-red-questions）
#      同步的题目里查到答案，回复对应答案文本。
#   2. 题库未命中：可选调大模型（OpenAI 兼容接口）作答（用户要求的兜底方案）。
#
# 作答方式为「回复文字答案」（reply_to 红包消息发送答案文本）。回复内容格式可配。
#
# 注意：scope=user，会以你的账号在群里发消息，请仅在可信群启用。发包 bot/群组
# 可配（留空=监听所有群里所有 bot 的答题红包），建议按需限定，避免误答。
#
# 消息格式无法从代码/网络推定，解析力求鲁棒并打日志；若真实红包格式特殊导致
# 解析/作答不准，用 getmsg 抓一条原文对照微调 _quiz.py 的解析或调整回复格式。
# =============================================================================
from __future__ import annotations

import asyncio
import re
import time as _time

from . import _engine
from ._bank import Bank
from ._quiz import (
    QUIZ_MARKERS, sanitize, parse_quiz, resolve_bank_answer,
    match_live_option, option_by_letter, build_reply,
)

__plugin__ = {
    "name": "影巢答题红包",
    "id": "hdhive_quiz",
    "version": "1.0.0",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "description": "自动回答影巢机器人发的答题红包：从社区题库查答案回复，题库没有时可选大模型兜底作答。发包bot/群组可配。",
    "requirements": ["openai>=1.0"],
    "config_schema": {
        # —— 作答 ——
        "enabled": {
            "type": "boolean", "default": False, "label": "启用自动答题",
            "section": "作答",
            "help": "监听答题红包并自动回复答案。scope=user，用你的账号在群里发送答案。",
        },
        "listen_groups": {
            "type": "string", "default": "", "label": "监听群组ID",
            "section": "作答", "show_if": {"enabled": True},
            "help": "英文逗号分隔的群组ID，留空 = 所有群。建议按需限定。",
        },
        "bot_ids": {
            "type": "string", "default": "", "label": "发包机器人ID",
            "section": "作答", "show_if": {"enabled": True},
            "help": "英文逗号分隔的机器人用户ID，只答这些 bot 发的题。留空 = 群里任意 bot。",
        },
        "answer_delay": {
            "type": "slider", "default": 3, "label": "作答延迟(秒)",
            "min": 0, "max": 60, "step": 1, "section": "作答",
            "show_if": {"enabled": True},
            "help": "解析出答案后等待多少秒再回复，避免秒回显得像脚本。",
        },
        "reply_format": {
            "type": "select", "default": "content", "label": "回复格式",
            "section": "作答", "show_if": {"enabled": True},
            "options": [
                {"value": "content", "label": "选项原文（如：蜜蜂）"},
                {"value": "letter", "label": "选项字母（如：A）"},
                {"value": "full", "label": "字母+原文（如：A. 蜜蜂）"},
            ],
            "help": "回复答案的文本形式。判断题固定回复 对/错。不确定就先用「选项原文」。",
        },
        # —— 大模型兜底 ——
        "llm_enabled": {
            "type": "boolean", "default": False, "label": "题库未命中时用大模型兜底",
            "section": "大模型兜底",
            "help": "题库里没有的题，调 OpenAI 兼容接口让大模型选答案。需配置下方接口。",
        },
        "llm_api_key": {
            "type": "password", "default": "", "label": "API Key",
            "section": "大模型兜底", "show_if": {"llm_enabled": True},
        },
        "llm_base_url": {
            "type": "string", "default": "", "label": "接口地址(Base URL)",
            "section": "大模型兜底", "show_if": {"llm_enabled": True},
            "help": "OpenAI 兼容接口地址，如 https://api.openai.com/v1。留空用官方默认。",
        },
        "llm_model": {
            "type": "string", "default": "gpt-4o-mini", "label": "模型",
            "section": "大模型兜底", "show_if": {"llm_enabled": True},
        },
        # —— 题库 ——
        "bank_repo": {
            "type": "string",
            "default": "https://github.com/my-name-is-alan/hdhive-red-questions",
            "label": "题库仓库地址", "section": "题库",
            "help": "GitHub 仓库地址，从中拉取 questions/ 下所有 *.json。",
        },
        "bank_branch": {
            "type": "string", "default": "main", "label": "分支",
            "section": "题库",
        },
        "bank_subdir": {
            "type": "string", "default": "questions", "label": "题库子目录",
            "section": "题库",
        },
        "bank_sync_hours": {
            "type": "slider", "default": 12, "label": "题库自动刷新间隔(小时)",
            "min": 1, "max": 168, "step": 1, "section": "题库",
            "help": "定时重新拉取题库。也可发送 .hqsync 立即刷新。",
        },
        # —— 通用 ——
        "notify_owner": {
            "type": "boolean", "default": True, "label": "作答结果通知我",
            "section": "通用", "help": "答题/失败时用机器人通知平台主人。",
        },
    },
}

# 题库实例（setup 时创建）
_bank: Bank | None = None

# 作答去重：key = "acct:chat:msg" → 时间戳
_answered: dict[str, float] = {}
_ANSWERED_TTL = 6 * 3600

# 题库过期阈值：超过该时长自动同步一次（秒）
_STALE_SECS = 24 * 3600


def _parse_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for tok in re.split(r"[,，\s]+", str(raw or "").strip()):
        if not tok:
            continue
        try:
            ids.add(int(tok))
        except ValueError:
            pass
    return ids


def _prune_answered() -> None:
    now = _time.time()
    for k in [k for k, ts in _answered.items() if now - ts > _ANSWERED_TTL]:
        _answered.pop(k, None)


def _answer_once(client, message) -> bool:
    me = getattr(client, "me", None)
    acct_id = me.id if me else id(client)
    key = f"{acct_id}:{message.chat.id}:{message.id}"
    _prune_answered()
    if key in _answered:
        return False
    _answered[key] = _time.time()
    return True


def _is_safe_reply(text: str) -> bool:
    """作答文本安全收口：非空、不以命令前缀开头、无换行/注入符。"""
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("/") or t.startswith("."):
        return False
    if re.search(r"[\n\r]", t):
        return False
    return True


async def _safe_notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="影巢答题红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def _resolve_answer(ctx, parsed: dict) -> tuple[object, str, str]:
    """
    得出答案。返回 (matched_option_or_None, correct_content, source)。
    matched 为 (label, content)；都为空表示未得出。source ∈ {'题库','大模型',''}。
    """
    cfg = ctx.config
    q, opts, qtype = parsed["question"], parsed["options"], parsed["qtype"]

    # 1) 题库
    rec = _bank.lookup(q) if _bank else None
    if rec:
        correct = resolve_bank_answer(rec)
        matched = match_live_option(correct, opts, qtype)
        if not matched and re.fullmatch(r"[A-Da-d]", str(rec.get("answer", "")).strip()):
            matched = option_by_letter(rec["answer"], opts)
            if matched:
                correct = matched[1]
        if matched or correct:
            return (matched, correct, "题库")

    # 2) 大模型兜底
    if cfg.get("llm_enabled", False):
        ans, err = await _engine.ask_answer(cfg, q, opts, qtype, ctx.log)
        if ans:
            if qtype == "judge":
                return (match_live_option(ans, opts, qtype), ans, "大模型")
            matched = option_by_letter(ans, opts)
            return (matched, matched[1] if matched else "", "大模型")
        ctx.log.info("[影巢答题] 大模型兜底未得出: %s", err)

    return (None, "", "")


async def setup(ctx):
    global _bank
    _bank = Bank(ctx)

    async def _do_sync(reason: str = ""):
        cfg = ctx.config
        n, err = await _bank.sync(
            cfg.get("bank_repo", ""), cfg.get("bank_branch", "main"),
            cfg.get("bank_subdir", "questions"),
        )
        if err:
            ctx.log.warning("[影巢答题] 题库同步失败(%s): %s", reason or "定时", err)
        return n, err

    # 启动时：题库为空或已过期则同步一次（后台任务，不阻塞 setup）
    async def _initial_sync():
        stale = (_time.time() - _bank.last_sync()) > _STALE_SECS
        if _bank.size == 0 or stale:
            await _do_sync("启动")
    asyncio.create_task(_initial_sync())

    # 定时刷新题库
    try:
        hours = int(ctx.config.get("bank_sync_hours", 12) or 12)
    except (ValueError, TypeError):
        hours = 12
    ctx.schedule(lambda: asyncio.create_task(_do_sync("定时")),
                 "interval", hours=max(1, hours), id="影巢答题-题库同步")

    # ───────── 手动刷新题库命令 .hqsync ─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-12)
    async def on_sync_cmd(client, message):
        if not re.match(r"^[/\.]hqsync(?:\s|$)", message.text or "", re.IGNORECASE):
            return
        try:
            m = await message.edit("题库同步中...")
        except Exception:
            m = message
        n, err = await _do_sync("手动")
        txt = f"题库同步完成，共 {n} 题" if not err else f"题库同步失败：{err}"
        try:
            await m.edit(txt)
        except Exception:
            pass

    # ───────── 监听答题红包 ─────────
    @ctx.on_message(ctx.filters.group & (ctx.filters.text | ctx.filters.caption), group=7)
    async def on_quiz_packet(client, message):
        cfg = ctx.config
        if not cfg.get("enabled", False):
            return
        fu = message.from_user
        if not (fu and getattr(fu, "is_bot", False)):
            return
        bot_ids = _parse_ids(cfg.get("bot_ids", ""))
        if bot_ids and fu.id not in bot_ids:
            return
        groups = _parse_ids(cfg.get("listen_groups", ""))
        if groups and message.chat.id not in groups:
            return

        text = message.text or message.caption or ""
        clean = sanitize(text)
        # 收口：像答题红包（含答题类标记）
        if not any(mk in clean for mk in QUIZ_MARKERS):
            return
        parsed = parse_quiz(text)
        if not parsed:
            ctx.log.info("[影巢答题] 疑似答题红包但未解析出题面 chat=%s msg=%s",
                         message.chat.id, message.id)
            return
        if not _answer_once(client, message):
            return

        matched, correct, source = await _resolve_answer(ctx, parsed)
        if not matched and not correct:
            ctx.log.info("[影巢答题] 未得出答案 q=%r 选项=%s",
                         parsed["question"], parsed["options"])
            if cfg.get("notify_owner", True):
                await _safe_notify(
                    ctx, client,
                    f"影巢答题红包-未能作答（题库未命中且兜底失败）\n\n题目：{parsed['question']}\n\n{getattr(message,'link','')}",
                    level="warning",
                )
            return

        reply_text = build_reply(matched, correct, parsed["qtype"], cfg.get("reply_format", "content"))
        if not _is_safe_reply(reply_text):
            ctx.log.warning("[影巢答题] 作答文本不安全，已拦截: %r", reply_text)
            return

        delay = 0
        try:
            delay = int(cfg.get("answer_delay", 3) or 0)
        except (ValueError, TypeError):
            delay = 0
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            await client.send_message(message.chat.id, reply_text,
                                      reply_to_message_id=message.id, parse_mode=None)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[影巢答题] 回复答案失败 chat=%s msg=%s: %r",
                          message.chat.id, message.id, e)
            if cfg.get("notify_owner", True):
                await _safe_notify(ctx, client,
                                   f"影巢答题红包-回复失败\n\n{e}\n\n{getattr(message,'link','')}",
                                   level="error")
            return

        ctx.log.info("[影巢答题] 已作答 chat=%s msg=%s 来源=%s 答案=%r",
                     message.chat.id, message.id, source, reply_text)
        if cfg.get("notify_owner", True):
            await _safe_notify(
                ctx, client,
                f"影巢答题红包-已作答（{source}）\n\n题目：{parsed['question']}\n\n答案：{reply_text}\n\n{getattr(message,'link','')}",
                level="success",
            )

    ctx.log.info("[影巢答题] 已加载（题库 %d 题）", _bank.size)


async def teardown(ctx):
    global _bank
    _bank = None
    _answered.clear()
