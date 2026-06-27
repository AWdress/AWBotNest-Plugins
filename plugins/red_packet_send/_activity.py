# =============================================================================
# 发红包插件 - 活动管理（进程内内存 + 后台任务）
#
# 迁移自 AWLottery plugins/user/games/red_packet.py 的 InstantRedPacketMonitor
# （仅发包侧：创建活动 / 收参与 / 拼手气分配 / 发放 / 结算 / 状态 / 结束）。
#
# 不依赖 libs.others / 平台 service / DB：
#   - build_user_markdown_link → build_user_link（本文件自实现）
#   - is_user_in_send_blacklist → 插件 config 字段「屏蔽用户ID」（parse_blacklist）
# 活动状态为短时进程内内存 dict；后台任务（超时结算、延迟删消息）登记到集合，
# teardown 时统一 cancel。
# =============================================================================
from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Dict, List, Optional, Tuple

# 后台任务集合（超时结算 + 延迟删除），teardown 时统一 cancel
_BG_TASKS: set = set()


def _track(task: asyncio.Task) -> asyncio.Task:
    """登记后台任务，完成后自动从集合移除。"""
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return task


def cancel_all_tasks() -> None:
    """teardown 调用：取消所有后台任务。"""
    for t in list(_BG_TASKS):
        if not t.done():
            t.cancel()
    _BG_TASKS.clear()


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def build_user_link(uid: int, name: str) -> str:
    """构造 Telegram 用户 Markdown 链接（名字做 markdown 转义）。

    替代旧项目 libs.others.build_user_markdown_link。
    """
    name = name or str(uid)
    for ch in ("\\", "`", "*", "_", "[", "]", "(", ")", "~", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        name = name.replace(ch, f"\\{ch}")
    return f"[{name}](tg://user?id={uid})"


def parse_blacklist(raw) -> set:
    """解析屏蔽用户ID（支持换行或逗号分隔）。"""
    ids: set = set()
    for part in re.split(r"[,\s]+", str(raw or "")):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            pass
    return ids


def to_int(val, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def acct_id(client) -> int:
    """账号唯一标识（多账号隔离活动用）。"""
    me = getattr(client, "me", None)
    return me.id if me else id(client)


def is_create_command(
    text: str,
    reply_msg,
    create_word: str,
    max_amount: int,
    max_count: int,
) -> Optional[Tuple[float, int, str]]:
    """检查是否是创建红包命令。

    支持格式：
      <命令词> 总金额 红包数量 关键词
      <命令词> 总金额 红包数量          （回复贴图消息时，贴图即口令）
    返回 (总金额, 红包数量, 关键词) 或 None。
    """
    text = (text or "").strip()
    word = re.escape(create_word)

    # 回复贴图：<命令词> 金额 数量
    if reply_msg is not None and getattr(reply_msg, "sticker", None):
        m = re.match(rf"^{word}\s+(\d+(?:\.\d+)?)\s+(\d+)$", text)
        if m:
            total_amount = float(m.group(1))
            packet_count = int(m.group(2))
            if total_amount <= 0 or packet_count <= 0:
                return None
            if max_amount > 0 and total_amount > max_amount:
                return None
            if max_count > 0 and packet_count > max_count:
                return None
            try:
                file_id = reply_msg.sticker.file_id
                unique_id = reply_msg.sticker.file_unique_id
                if not file_id or not unique_id:
                    return None
                keyword = f"sticker:{file_id}:{unique_id}"
            except AttributeError:
                return None
            return total_amount, packet_count, keyword

    # 普通文本关键词：<命令词> 金额 数量 关键词
    m = re.match(rf"^{word}\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(.+)$", text)
    if m:
        total_amount = float(m.group(1))
        packet_count = int(m.group(2))
        keyword = m.group(3).strip()
        if total_amount <= 0 or packet_count <= 0 or not keyword:
            return None
        if len(keyword) > 100 or not keyword.isprintable():
            return None
        if max_amount > 0 and total_amount > max_amount:
            return None
        if max_count > 0 and packet_count > max_count:
            return None
        return total_amount, packet_count, keyword
    return None


def allocate_amount(activity: Dict) -> float:
    """拼手气分配：从剩余金额里随机切一份（分为单位，提高精度）。"""
    remaining_count = activity["remaining_count"]
    remaining_amount = activity["remaining_amount"]

    if remaining_count <= 0 or remaining_amount <= 0:
        return 0.0

    if remaining_count == 1:
        return max(0, round(remaining_amount, 2))

    remaining_cents = int(round(remaining_amount * 100))
    min_cents = 1
    max_cents = remaining_cents - (remaining_count - 1) * min_cents
    if max_cents <= min_cents:
        return 0.01

    allocated_cents = random.randint(
        min_cents, min(max_cents, remaining_cents // remaining_count * 2)
    )
    return round(allocated_cents / 100, 2)


# ─── 活动管理器 ──────────────────────────────────────────────────────────────

class ActivityManager:
    """拼手气红包活动管理器（发包侧）。

    活动以 (账号id, chat_id) 隔离，存进程内内存。每个活动：
      创建 → 群友回复口令/贴图参与 → 拼手气分配 → reply「+金额」发放 → 结算公布。
    超时（config 配置）自动结算；创建者可手动结束。
    """

    def __init__(self, ctx):
        self.ctx = ctx
        self.active: Dict[str, Dict] = {}            # key -> activity
        self.locks: Dict[str, asyncio.Lock] = {}     # key -> Lock
        self.cleanup_tasks: Dict[str, asyncio.Task] = {}

    # —— key 工具 ——
    @staticmethod
    def _key(client, chat_id: int) -> str:
        return f"{acct_id(client)}:{chat_id}"

    def _cfg(self, name, default):
        return self.ctx.config.get(name, default)

    # —— 创建活动 ——
    async def create_redpacket(self, client, message, params: Tuple[float, int, str]) -> bool:
        total_amount, packet_count, keyword = params
        total_amount = int(round(total_amount))
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        user_id = message.from_user.id if message.from_user else 0
        username = (
            (message.from_user.username or message.from_user.first_name)
            if message.from_user else str(user_id)
        )

        if key in self.active:
            await message.reply("当前群组已有进行中的红包活动，请等待活动结束后再创建新的活动。")
            return False

        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

        activity = {
            "client": client,
            "chat_id": chat_id,
            "creator_id": user_id,
            "creator_name": username,
            "total_amount": total_amount,
            "packet_count": packet_count,
            "remaining_count": packet_count,
            "remaining_amount": total_amount,
            "keyword": keyword,
            "participants": [],
            "distributed_amount": 0,
            "status": "进行中",
            "created_time": time.time(),
            "message_id": message.id,
            "msg_ids": [],   # 记录红包相关消息ID，用于结束后批量删除
        }
        self.active[key] = activity

        await self._schedule_cleanup(client, chat_id)

        reply_target_id = message.reply_to_message.id if message.reply_to_message else message.id

        if keyword.startswith("sticker:"):
            try:
                sticker_file_id = keyword.split(":", 2)[1]
                sticker_msg = await client.send_sticker(
                    chat_id=chat_id,
                    sticker=sticker_file_id,
                    reply_to_message_id=reply_target_id,
                )
                if sticker_msg:
                    activity["msg_ids"].append(sticker_msg.id)
                create_msg = (
                    f"🎉 幸运红包活动创建成功！\n"
                    f"📦 总金额：{total_amount} 魔力\n"
                    f"🎯 红包数量：{packet_count} 个\n"
                    f"🏷️ 参与方式：发送上方的贴图表情\n"
                    f"💡 发送相同的贴图即可参与抢红包！"
                )
                txt_msg = await client.send_message(
                    chat_id=chat_id,
                    text=create_msg,
                    reply_to_message_id=sticker_msg.id if sticker_msg else reply_target_id,
                )
                if txt_msg:
                    activity["msg_ids"].append(txt_msg.id)
            except Exception as e:  # noqa: BLE001
                self.ctx.log.warning("[发红包] 发送贴图失败，回退文本: %r", e)
                create_msg = (
                    f"🎉 幸运红包活动创建成功！\n"
                    f"📦 总金额：{total_amount} 魔力\n"
                    f"🎯 红包数量：{packet_count} 个\n"
                    f"🏷️ 参与方式：发送指定的贴图表情\n"
                    f"💡 回复原始消息查看参与贴图！"
                )
                txt_msg = await client.send_message(
                    chat_id=chat_id, text=create_msg, reply_to_message_id=reply_target_id
                )
                if txt_msg:
                    activity["msg_ids"].append(txt_msg.id)
        else:
            create_msg = (
                f"🎉 幸运红包活动创建成功！\n"
                f"📦 总金额：{total_amount} 魔力\n"
                f"🎯 红包数量：{packet_count} 个\n"
                f"🔑 参与关键词：{keyword}\n"
                f"💡 发送与关键词完全一致的消息即可参与抢红包！"
            )
            txt_msg = await client.send_message(
                chat_id=chat_id, text=create_msg, reply_to_message_id=reply_target_id
            )
            if txt_msg:
                activity["msg_ids"].append(txt_msg.id)

        self.ctx.log.info(
            "[发红包] 群 %s 创建活动：%s魔力/%s个，口令=%s", chat_id, total_amount, packet_count, keyword
        )
        return True

    # —— 自动超时结算 ——
    async def _schedule_cleanup(self, client, chat_id: int):
        key = self._key(client, chat_id)
        timeout_secs = max(1, to_int(self._cfg("activity_timeout_minutes", 30), 30)) * 60

        async def cleanup_expired():
            try:
                await asyncio.sleep(timeout_secs)
                activity = self.active.get(key)
                if activity and activity["status"] == "进行中":
                    self.ctx.log.warning("[发红包] 群 %s 活动超时，自动结束", chat_id)
                    await self.end_activity(client, chat_id)
            except asyncio.CancelledError:
                pass
            except Exception as e:  # noqa: BLE001
                self.ctx.log.error("[发红包] 活动清理任务异常: %r", e)
            finally:
                self.cleanup_tasks.pop(key, None)

        task = _track(asyncio.create_task(cleanup_expired()))
        self.cleanup_tasks[key] = task

    # —— 处理参与 ——
    async def handle_participation(self, client, message) -> bool:
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        if key not in self.active:
            return False

        user_id = message.from_user.id if message.from_user else 0
        username = (
            (message.from_user.username or message.from_user.first_name)
            if message.from_user else str(user_id)
        )
        text = message.text or ""

        # 屏蔽名单：这些用户不计入参与
        blacklist = parse_blacklist(self._cfg("blacklist_ids", ""))
        if user_id in blacklist:
            return False

        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

        async with self.locks[key]:
            activity = self.active.get(key)
            if not activity or activity["status"] != "进行中":
                return False
            if any(p["user_id"] == user_id for p in activity["participants"]):
                return False

            # 口令/贴图匹配
            keyword_matched = False
            if activity["keyword"].startswith("sticker:"):
                kw_parts = activity["keyword"].split(":", 2)
                sticker = message.sticker or (
                    message.reply_to_message.sticker if message.reply_to_message else None
                )
                if sticker and len(kw_parts) == 3:
                    keyword_matched = sticker.file_unique_id == kw_parts[2]
                elif sticker and len(kw_parts) >= 2:
                    keyword_matched = sticker.file_id == kw_parts[1]
            else:
                if activity["keyword"].lower() == text.lower().strip():
                    keyword_matched = True

            if not keyword_matched:
                return False

            amount = allocate_amount(activity)
            if amount <= 0:
                return False

            activity["participants"].append({
                "user_id": user_id,
                "username": username,
                "display_name": build_user_link(user_id, username),
                "amount": amount,
                "timestamp": time.time(),
            })
            activity["remaining_count"] -= 1
            activity["remaining_amount"] = max(0, round(activity["remaining_amount"] - amount, 2))
            activity["distributed_amount"] += amount

            await self._send_redpacket(client, message, username, amount)

            if activity["remaining_count"] <= 0:
                await self.end_activity(client, chat_id)
            return True

    # —— 发放红包（reply +金额 触发转账bot打款）——
    async def _send_redpacket(self, client, message, username: str, amount: float):
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        try:
            int_amount = int(round(amount))
            prefix = str(self._cfg("transfer_prefix", "+") or "+")
            congrats_tpl = self._cfg("congrats_text", "恭喜 {name} 抢到 {amount} 魔力！") \
                or "恭喜 {name} 抢到 {amount} 魔力！"

            # 先发简洁金额（+xxx），转账bot据此打款
            msg1 = await client.send_message(
                chat_id=chat_id,
                text=f"{prefix}{int_amount}",
                reply_to_message_id=message.id,
            )
            # 再发祝贺消息
            try:
                congrats = congrats_tpl.format(name=username, amount=int_amount)
            except (KeyError, IndexError, ValueError):
                congrats = f"恭喜 {username} 抢到 {int_amount} 魔力！"
            msg2 = await client.send_message(
                chat_id=chat_id, text=congrats, reply_to_message_id=message.id
            )

            activity = self.active.get(key)
            if activity:
                if msg1:
                    activity["msg_ids"].append(msg1.id)
                if msg2:
                    activity["msg_ids"].append(msg2.id)
        except Exception as e:  # noqa: BLE001
            self.ctx.log.error("[发红包] 发送红包失败: %r", e)
            try:
                await message.reply("发送红包时出现错误，请稍后重试。")
            except Exception:  # noqa: BLE001
                pass

    # —— 结束活动（结算公布 + 延迟批量删消息）——
    async def end_activity(self, client, chat_id: int):
        key = self._key(client, chat_id)
        activity = self.active.get(key)
        if not activity:
            return
        activity["status"] = "已结束"
        # client 可能为超时任务保存的引用
        client = client or activity.get("client")

        try:
            participants = activity["participants"]
            sorted_p = sorted(participants, key=lambda p: p["amount"], reverse=True)
            detail_lines = "\n".join(
                f"• {p['username']}：{int(round(p['amount']))} 魔力" for p in sorted_p
            )
            if sorted_p:
                best = sorted_p[0]
                lucky_line = f"\n\n🏆 手气最佳：{best['username']}（{int(round(best['amount']))} 魔力）"
            else:
                lucky_line = ""

            end_msg = (
                f"🎉 幸运红包活动已结束！\n"
                f"📊 活动统计：\n"
                f"👥 总参与人数：{len(participants)} 人\n"
                f"💰 总发放金额：{int(round(activity['distributed_amount']))} 魔力\n"
                f"📦 总红包数量：{activity['packet_count']} 个"
                + (f"\n\n🧧 领取明细：\n{detail_lines}" if detail_lines else "")
                + lucky_line
            )

            if client:
                try:
                    end_obj = await client.send_message(
                        chat_id, end_msg, reply_to_message_id=activity.get("message_id")
                    )
                except Exception:  # noqa: BLE001
                    end_obj = await client.send_message(chat_id, end_msg)
                if end_obj:
                    activity["msg_ids"].append(end_obj.id)

            # 延迟批量删除红包相关消息
            delay = to_int(self._cfg("end_delete_delay", 0), 0)
            if client and delay > 0 and activity.get("msg_ids"):
                ids_to_delete = list(activity["msg_ids"])

                async def _batch_delete(_c=client, _cid=chat_id, _ids=ids_to_delete, _d=delay):
                    try:
                        await asyncio.sleep(_d)
                        await _c.delete_messages(_cid, _ids)
                    except Exception:  # noqa: BLE001
                        pass

                _track(asyncio.create_task(_batch_delete()))

            self.ctx.log.info(
                "[发红包] 群 %s 活动结束，参与 %s 人，发放 %s 魔力",
                chat_id, len(participants), int(round(activity["distributed_amount"])),
            )
        except Exception as e:  # noqa: BLE001
            self.ctx.log.error("[发红包] 发送结算消息失败: %r", e)
        finally:
            self.active.pop(key, None)
            self.locks.pop(key, None)
            t = self.cleanup_tasks.pop(key, None)
            if t and not t.done():
                t.cancel()

    # —— 用户手动结束（仅创建者）——
    async def end_activity_by_user(self, client, message) -> bool:
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        activity = self.active.get(key)
        if not activity:
            await message.reply("当前群组没有进行中的红包活动")
            return False
        user_id = message.from_user.id if message.from_user else 0
        if activity["creator_id"] != user_id:
            await message.reply("❌ 只有红包创建者才能结束活动")
            return False
        await self.end_activity(client, chat_id)
        return True

    # —— 查询状态 ——
    async def get_activity_status(self, client, chat_id: int):
        key = self._key(client, chat_id)
        activity = self.active.get(key)
        if not activity:
            await client.send_message(chat_id, "当前群组没有进行中的红包活动")
            return
        participants = activity["participants"]

        if activity["keyword"].startswith("sticker:"):
            try:
                sticker_file_id = activity["keyword"].split(":", 2)[1]
                await client.send_sticker(chat_id, sticker_file_id)
                status_msg = (
                    f"🎉 幸运红包活动进行中\n"
                    f"📦 总金额：{activity['total_amount']} 魔力\n"
                    f"🎯 剩余红包：{activity['remaining_count']} 个\n"
                    f"👥 已参与：{len(participants)} 人\n"
                    f"🏷️ 参与方式：发送上方的贴图表情\n"
                    f"💰 剩余金额：{int(round(activity['remaining_amount']))} 魔力"
                )
            except Exception:  # noqa: BLE001
                status_msg = (
                    f"🎉 幸运红包活动进行中\n"
                    f"📦 总金额：{activity['total_amount']} 魔力\n"
                    f"🎯 剩余红包：{activity['remaining_count']} 个\n"
                    f"👥 已参与：{len(participants)} 人\n"
                    f"🏷️ 参与方式：发送指定的贴图表情\n"
                    f"💰 剩余金额：{int(round(activity['remaining_amount']))} 魔力"
                )
        else:
            status_msg = (
                f"🎉 幸运红包活动进行中\n"
                f"📦 总金额：{activity['total_amount']} 魔力\n"
                f"🎯 剩余红包：{activity['remaining_count']} 个\n"
                f"👥 已参与：{len(participants)} 人\n"
                f"🔑 参与关键词：\"{activity['keyword']}\"\n"
                f"💰 剩余金额：{int(round(activity['remaining_amount']))} 魔力"
            )
        try:
            await client.send_message(chat_id, status_msg)
        except Exception as e:  # noqa: BLE001
            self.ctx.log.error("[发红包] 发送状态消息失败: %r", e)

    # —— 全部结束（teardown）——
    def clear(self):
        for key in list(self.cleanup_tasks):
            t = self.cleanup_tasks.pop(key, None)
            if t and not t.done():
                t.cancel()
        self.active.clear()
        self.locks.clear()
