# =============================================================================
# AWBotNest 插件：趣味答题（quiz_game）
#
# 用你的用户账号在群里跑答题游戏：发「开启答题」出题，群友直接发答案抢答，
# 答对自动用 reply("+魔力") 发奖（由群转账 bot 实际打款），支持连胜加成。
#
# 出题源：AI（OpenAI 兼容接口，本插件自带配置）或天行数据 API。
# =============================================================================

import asyncio
import unicodedata
from collections import deque
from datetime import datetime
from difflib import SequenceMatcher

from ._engine import fetch_from_ai, fetch_from_tianapi

__plugin__ = {
    "name": "趣味答题",
    "id": "quiz_game",
    "version": "1.0.14",
    "author": "AWdress",
    "description": "群内答题游戏：发「开启答题」出题，群友抢答，答对自动发魔力奖励，支持连胜加成。AI或天行出题。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/quiz_game.png",
    "changelog": "v1.0.10 修复 Vue 配置保存\n- 保存配置改用新版平台 host.saveConfig，修复读取 undefined.post 失败\n- 答题记录和群组名称改用 host.callApi 读取\n- 读取、保存成功与失败统一使用平台提示\n\nv1.0.9 限制开局与答题消息来源\n- 只有插件所用的本人账号发送‘开启答题’或‘开始答题’才会开局\n- 结束命令同样只接受本人账号发送\n- 答案只接收其他群友的入站消息，开局账号不会参与抢答\n\nv1.0.7 前端移除自带 API 配置字段\n- 移除 AI 出题源的 ai_api_key/ai_base_url/ai_model 配置界面\n\nv1.0.6 改为仅使用平台统一 AI\n- 移除插件自带配置回退逻辑，仅调用平台统一 AI\n- 不再需要配置 ai_api_key/ai_base_url/ai_model\n\nv1.0.5 接入平台统一 AI 能力\n- AI 出题优先使用平台统一 AI（管理员在「系统设置→AI 服务」配置）\n- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置或天行数据\n\nv1.0.4 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "requirements": ["openai>=1.0"],
}

__plugin__["changelog"] = (
    "v1.0.14 持久化题库并加强近似去重\n"
    "- 已生成题目写入插件 KV，重载和容器重启后仍会过滤\n"
    "- 已用题库由最近 100 道扩大到 500 道\n"
    "- 除完全相同外，改写措辞和高度相似题目也会被拦截并继续补题\n\n"
    "v1.0.13 连续答题与交互提示\n"
    "- 单题无人答对时公布正确答案并自动进入下一题，不再提前结束整场\n"
    "- 配置页新增每场题目数量，支持 1 至 20 题\n"
    "- 答错时引用原消息提示并自动删除，题目与启动文案重新排版\n"
    "- 加固答对与超时并发处理，避免同一题重复结算\n\n"
    "v1.0.12 修复 AI 重复出题\n"
    "- 对 AI 返回结果执行代码级硬去重，不再只依赖提示词\n"
    "- 忽略题目中的空格、标点、全角半角及大小写差异后再比较\n"
    "- 单批题目不足时自动补题，最近 100 道已生成题目不会再次采用\n\n"
    "v1.0.11 优化答题交互与消息清理\n"
    "- 开启命令会原地显示题目生成状态，生成完成后直接变为首题\n"
    "- 每题答对后自动删除旧题，手动结束会清理本场全部答题消息\n"
    "- 防止题目生成期间重复开局，并完善超时、结束与卸载清理\n"
    "- 配置页新增命令和玩法说明\n\n"
    + __plugin__["changelog"]
)

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
    "question_count": 5,
    "auto_delete_delay": 30,
}

# ── 运行态 ──
_active: dict = {}
_starting: set = set()
_cancelled_starts: set = set()
_busy_hints: set = set()
_name_cache: dict = {}
_tasks: set = set()
_history = deque(maxlen=100)
_recent_questions = deque(maxlen=500)
_QUESTION_HISTORY_KEY = "used_questions_v2"
_SIMILARITY_THRESHOLD = 0.80


def _question_key(value) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    math_symbols = "+-×÷*/=<>"
    return "".join(char for char in normalized if char.isalnum() or char in math_symbols)


def _is_similar_question(key: str, seen_keys) -> bool:
    """拦截完全重复、包含式改写和高度相似题目。"""
    for old_key in seen_keys:
        if key == old_key:
            return True
        shorter, longer = sorted((key, old_key), key=len)
        if len(shorter) >= 8 and shorter in longer and len(shorter) / len(longer) >= 0.72:
            return True
        if min(len(key), len(old_key)) >= 6:
            if SequenceMatcher(None, key, old_key, autojunk=False).ratio() >= _SIMILARITY_THRESHOLD:
                return True
    return False


def _dedupe_questions(items, excluded=()) -> list[dict]:
    seen = set()
    for item in excluded:
        key = _question_key(item)
        if key:
            seen.add(key)
    result = []
    for item in items or []:
        question = str((item or {}).get("q", "")).strip()
        answer = str((item or {}).get("a", "")).strip()
        key = _question_key(question)
        if not key or not answer or _is_similar_question(key, seen):
            continue
        seen.add(key)
        result.append({**item, "q": question, "a": answer})
    return result


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


async def _delete_message(message):
    if not message:
        return
    try:
        await message.delete()
    except Exception:
        pass


async def _edit_message(message, text):
    try:
        await message.edit(text)
        return True
    except Exception:
        return False


async def setup(ctx):
    _recent_questions.clear()
    saved_questions = ctx.kv.get(_QUESTION_HISTORY_KEY) or []
    if isinstance(saved_questions, list):
        _recent_questions.extend(
            str(item).strip() for item in saved_questions if str(item).strip()
        )
    ctx.log.info("[答题] 已加载持久化去重题库：%s 道", len(_recent_questions))

    async def _send_temp(client, chat_id, text, delay=30):
        msg = await client.send_message(chat_id, text)
        _track(asyncio.create_task(_auto_del(msg, delay)))
        return msg

    async def _fetch_pool(cfg, rounds):
        source = cfg.get("source", "ai")
        excluded = list(_recent_questions)
        if not excluded:
            excluded = [item.get("question", "") for item in _history if item.get("question")]
        pool = []
        if source == "tianapi":
            for _ in range(rounds * 3):
                q = await fetch_from_tianapi(cfg.get("tianapi_key", ""), ctx.log)
                if q:
                    pool = _dedupe_questions([*pool, q], excluded)
                if len(pool) >= rounds:
                    break
            return pool[:rounds]

        # 提示词负责减少重复，代码过滤负责保证重复题绝不进入本轮。
        for _ in range(3):
            recent_questions = [*excluded, *(item["q"] for item in pool)]
            batch = await fetch_from_ai(
                ctx,
                rounds,
                "中等",
                ctx.log,
                recent_questions,
            )
            pool = _dedupe_questions([*pool, *batch], excluded)
            if len(pool) >= rounds:
                break
        if len(pool) < rounds:
            ctx.log.warning("[答题] AI 去重后题目不足：需要 %s 道，获得 %s 道", rounds, len(pool))
        return pool[:rounds]

    def _question_text(state, timeout, reward):
        return (
            "🎯 趣味答题\n"
            f"第 {state['round']} / {state['total_rounds']} 题\n\n"
            "🧩 题目\n"
            f"{state['q']}\n\n"
            f"⏱ 作答时间：{timeout} 秒\n"
            f"🎁 本题奖励：{reward} 魔力\n"
            "💬 直接发送答案，最先答对者获奖"
        )

    async def _advance_question(client, chat_id, timeout):
        state = _active.get(chat_id)
        if not state:
            return False
        if state["round"] >= state["total_rounds"]:
            return False
        state["round"] += 1
        next_q = state["question_pool"][state["next_idx"]]
        state["next_idx"] += 1
        state["q"] = next_q["q"]
        state["a"] = next_q["a"]
        state["aliases"] = next_q.get("aliases", [])
        state["answering"] = False
        await _send_next_question(client, chat_id, timeout)
        return True

    def _schedule_timeout(client, chat_id, timeout):
        async def _runner():
            await asyncio.sleep(timeout)
            state = _active.get(chat_id)
            if not state or state.get("answering"):
                return
            state["answering"] = True
            answer = state["a"]
            await _delete_message(state.get("question_msg"))
            state["question_msg"] = None
            if state["round"] >= state["total_rounds"]:
                await _stop(client, chat_id)
                await _send_temp(
                    client,
                    chat_id,
                    f"🏁 本场答题结束\n\n最后一题无人答对\n✅ 正确答案：{answer}\n\n题目已全部完成，本场消息已清理。",
                )
                return
            await _send_temp(
                client,
                chat_id,
                f"⌛ 本题时间到\n\n本题无人答对\n✅ 正确答案：{answer}\n\n下一题即将开始…",
                8,
            )
            await asyncio.sleep(3)
            if chat_id in _active:
                await _advance_question(client, chat_id, timeout)
        return _track(asyncio.create_task(_runner()))

    async def _send_next_question(client, chat_id, timeout):
        state = _active[chat_id]
        reward = int(_effective_cfg(ctx).get("base_reward", 500) or 500)
        text = _question_text(state, timeout, reward)
        try:
            msg = await client.send_message(chat_id, text)
            state["question_msg"] = msg
            state["messages"].append(msg)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[答题] 发题失败: %r", e)
            await _stop(client, chat_id)
            await _send_temp(client, chat_id, "题目发送失败，本场答题已结束。")
            return
        state["task"] = _schedule_timeout(client, chat_id, timeout)

    async def _start_legacy(client, chat_id, message):
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

    async def _stop_legacy(client, chat_id):
        if chat_id not in _active:
            return
        state = _active[chat_id]
        if state.get("task"):
            state["task"].cancel()
        _active.pop(chat_id, None)
        _busy_hints.discard(chat_id)

    async def _start(client, chat_id, message):
        cfg = _effective_cfg(ctx)
        if chat_id in _starting:
            await _edit_message(message, "⏳ 题目正在生成中\n\n请勿重复启动，稍候即可开始答题。")
            _track(asyncio.create_task(_auto_del(message, 5)))
            return
        if chat_id in _active:
            await _edit_message(message, "⚠️ 当前已有答题正在进行\n\n如需结束，请发送：结束答题")
            _track(asyncio.create_task(_auto_del(message, 5)))
            return

        _starting.add(chat_id)
        timeout = int(cfg.get("timeout", 60) or 60)
        reward = int(cfg.get("base_reward", 500) or 500)
        rounds = max(1, min(20, int(cfg.get("question_count", 5) or 5)))
        await _edit_message(
            message,
            "🎯 趣味答题 · 准备中\n\n"
            f"正在为本场生成 {rounds} 道题目\n"
            "题库会自动避开近期重复内容，请稍候…",
        )
        try:
            pool = await _fetch_pool(cfg, rounds)
            if chat_id in _cancelled_starts:
                await _delete_message(message)
                return
            if len(pool) < rounds:
                await _edit_message(message, "❌ 题目生成失败\n\n请检查出题源配置后重新发送“开启答题”。")
                _track(asyncio.create_task(_auto_del(message, 8)))
                return

            _recent_questions.extend(item["q"] for item in pool)
            ctx.kv.set(_QUESTION_HISTORY_KEY, list(_recent_questions))

            first = pool[0]
            _active[chat_id] = {
                "q": first["q"], "a": first["a"], "aliases": first.get("aliases", []),
                "round": 1, "total_rounds": rounds, "scores": {}, "task": None,
                "answering": False, "question_pool": pool, "next_idx": 1,
                "messages": [message], "question_msg": message,
                "last_winner_id": 0, "streak_count": 0,
            }
            _name_cache.setdefault(chat_id, {})
            text = _question_text(_active[chat_id], timeout, reward)
            if not await _edit_message(message, text):
                msg = await client.send_message(chat_id, text)
                _active[chat_id]["question_msg"] = msg
                _active[chat_id]["messages"].append(msg)
                await _delete_message(message)
            _active[chat_id]["task"] = _schedule_timeout(client, chat_id, timeout)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[答题] 启动失败: %r", e)
            _active.pop(chat_id, None)
            await _edit_message(message, "❌ 答题启动失败\n\n请稍后重新发送“开启答题”。")
            _track(asyncio.create_task(_auto_del(message, 8)))
        finally:
            _starting.discard(chat_id)
            _cancelled_starts.discard(chat_id)

    async def _stop(client, chat_id):
        state = _active.pop(chat_id, None)
        if not state:
            if chat_id in _starting:
                _cancelled_starts.add(chat_id)
                return True
            _starting.discard(chat_id)
            return False
        task = state.get("task")
        if task and task is not asyncio.current_task():
            task.cancel()
        seen = set()
        for msg in state.get("messages", []):
            marker = getattr(msg, "id", None) or id(msg)
            if marker in seen:
                continue
            seen.add(marker)
            await _delete_message(msg)
        _busy_hints.discard(chat_id)
        _starting.discard(chat_id)
        return True

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
        if not text:
            return

        # 统一纳入本场清理；没有群管理权限时删除失败会被安全忽略。
        state["messages"].append(message)

        correct = state["a"].strip().lower()
        aliases = [x.strip().lower() for x in state.get("aliases", [])]

        if text not in [correct, *aliases]:
            try:
                hint = await message.reply("❌ 答案不对，再想一想～", quote=True)
                if hint:
                    state["messages"].append(hint)
                    _track(asyncio.create_task(_auto_del(hint, 4)))
            except Exception:  # noqa: BLE001
                await _send_temp(client, chat_id, "❌ 答案不对，再想一想～", 4)
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
            reward_msg = await message.reply(f"+{reward}", quote=True)
            if reward_msg:
                state["messages"].append(reward_msg)
        except Exception:  # noqa: BLE001
            pass

        _history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "group": message.chat.title or str(chat_id),
            "question": state["q"],
            "answer": state["a"],
            "player": user_name,
            "reward": reward,
        })

        await _delete_message(state.get("question_msg"))
        state["question_msg"] = None

        if state["round"] >= state["total_rounds"]:
            await _stop(client, chat_id)
            await _send_temp(
                client,
                chat_id,
                f"🏁 趣味答题结束\n\n最后一题由 {user_name} 答对，本场消息已清理。",
            )
            return

        timeout = int(cfg.get("timeout", 60) or 60)
        await _send_temp(client, chat_id, f"✅ {user_name} 答对，获得 {reward} 魔力\n正在发送下一题…", 4)
        await _advance_question(client, chat_id, timeout)

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
            stopped = await _stop(client, chat_id)
            notice = (
                "✅ 趣味答题已结束\n\n本场题目与奖励消息已清理。"
                if stopped else
                "ℹ️ 当前没有正在进行的答题。"
            )
            await _edit_message(message, notice)
            _track(asyncio.create_task(_auto_del(message, 5)))
            return

        # 开局账号只负责发起/结束，不参与自己的答题。
        if is_outgoing:
            return
        await _handle_answer(client, message)


async def teardown(ctx):
    for task in list(_tasks):
        task.cancel()
    _tasks.clear()
    for state in list(_active.values()):
        for message in state.get("messages", []):
            await _delete_message(message)
    _active.clear()
    _starting.clear()
    _cancelled_starts.clear()
    _busy_hints.clear()
