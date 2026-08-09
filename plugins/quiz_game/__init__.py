# =============================================================================
# AWBotNest 插件：趣味答题（quiz_game）
#
# 用你的用户账号在群里跑答题游戏：发「开启答题」出题，群友直接发答案抢答，
# 答对自动用 reply("+魔力") 发奖（由群转账 bot 实际打款），支持连胜加成。
#
# 出题源：AI（OpenAI 兼容接口，本插件自带配置）或天行数据 API。
# =============================================================================

import asyncio
from collections import deque
from datetime import datetime

from ._engine import fetch_from_ai, fetch_from_tianapi

__plugin__ = {
    "name": "趣味答题",
    "id": "quiz_game",
    "version": "1.0.10",
    "author": "AWdress",
    "description": "群内答题游戏：发「开启答题」出题，群友抢答，答对自动发魔力奖励，支持连胜加成。AI或天行出题。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/quiz_game.png",
    "changelog": "v1.0.10 修复 Vue 配置保存\n- 保存配置改用新版平台 host.saveConfig，修复读取 undefined.post 失败\n- 答题记录和群组名称改用 host.callApi 读取\n- 读取、保存成功与失败统一使用平台提示\n\nv1.0.9 限制开局与答题消息来源\n- 只有插件所用的本人账号发送‘开启答题’或‘开始答题’才会开局\n- 结束命令同样只接受本人账号发送\n- 答案只接收其他群友的入站消息，开局账号不会参与抢答\n\nv1.0.7 前端移除自带 API 配置字段\n- 移除 AI 出题源的 ai_api_key/ai_base_url/ai_model 配置界面\n\nv1.0.6 改为仅使用平台统一 AI\n- 移除插件自带配置回退逻辑，仅调用平台统一 AI\n- 不再需要配置 ai_api_key/ai_base_url/ai_model\n\nv1.0.5 接入平台统一 AI 能力\n- AI 出题优先使用平台统一 AI（管理员在「系统设置→AI 服务」配置）\n- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置或天行数据\n\nv1.0.4 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": ["openai>=1.0"],
}

# ── 配置默认值 ──
DEFAULTS = {
    "valid_groups": "",
    "source": "ai",
    "ai_api_key": "",
    "ai_base_url": "",
    "ai_model": "gpt-4o-mini",
    "tianapi_key": "",
    "base_reward": 500,
    "streak_enabled": True,
    "streak_multiplier": 1.5,
    "max_streak": 5,
    "timeout": 60,
    "auto_delete_delay": 30,
}

# ── 运行态 ──
_active: dict = {}
_busy_hints: set = set()
_name_cache: dict = {}
_tasks: set = set()
_history = deque(maxlen=100)


def _effective_cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _track(task):
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


def _lines(raw) -> list[str]:
    return [x.strip() for x in str(raw or "").splitlines() if x.strip()]


def _valid_group(cfg, chat_id: int) -> bool:
    raw = cfg.get("valid_groups") or []
    items = raw if isinstance(raw, list) else _lines(raw)
    groups = []
    for x in items:
        try:
            groups.append(int(x))
        except (ValueError, TypeError):
            pass
    return True if not groups else chat_id in groups


def _chat_name(chat, fallback) -> str:
    return getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(fallback)


async def _chat_name_items(ctx, raw) -> list[dict]:
    values = []
    for item in (raw if isinstance(raw, list) else _lines(raw)):
        try:
            value = int(item)
        except (ValueError, TypeError):
            continue
        if value not in values:
            values.append(value)
    apps = list(getattr(ctx, "user_apps", None) or [])
    items = []
    for value in values:
        title = str(value)
        for app in apps:
            try:
                title = _chat_name(await app.get_chat(value), value)
                break
            except Exception:  # noqa: BLE001
                continue
        items.append({"id": value, "title": title})
    return items


async def _auto_del(message, delay: int = 30):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def setup(ctx):
    async def _send_temp(client, chat_id, text, delay=30):
        msg = await client.send_message(chat_id, text)
        _track(asyncio.create_task(_auto_del(msg, delay)))
        return msg

    async def _fetch_pool(cfg, rounds):
        source = cfg.get("source", "ai")
        if source == "tianapi":
            pool = []
            for _ in range(rounds):
                q = await fetch_from_tianapi(cfg.get("tianapi_key", ""), ctx.log)
                if q:
                    pool.append(q)
            return pool
        return await fetch_from_ai(ctx, rounds, "中等", ctx.log)

    def _schedule_timeout(client, chat_id, timeout):
        async def _runner():
            await asyncio.sleep(timeout)
            if chat_id in _active:
                ans = _active[chat_id]["a"]
                await _send_temp(client, chat_id, f"时间到！正确答案是：{ans}\n活动已结束")
                await _stop(client, chat_id)
        return _track(asyncio.create_task(_runner()))

    async def _send_next_question(client, chat_id, timeout):
        state = _active[chat_id]
        text = (f"趣味答题 · 第 {state['round']}/{state['total_rounds']} 轮\n"
                f"{state['q']}\n\n请在 {timeout} 秒内直接发送答案")
        try:
            msg = await client.send_message(chat_id, text)
            state["q_msgs"].append(msg)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[答题] 发题失败: %r", e)
            return
        state["task"] = _schedule_timeout(client, chat_id, timeout)

    async def _start(client, chat_id, message):
        cfg = _effective_cfg(ctx)
        if chat_id in _active:
            if chat_id not in _busy_hints:
                _busy_hints.add(chat_id)
                await _send_temp(client, chat_id, "答题已在进行中，结束请发：结束答题")
            return
        timeout = int(cfg.get("timeout", 60) or 60)
        reward = int(cfg.get("base_reward", 500) or 500)
        rounds = 5

        pool = await _fetch_pool(cfg, rounds)
        _busy_hints.discard(chat_id)
        if len(pool) < rounds:
            await _send_temp(client, chat_id, "出题失败，请检查出题源配置。")
            return

        first = pool[0]
        _active[chat_id] = {
            "q": first["q"], "a": first["a"], "aliases": first.get("aliases", []),
            "round": 1, "total_rounds": rounds, "scores": {}, "task": None,
            "answering": False, "question_pool": pool, "next_idx": 1, "q_msgs": [],
            "last_winner_id": 0, "streak_count": 0,
        }
        _name_cache.setdefault(chat_id, {})
        text = (f"趣味答题 · 第 1/{rounds} 轮\n答对奖励：{reward} 魔力\n"
                f"{first['q']}\n\n请在 {timeout} 秒内直接发送答案\n（发「结束答题」可手动结束）")
        try:
            msg = await client.send_message(chat_id, text)
            _active[chat_id]["q_msgs"].append(msg)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[答题] 发题失败: %r", e)
            return
        _active[chat_id]["task"] = _schedule_timeout(client, chat_id, timeout)

    async def _stop(client, chat_id):
        if chat_id not in _active:
            return
        state = _active[chat_id]
        if state.get("task"):
            state["task"].cancel()
        _active.pop(chat_id, None)
        _busy_hints.discard(chat_id)

    async def _handle_answer(client, message):
        cfg = _effective_cfg(ctx)
        chat_id = message.chat.id
        if chat_id not in _active:
            return
        state = _active[chat_id]
        if state.get("answering"):
            return
        if not getattr(message, "from_user", None):
            return

        text = (message.text or "").strip().lower()
        correct = state["a"].strip().lower()
        aliases = [x.strip().lower() for x in state.get("aliases", [])]

        if text not in [correct, *aliases]:
            return

        state["answering"] = True
        if state.get("task"):
            state["task"].cancel()

        user_id = message.from_user.id
        user_name = message.from_user.first_name or str(user_id)
        _name_cache.setdefault(chat_id, {})[user_id] = user_name

        reward = int(cfg.get("base_reward", 500) or 500)
        if cfg.get("streak_enabled") and user_id == state["last_winner_id"]:
            state["streak_count"] += 1
            multiplier = float(cfg.get("streak_multiplier", 1.5))
            max_streak = int(cfg.get("max_streak", 5))
            streak = min(state["streak_count"], max_streak)
            reward = int(reward * (multiplier ** streak))
        else:
            state["streak_count"] = 1
            state["last_winner_id"] = user_id

        state["scores"][user_id] = state["scores"].get(user_id, 0) + reward

        try:
            await message.reply(f"+{reward}", quote=True)
        except Exception:  # noqa: BLE001
            pass

        _history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "group": message.chat.title or str(chat_id),
            "question": state["q"][:50],
            "answer": state["a"],
            "player": user_name,
            "reward": reward,
        })

        if state["round"] >= state["total_rounds"]:
            await _send_temp(client, chat_id, f"✅ {user_name} 答对！\n游戏结束")
            await _stop(client, chat_id)
            return

        state["round"] += 1
        next_q = state["question_pool"][state["next_idx"]]
        state["next_idx"] += 1
        state["q"] = next_q["q"]
        state["a"] = next_q["a"]
        state["aliases"] = next_q.get("aliases", [])
        state["answering"] = False

        timeout = int(cfg.get("timeout", 60) or 60)
        await _send_next_question(client, chat_id, timeout)

    # ───────── Vue 模式后端 API ─────────
    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        return {"history": list(_history)}

    @ctx.on_api("/chat_names", methods=["GET"])
    async def _api_chat_names(req):
        return {"items": await _chat_name_items(ctx, _effective_cfg(ctx).get("valid_groups", ""))}

    # ───────── 消息监听 ─────────
    @ctx.on_message(ctx.filters.group, group=7)
    async def on_group_message(client, message):
        cfg = _effective_cfg(ctx)
        chat_id = message.chat.id

        if not _valid_group(cfg, chat_id):
            return

        text = (message.text or "").strip()
        is_outgoing = bool(getattr(message, "outgoing", False))

        if text in ["开启答题", "开始答题"]:
            if not is_outgoing:
                return
            await _start(client, chat_id, message)
            return

        if text in ["结束答题", "停止答题"]:
            if not is_outgoing:
                return
            await _stop(client, chat_id)
            await _send_temp(client, chat_id, "答题活动已结束")
            return

        # 开局账号只负责发起/结束，不参与自己的答题。
        if is_outgoing:
            return
        await _handle_answer(client, message)


async def teardown(ctx):
    for task in list(_tasks):
        task.cancel()
    _tasks.clear()
