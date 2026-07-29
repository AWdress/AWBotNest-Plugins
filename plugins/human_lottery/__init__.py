"""人形抽奖：用户账号在群里发起、收集参与者并随机开奖。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import random
import re
import time


__plugin__ = {
    "name": "人形抽奖",
    "id": "human_lottery",
    "version": "1.0.1",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "description": "用用户账号在群里像真人一样发起抽奖：群友发送关键词参与，到时随机开奖，支持状态、提前开奖、取消和历史记录。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/common_lottery.jpg",
    "changelog": "v1.0.1 新增自动发奖\n- 开奖后由用户账号回复中奖者的参与消息发送 +金额\n- 创建命令支持第 5 项指定每人奖励金额，省略时自动从奖品名称提取数字\n- 支持自动发奖开关、命令模板、逐人随机间隔及发奖结果记录\n\nv1.0.0 初始版本\n- 用户账号通过自然命令在群里发起抽奖\n- 群友发送参与关键词报名，同一用户自动去重\n- 支持定时开奖、提前开奖、取消、参与播报和随机人形延迟\n- 支持用户黑名单、最低参与人数、命令自动删除及活动历史面板",
}


DEFAULTS = {
    "enabled": True,
    "create_word": "创建抽奖",
    "status_word": "抽奖状态",
    "draw_word": "立即开奖",
    "cancel_word": "取消抽奖",
    "default_keyword": "参与抽奖",
    "default_duration": 10,
    "default_winners": 1,
    "min_participants": 1,
    "max_duration": 1440,
    "max_winners": 100,
    "allow_creator": False,
    "require_reply": False,
    "delete_commands": True,
    "announce_delay_min": 1,
    "announce_delay_max": 3,
    "draw_delay_min": 2,
    "draw_delay_max": 8,
    "progress_every": 0,
    "blacklist_ids": "",
    "notify_owner": True,
    "auto_award": True,
    "award_command": "+{amount}",
    "award_delay_min": 1,
    "award_delay_max": 3,
    "announce_template": "🎉 抽奖开始啦！\n\n🎁 奖品：{prize}\n🏆 中奖人数：{winners} 人\n⏰ 开奖时间：{draw_time}\n🔑 参与方式：发送「{keyword}」\n\n每人只能参与一次，祝大家好运～",
    "result_template": "🎊 开奖啦！\n\n🎁 奖品：{prize}\n👥 参与人数：{participants}\n🏆 中奖名单：\n{winner_list}\n\n恭喜中奖，感谢大家参与～",
    "empty_template": "这次抽奖参与人数不足（{participants}/{minimum}），先取消啦，下次再来～",
}


_manager = None


def _to_int(value, default: int, low: int = 0, high: int = 10**9) -> int:
    try:
        return max(low, min(high, int(float(value))))
    except (TypeError, ValueError):
        return default


def _parse_ids(raw) -> set[int]:
    result = set()
    for part in re.split(r"[\s,，]+", str(raw or "")):
        try:
            result.add(int(part))
        except (TypeError, ValueError):
            pass
    return result


def _display_name(user) -> str:
    if not user:
        return "未知用户"
    return str(
        getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or getattr(user, "id", "未知用户")
    )


def _winner_label(item: dict) -> str:
    username = str(item.get("username") or "").strip().lstrip("@")
    return f"@{username}" if username else f"{item.get('name') or '用户'}（{item.get('id')}）"


class _SafeValues(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _format_template(template: str, **values) -> str:
    """未知占位符原样保留，避免用户自定义文案中的花括号导致活动失败。"""
    return str(template or "").format_map(_SafeValues(values))


def _activity_key(client, chat_id: int) -> str:
    me = getattr(client, "me", None)
    account_id = getattr(me, "id", None) or id(client)
    return f"{account_id}:{chat_id}"


def _parse_create(text: str, cfg: dict):
    """格式：创建抽奖 奖品 | 中奖人数 | 持续分钟 | 参与关键词 | 每人奖励。"""
    word = str(cfg.get("create_word") or "创建抽奖").strip()
    raw = str(text or "").strip()
    if raw != word and not raw.startswith(word + " "):
        return None
    body = raw[len(word):].strip()
    if not body:
        return {"error": "格式：创建抽奖 奖品 | 中奖人数 | 持续分钟 | 参与关键词 | 每人奖励（可省略）"}
    parts = [part.strip() for part in re.split(r"\s*[|｜]\s*", body)]
    prize = parts[0]
    if not prize:
        return {"error": "奖品不能为空"}
    winners = _to_int(
        parts[1] if len(parts) > 1 and parts[1] else cfg.get("default_winners"),
        1, 1, _to_int(cfg.get("max_winners"), 100, 1, 1000),
    )
    duration = _to_int(
        parts[2] if len(parts) > 2 and parts[2] else cfg.get("default_duration"),
        10, 1, _to_int(cfg.get("max_duration"), 1440, 1, 10080),
    )
    keyword = parts[3] if len(parts) > 3 and parts[3] else str(
        cfg.get("default_keyword") or "参与抽奖"
    ).strip()
    if not keyword:
        return {"error": "参与关键词不能为空"}
    if len(prize) > 200 or len(keyword) > 50:
        return {"error": "奖品最多 200 字，参与关键词最多 50 字"}
    award_amount = ""
    if len(parts) > 4 and parts[4]:
        amount_match = re.search(r"\d+(?:\.\d+)?", parts[4].replace(",", ""))
        award_amount = amount_match.group(0) if amount_match else ""
        if not award_amount:
            return {"error": "每人奖励必须包含有效数字，例如 1000"}
    elif cfg.get("auto_award", True):
        amount_match = re.search(r"\d+(?:\.\d+)?", prize.replace(",", ""))
        award_amount = amount_match.group(0) if amount_match else ""
    return {
        "prize": prize, "winners": winners, "duration": duration,
        "keyword": keyword, "award_amount": award_amount,
    }


async def _safe_delete(message):
    try:
        await message.delete()
    except Exception:  # noqa: BLE001 - 无删除权限时不影响主流程
        pass


class LotteryManager:
    HISTORY_KEY = "lottery_history"
    HISTORY_MAX = 200

    def __init__(self, ctx):
        self.ctx = ctx
        self.active: dict[str, dict] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def _cfg(self, key, default=None):
        return self.ctx.config.get(key, DEFAULTS.get(key, default))

    @staticmethod
    async def _human_delay(low, high):
        low, high = max(0, float(low)), max(0, float(high))
        if low > high:
            low, high = high, low
        if high:
            await asyncio.sleep(random.uniform(low, high))

    def _next_id(self) -> int:
        seq = _to_int(self.ctx.kv.get("lottery_seq", 0), 0) + 1
        self.ctx.kv.set("lottery_seq", seq)
        return seq

    async def create(self, client, message, params: dict) -> bool:
        key = _activity_key(client, message.chat.id)
        if key in self.active:
            await client.send_message(message.chat.id, "这个群已经有一场抽奖在进行了，先开奖或取消再创建吧～")
            return False

        await self._human_delay(
            self._cfg("announce_delay_min", 1),
            self._cfg("announce_delay_max", 3),
        )
        now = time.time()
        draw_at = now + params["duration"] * 60
        lottery_id = self._next_id()
        draw_time = datetime.fromtimestamp(draw_at).strftime("%m-%d %H:%M")
        template = str(self._cfg("announce_template", DEFAULTS["announce_template"]))
        text = _format_template(
            template,
            prize=params["prize"], winners=params["winners"],
            keyword=params["keyword"], duration=params["duration"],
            draw_time=draw_time, lottery_id=lottery_id,
        )
        announcement = await client.send_message(message.chat.id, text)
        if not announcement:
            return False

        creator = message.from_user
        activity = {
            "key": key,
            "lottery_id": lottery_id,
            "client": client,
            "chat_id": message.chat.id,
            "chat_title": getattr(message.chat, "title", "") or str(message.chat.id),
            "creator_id": getattr(creator, "id", 0),
            "creator_name": _display_name(creator),
            "announcement_id": announcement.id,
            "prize": params["prize"],
            "winner_count": params["winners"],
            "keyword": params["keyword"],
            "award_amount": params.get("award_amount", ""),
            "duration": params["duration"],
            "created_at": now,
            "draw_at": draw_at,
            "participants": {},
            "status": "进行中",
        }
        self.active[key] = activity
        self.locks[key] = asyncio.Lock()
        self.tasks[key] = asyncio.create_task(self._wait_and_draw(key))
        self.tasks[key].add_done_callback(lambda _task, k=key: self.tasks.pop(k, None))
        self.ctx.log.info(
            "群 %s 创建抽奖 #%s：%s，%s 人，%s 分钟，关键词=%s",
            message.chat.id, lottery_id, params["prize"], params["winners"],
            params["duration"], params["keyword"],
        )
        return True

    async def _wait_and_draw(self, key: str):
        try:
            activity = self.active.get(key)
            if not activity:
                return
            await asyncio.sleep(max(0, activity["draw_at"] - time.time()))
            await self.draw(key, reason="到时开奖")
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            self.ctx.log.error("自动开奖失败：%r", exc)

    async def participate(self, client, message) -> bool:
        key = _activity_key(client, message.chat.id)
        activity = self.active.get(key)
        if not activity or activity["status"] != "进行中":
            return False
        if str(message.text or "").strip() != activity["keyword"]:
            return False
        user = message.from_user
        user_id = getattr(user, "id", 0)
        if not user_id or user_id in _parse_ids(self._cfg("blacklist_ids", "")):
            return False
        if not self._cfg("allow_creator", False) and user_id == activity["creator_id"]:
            return False
        if self._cfg("require_reply", False):
            replied = getattr(message, "reply_to_message", None)
            if not replied or getattr(replied, "id", None) != activity["announcement_id"]:
                return False

        async with self.locks[key]:
            activity = self.active.get(key)
            if not activity or user_id in activity["participants"]:
                return False
            activity["participants"][user_id] = {
                "id": user_id,
                "name": _display_name(user),
                "username": getattr(user, "username", None) or "",
                "message_id": getattr(message, "id", None),
                "joined_at": time.time(),
            }
            count = len(activity["participants"])

        every = _to_int(self._cfg("progress_every", 0), 0, 0, 1000)
        if every and count % every == 0:
            await self._human_delay(0.5, 2.0)
            await client.send_message(
                activity["chat_id"],
                f"抽奖 #{activity['lottery_id']} 已有 {count} 人参加啦，继续等有缘人～",
            )
        return True

    async def draw(self, key: str, reason: str = "手动开奖") -> bool:
        activity = self.active.get(key)
        if not activity:
            return False
        async with self.locks.setdefault(key, asyncio.Lock()):
            activity = self.active.get(key)
            if not activity or activity["status"] != "进行中":
                return False
            activity["status"] = "开奖中"

        task = self.tasks.get(key)
        current = asyncio.current_task()
        if task and task is not current and not task.done():
            task.cancel()

        await self._human_delay(
            self._cfg("draw_delay_min", 2),
            self._cfg("draw_delay_max", 8),
        )
        participants = list(activity["participants"].values())
        minimum = _to_int(self._cfg("min_participants", 1), 1, 1, 100000)
        winners = []
        if len(participants) >= minimum:
            count = min(activity["winner_count"], len(participants))
            winners = random.SystemRandom().sample(participants, count)
            winner_list = "\n".join(
                f"{index}. {_winner_label(item)}"
                for index, item in enumerate(winners, 1)
            )
            text = _format_template(
                self._cfg("result_template", DEFAULTS["result_template"]),
                prize=activity["prize"], participants=len(participants),
                winners=len(winners), winner_list=winner_list,
                lottery_id=activity["lottery_id"], keyword=activity["keyword"],
            )
            await activity["client"].send_message(
                activity["chat_id"], text,
                reply_to_message_id=activity["announcement_id"],
                parse_mode=None,
            )
            award_result = await self._send_awards(activity, winners)
            status = "已开奖"
        else:
            award_result = {"enabled": False, "success": 0, "total": 0, "failed": []}
            text = _format_template(
                self._cfg("empty_template", DEFAULTS["empty_template"]),
                prize=activity["prize"], participants=len(participants),
                minimum=minimum, lottery_id=activity["lottery_id"],
            )
            await activity["client"].send_message(
                activity["chat_id"], text,
                reply_to_message_id=activity["announcement_id"],
            )
            status = "人数不足"

        self._finish(activity, status, winners, reason, award_result)
        if self._cfg("notify_owner", True):
            try:
                await self.ctx.notify(
                    f"抽奖 #{activity['lottery_id']} {status}：{activity['prize']}，"
                    f"参与 {len(participants)} 人，中奖 {len(winners)} 人",
                    level="success" if winners else "warning",
                    category="人形抽奖",
                    account=activity["client"],
                )
            except Exception as exc:  # noqa: BLE001
                self.ctx.log.warning("开奖通知失败：%r", exc)
        return True

    async def _send_awards(self, activity: dict, winners: list[dict]) -> dict:
        amount = str(activity.get("award_amount") or "").strip()
        if not self._cfg("auto_award", True) or not amount:
            if self._cfg("auto_award", True) and not amount:
                self.ctx.log.warning(
                    "抽奖 #%s 未提取到奖励金额，已跳过自动发奖",
                    activity["lottery_id"],
                )
            return {"enabled": False, "success": 0, "total": len(winners), "failed": []}

        command = _format_template(
            str(self._cfg("award_command", "+{amount}") or "+{amount}"),
            amount=amount,
            prize=activity["prize"],
            lottery_id=activity["lottery_id"],
        ).strip()
        success, failed = 0, []
        for winner in winners:
            message_id = winner.get("message_id")
            try:
                if not message_id:
                    raise RuntimeError("缺少参与消息 ID")
                await self._human_delay(
                    self._cfg("award_delay_min", 1),
                    self._cfg("award_delay_max", 3),
                )
                sent = await activity["client"].send_message(
                    activity["chat_id"],
                    command,
                    reply_to_message_id=message_id,
                )
                if not sent:
                    raise RuntimeError("Telegram 未返回发奖消息")
                success += 1
                self.ctx.log.info(
                    "抽奖 #%s 已给 %s (%s) 发奖：%s",
                    activity["lottery_id"], winner["name"], winner["id"], command,
                )
            except Exception as exc:  # noqa: BLE001
                failed.append({"id": winner["id"], "name": winner["name"], "error": str(exc)})
                self.ctx.log.error(
                    "抽奖 #%s 给 %s (%s) 发奖失败：%r",
                    activity["lottery_id"], winner["name"], winner["id"], exc,
                )
        return {
            "enabled": True, "amount": amount, "command": command,
            "success": success, "total": len(winners), "failed": failed,
        }

    async def cancel(self, key: str, reason: str = "手动取消") -> bool:
        activity = self.active.get(key)
        if not activity:
            return False
        task = self.tasks.get(key)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
        await activity["client"].send_message(
            activity["chat_id"],
            f"抽奖 #{activity['lottery_id']} 已取消，大家不用再发参与关键词啦～",
            reply_to_message_id=activity["announcement_id"],
        )
        self._finish(
            activity, "已取消", [], reason,
            {"enabled": False, "success": 0, "total": 0, "failed": []},
        )
        return True

    def _finish(
        self, activity: dict, status: str, winners: list, reason: str,
        award_result: dict,
    ):
        history = self.ctx.kv.get(self.HISTORY_KEY, [])
        if not isinstance(history, list):
            history = []
        history.append({
            "lottery_id": activity["lottery_id"],
            "chat_id": activity["chat_id"],
            "chat_title": activity["chat_title"],
            "prize": activity["prize"],
            "keyword": activity["keyword"],
            "winner_count": activity["winner_count"],
            "participants": len(activity["participants"]),
            "winners": [{"id": w["id"], "name": w["name"]} for w in winners],
            "award": award_result,
            "status": status,
            "reason": reason,
            "created_at": activity["created_at"],
            "finished_at": time.time(),
        })
        self.ctx.kv.set(self.HISTORY_KEY, history[-self.HISTORY_MAX:])
        key = activity["key"]
        self.active.pop(key, None)
        self.locks.pop(key, None)
        self.ctx.log.info(
            "抽奖 #%s %s：参与 %s，中奖 %s",
            activity["lottery_id"], status, len(activity["participants"]), len(winners),
        )

    async def status(self, client, chat_id: int):
        activity = self.active.get(_activity_key(client, chat_id))
        if not activity:
            await client.send_message(chat_id, "这个群现在没有进行中的抽奖～")
            return
        remain = max(0, int(activity["draw_at"] - time.time()))
        await client.send_message(
            chat_id,
            f"🎟 抽奖 #{activity['lottery_id']} 状态\n"
            f"奖品：{activity['prize']}\n"
            f"参与：{len(activity['participants'])} 人\n"
            f"中奖名额：{activity['winner_count']} 人\n"
            f"距离开奖：约 {remain // 60} 分 {remain % 60} 秒\n"
            f"参与关键词：{activity['keyword']}",
            reply_to_message_id=activity["announcement_id"],
        )

    def snapshot(self):
        now = time.time()
        return [{
            "key": key,
            "lottery_id": a["lottery_id"],
            "chat_id": a["chat_id"],
            "chat_title": a["chat_title"],
            "prize": a["prize"],
            "keyword": a["keyword"],
            "winner_count": a["winner_count"],
            "participants": len(a["participants"]),
            "draw_time": datetime.fromtimestamp(a["draw_at"]).strftime("%m-%d %H:%M"),
            "remaining_seconds": max(0, int(a["draw_at"] - now)),
            "status": a["status"],
        } for key, a in self.active.items()]

    def history(self):
        raw = self.ctx.kv.get(self.HISTORY_KEY, [])
        if not isinstance(raw, list):
            return []
        result = []
        for item in reversed(raw):
            row = dict(item)
            row["winner_names"] = "、".join(w.get("name", "") for w in row.get("winners", []))
            row["time"] = datetime.fromtimestamp(
                row.get("finished_at", 0)
            ).strftime("%Y-%m-%d %H:%M")
            result.append(row)
        return result

    def close(self):
        for task in list(self.tasks.values()):
            if not task.done():
                task.cancel()
        self.tasks.clear()
        self.active.clear()
        self.locks.clear()


async def setup(ctx):
    global _manager
    _manager = LotteryManager(ctx)

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.group & ctx.filters.text, group=-10)
    async def on_owner_command(client, message):
        if not ctx.config.get("enabled", DEFAULTS["enabled"]):
            return
        text = str(message.text or "").strip()
        cfg = {**DEFAULTS, **dict(ctx.config or {})}
        create = _parse_create(text, cfg)
        handled = False
        try:
            if create is not None:
                handled = True
                if create.get("error"):
                    await client.send_message(message.chat.id, create["error"])
                else:
                    await _manager.create(client, message, create)
            elif text == str(cfg["status_word"]).strip():
                handled = True
                await _manager.status(client, message.chat.id)
            elif text == str(cfg["draw_word"]).strip():
                handled = True
                key = _activity_key(client, message.chat.id)
                if not await _manager.draw(key, reason="命令提前开奖"):
                    await client.send_message(message.chat.id, "这个群没有可以开奖的活动～")
            elif text == str(cfg["cancel_word"]).strip():
                handled = True
                key = _activity_key(client, message.chat.id)
                if not await _manager.cancel(key):
                    await client.send_message(message.chat.id, "这个群没有可以取消的抽奖～")
        except Exception as exc:  # noqa: BLE001
            ctx.log.error("处理抽奖命令失败：%r", exc)
            await client.send_message(message.chat.id, f"抽奖操作失败：{exc}")
        finally:
            if handled and cfg.get("delete_commands", True):
                await _safe_delete(message)

    @ctx.on_message(ctx.filters.incoming & ctx.filters.group & ctx.filters.text, group=5)
    async def on_participation(client, message):
        if not ctx.config.get("enabled", DEFAULTS["enabled"]):
            return
        try:
            await _manager.participate(client, message)
        except Exception as exc:  # noqa: BLE001
            ctx.log.error("记录抽奖参与者失败：%r", exc)

    @ctx.on_api("/activities", methods=["GET"])
    async def api_activities(req):
        return {"items": _manager.snapshot()}

    @ctx.on_api("/history", methods=["GET"])
    async def api_history(req):
        return {"items": _manager.history()}

    @ctx.on_api("/draw", methods=["POST"])
    async def api_draw(req):
        key = str((req.json or {}).get("key") or "")
        ok = bool(key) and await _manager.draw(key, reason="管理面板提前开奖")
        return {"ok": ok, "message": "已开奖" if ok else "活动不存在或已结束"}

    @ctx.on_api("/cancel", methods=["POST"])
    async def api_cancel(req):
        key = str((req.json or {}).get("key") or "")
        ok = bool(key) and await _manager.cancel(key, reason="管理面板取消")
        return {"ok": ok, "message": "已取消" if ok else "活动不存在或已结束"}

    ctx.log.info("人形抽奖插件已启用")


async def teardown(ctx):
    global _manager
    if _manager:
        _manager.close()
    _manager = None
    ctx.log.info("人形抽奖插件已停用")
