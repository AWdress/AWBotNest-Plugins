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
# =============================================================================
from __future__ import annotations

import asyncio
import re
import time as _time
from collections import deque
from datetime import datetime

from . import _engine
from ._bank import Bank
from ._quiz import (
    QUIZ_MARKERS, sanitize, parse_quiz, resolve_bank_answer,
    match_live_option, option_by_letter, build_reply,
)

__plugin__ = {
    "name": "影巢答题红包",
    "id": "hdhive_quiz",
    "version": "1.0.1",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "description": "自动回答影巢机器人发的答题红包：从社区题库查答案回复，题库没有时可选大模型兜底作答。发包bot/群组可配。",
    "requirements": ["openai>=1.0"],
}

# ── 配置默认值（Vue 模式） ──
DEFAULTS = {
    "enabled": False,
    "bot_ids": "",
    "chat_ids": "",
    "reply_format": "content",
    "llm_enabled": False,
    "llm_api_key": "",
    "llm_base_url": "",
    "llm_model": "gpt-4o-mini",
    "bank_repo": "https://github.com/my-name-is-alan/hdhive-red-questions",
    "bank_branch": "main",
    "bank_subdir": "questions",
    "bank_sync_hours": 12,
}

# ── 运行态 ──
_bank: Bank | None = None
_answered: dict[str, float] = {}
_ANSWERED_TTL = 6 * 3600
_STALE_SECS = 24 * 3600
_sync_status = {"running": False, "message": ""}
_history = deque(maxlen=200)  # 答题记录环形缓冲


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _parse_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for tok in re.split(r"[,，\s]+", str(raw or "").strip()):
        if tok:
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
    return len(text) <= 200 and not re.search(r"[@#]", text)


async def _safe_notify(ctx, client, text, level="info"):
    try:
        await ctx.notify(text, level=level, category="影巢答题红包", account=client)
    except Exception:  # noqa: BLE001
        pass


async def _resolve_answer(ctx, parsed: dict) -> tuple[object, str, str]:
    """得出答案。返回 (matched_option_or_None, correct_content, source)。"""
    cfg = _effective_cfg(ctx)
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
        _sync_status["running"] = True
        _sync_status["message"] = f"同步中({reason})..."
        cfg = _effective_cfg(ctx)
        n, err = await _bank.sync(
            cfg.get("bank_repo", ""), cfg.get("bank_branch", "main"),
            cfg.get("bank_subdir", "questions"),
        )
        _sync_status["running"] = False
        if err:
            _sync_status["message"] = f"同步失败: {err}"
            ctx.log.warning("[影巢答题] 题库同步失败(%s): %s", reason or "定时", err)
        else:
            _sync_status["message"] = f"同步完成，共 {n} 题"
        return n, err

    # 启动时：题库为空或已过期则同步一次
    async def _initial_sync():
        stale = (_time.time() - _bank.last_sync()) > _STALE_SECS
        if _bank.size == 0 or stale:
            await _do_sync("启动")
    asyncio.create_task(_initial_sync())

    # 定时刷新题库（修正：传协程函数，不能用 lambda+create_task）
    async def _scheduled_sync():
        await _do_sync("定时")

    cfg = _effective_cfg(ctx)
    try:
        hours = int(cfg.get("bank_sync_hours", 12) or 12)
    except (ValueError, TypeError):
        hours = 12
    ctx.schedule(_scheduled_sync, "interval", hours=max(1, hours), id="题库同步")

    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/status", methods=["GET"])
    async def _api_status(req):
        last_ts = _bank.last_sync() if _bank else 0
        last_str = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S") if last_ts > 0 else "从未同步"
        return {
            "bank_size": _bank.size if _bank else 0,
            "last_sync": last_str,
            "sync_running": _sync_status["running"],
            "sync_status": _sync_status["message"] or "空闲",
        }

    @ctx.on_api("/sync", methods=["POST"])
    async def _api_sync(req):
        n, err = await _do_sync("手动")
        if err:
            return {"ok": False, "message": f"同步失败: {err}"}
        return {"ok": True, "message": f"同步完成，共 {n} 题"}

    @ctx.on_api("/test_llm", methods=["POST"])
    async def _api_test_llm(req):
        cfg = _effective_cfg(ctx)
        if not cfg.get("llm_enabled"):
            return {"ok": False, "message": "大模型兜底未启用"}
        test_q = "以下哪个是哺乳动物？"
        test_opts = [("A", "鲸鱼"), ("B", "鲨鱼"), ("C", "鳄鱼"), ("D", "蝙蝠")]
        ans, err = await _engine.ask_answer(cfg, test_q, test_opts, "single", ctx.log)
        if err:
            return {"ok": False, "message": f"调用失败: {err}"}
        return {"ok": True, "message": f"测试成功，返回: {ans}"}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        return {"history": list(_history)}

    @ctx.on_api("/update_config", methods=["POST"])
    async def _api_update_config(req):
        body = await req.json()
        ctx.update_config(body)
        return {"ok": True}

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
        cfg = _effective_cfg(ctx)
        if not cfg.get("enabled", False):
            return
        fu = message.from_user
        if not (fu and getattr(fu, "is_bot", False)):
            return
        bot_ids = _parse_ids(cfg.get("bot_ids", ""))
        if bot_ids and fu.id not in bot_ids:
            return
        chat_ids = _parse_ids(cfg.get("chat_ids", ""))
        if chat_ids and message.chat.id not in chat_ids:
            return

        text = sanitize(message.text or message.caption or "")
        if not any(m in text for m in QUIZ_MARKERS):
            return
        if not _answer_once(client, message):
            return

        parsed = parse_quiz(text)
        if not parsed:
            ctx.log.info("[影巢答题] 解析失败: %s", text[:100])
            return

        matched, correct, source = await _resolve_answer(ctx, parsed)
        if not (matched or correct):
            ctx.log.info("[影巢答题] 未得出答案: %s", parsed["question"][:50])
            return

        reply_text = build_reply(matched, correct, parsed["qtype"], cfg.get("reply_format", "content"))
        if not _is_safe_reply(reply_text):
            ctx.log.warning("[影巢答题] 回复内容异常: %s", reply_text[:50])
            return

        try:
            await message.reply(reply_text, quote=True)
            ctx.log.info("[影巢答题] 已作答(%s): %s → %s", source, parsed["question"][:30], reply_text)
            _history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "question": parsed["question"][:50],
                "answer": reply_text,
                "source": "bank" if source == "题库" else "llm",
            })
            await _safe_notify(ctx, client, f"✅ 已答题({source}): {parsed['question'][:30]}")
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[影巢答题] 回复失败: %s", e)


async def teardown(ctx):
    pass
