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
import os
import random
import re
import time
from typing import Dict, Optional, Tuple

from ._captcha import generate_code, render_captcha

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


async def _auto_delete(message, delay: int) -> None:
    """延迟删除一条消息（用于命令回执/提示等临时消息）。"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception:  # noqa: BLE001
        pass


async def delete_message(message) -> None:
    """立即删除一条消息（命令秒删用），失败静默。"""
    try:
        await message.delete()
    except Exception:  # noqa: BLE001
        pass


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
    create_word: str,
    max_amount: int,
    max_count: int,
) -> Optional[Tuple[float, int, Optional[str]]]:
    """检查是否是创建红包命令。

    格式（验证码模式，不再需要贴图）：
      <命令词> 总金额 红包数量                → 系统随机生成验证码图片
      <命令词> 总金额 红包数量 自定义口令      → 用自定义口令渲染成验证码图片
    口令均以图片形式呈现（防复制粘贴脚本），群友肉眼识别后打出内容才算参与。
    返回 (总金额, 红包数量, 自定义口令或None) 或 None。
    """
    text = (text or "").strip()
    word = re.escape(create_word)

    m = re.match(rf"^{word}\s+(\d+(?:\.\d+)?)\s+(\d+)(?:\s+(.+))?$", text, re.S)
    if not m:
        return None
    total_amount = float(m.group(1))
    packet_count = int(m.group(2))
    custom = (m.group(3) or "").strip()
    if total_amount <= 0 or packet_count <= 0:
        return None
    if max_amount > 0 and total_amount > max_amount:
        return None
    if max_count > 0 and packet_count > max_count:
        return None
    if custom:
        # 自定义口令：限长 + 单行（渲染成图片，太长图会过宽）
        custom = " ".join(custom.split())
        if len(custom) > 30:
            custom = custom[:30]
    return total_amount, packet_count, (custom or None)


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

    def _data_dir(self):
        """插件独享可写目录（存验证码临时图）。"""
        return getattr(self.ctx, "data_dir", ".")

    def _next_id(self) -> int:
        """全局递增红包编号（持久化到 kv，重启不重复，便于后期对照）。"""
        try:
            n = int(self.ctx.kv.get("rp_seq", 0) or 0) + 1
        except Exception:  # noqa: BLE001
            n = 1
        try:
            self.ctx.kv.set("rp_seq", n)
        except Exception:  # noqa: BLE001
            pass
        return n

    def _make_code(self, prefix: str = "") -> str:
        """生成参与口令：固定前缀 + 随机防挂码（无前缀时整体即随机验证码）。"""
        suffix = generate_code(to_int(self._cfg("code_length", 4), 4))
        return f"{prefix}{suffix}" if prefix else suffix

    # —— 创建活动 ——
    async def create_redpacket(self, client, message, params: Tuple[float, int, Optional[str]]) -> bool:
        total_amount, packet_count, custom_code = params
        total_amount = int(round(total_amount))
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        user_id = message.from_user.id if message.from_user else 0
        username = (
            (message.from_user.username or message.from_user.first_name)
            if message.from_user else str(user_id)
        )

        if key in self.active:
            notice = await client.send_message(
                chat_id, "当前群组已有进行中的红包活动，请等待活动结束后再创建。")
            if notice:
                _track(asyncio.create_task(_auto_delete(notice, 8)))
            return False

        if key not in self.locks:
            self.locks[key] = asyncio.Lock()

        # 口令即参与凭证：自定义口令做「固定前缀」，后面永远拼一段随机「防挂码」，
        # 整体渲染成扭曲图片防脚本。无自定义口令时整个就是随机验证码。
        prefix = custom_code or ""
        code = self._make_code(prefix)
        captcha_path = render_captcha(code, self._data_dir())
        rp_id = self._next_id()

        activity = {
            "client": client,
            "chat_id": chat_id,
            "rp_id": rp_id,
            "creator_id": user_id,
            "creator_name": username,
            "total_amount": total_amount,
            "packet_count": packet_count,
            "remaining_count": packet_count,
            "remaining_amount": total_amount,
            "keyword": code,            # 参与口令 = 前缀 + 随机防挂码（大小写不敏感匹配）
            "prefix": prefix,           # 自定义口令固定前缀，轮换时保留
            "captcha_path": captcha_path,
            "captcha_msg_id": None,      # 当前验证码图片消息ID（轮换时删旧发新）
            "custom": bool(custom_code),  # 是否带自定义口令前缀
            "participants": [],
            "distributed_amount": 0,
            "status": "进行中",
            "created_time": time.time(),
            "message_id": message.id,
            "msg_ids": [],   # 记录红包相关消息ID，用于结束后批量删除
        }
        self.active[key] = activity

        await self._schedule_cleanup(client, chat_id)

        # 命令本身待会儿删掉，只有当创建者是「回复某条消息」发的命令时才保留回复指向
        reply_target_id = message.reply_to_message.id if message.reply_to_message else None

        caption = (
            f"🧧 幸运红包  #{rp_id}\n"
            f"━━━━━━━━━━━━━\n"
            f"💰 总金额    {total_amount} 魔力\n"
            f"🎁 数量      {packet_count} 个\n"
            f"━━━━━━━━━━━━━\n"
            f"👉 识别上方验证码图片\n"
            f"　  发送图中完整字符即可参与（含随机防挂码，不区分大小写）"
        )

        sent_msg = None
        if captcha_path:
            try:
                sent_msg = await client.send_photo(
                    chat_id=chat_id,
                    photo=captcha_path,
                    caption=caption,
                    reply_to_message_id=reply_target_id,
                )
            except Exception as e:  # noqa: BLE001
                self.ctx.log.warning("[发红包] 发送验证码图片失败，回退文本: %r", e)

        if sent_msg is None:
            # PIL 缺失或发图失败：降级为文本公布验证码（仍可玩，防脚本能力下降）
            sent_msg = await client.send_message(
                chat_id=chat_id,
                text=(
                    f"🧧 幸运红包  #{rp_id}\n"
                    f"━━━━━━━━━━━━━\n"
                    f"💰 总金额    {total_amount} 魔力\n"
                    f"🎁 数量      {packet_count} 个\n"
                    f"🔑 口令      {code}\n"
                    f"━━━━━━━━━━━━━\n"
                    f"👉 发送与口令一致的消息即可参与（不区分大小写）"
                ),
                reply_to_message_id=reply_target_id,
            )
        if sent_msg:
            activity["msg_ids"].append(sent_msg.id)
            activity["captcha_msg_id"] = sent_msg.id

        self.ctx.log.info(
            "[发红包] 群 %s 创建活动 #%s：%s魔力/%s个，验证码=%s",
            chat_id, rp_id, total_amount, packet_count, code,
        )
        return True

    # —— 轮换验证码（每抢一个换一个，防复制粘贴）——
    async def _rotate_captcha(self, client, chat_id: int, activity: Dict):
        """删掉旧验证码消息/图片，随机生成新验证码并重新发图。仅随机模式生效。"""
        # 删旧消息 + 旧图
        old_mid = activity.get("captcha_msg_id")
        if old_mid:
            try:
                await client.delete_messages(chat_id, old_mid)
            except Exception:  # noqa: BLE001
                pass
            if old_mid in activity.get("msg_ids", []):
                try:
                    activity["msg_ids"].remove(old_mid)
                except ValueError:
                    pass
        old_path = activity.get("captcha_path")
        if old_path:
            try:
                os.remove(old_path)
            except OSError:
                pass

        code = self._make_code(activity.get("prefix", ""))
        activity["keyword"] = code
        path = render_captcha(code, self._data_dir())
        activity["captcha_path"] = path
        rp_id = activity.get("rp_id", 0)
        caption = (
            f"🧧 幸运红包  #{rp_id} · 新验证码\n"
            f"━━━━━━━━━━━━━\n"
            f"⚠️ 上一个验证码已失效\n"
            f"🎁 剩余      {activity['remaining_count']} / {activity['packet_count']} 个\n"
            f"━━━━━━━━━━━━━\n"
            f"👉 识别上图新验证码，发送图中字符参与（不区分大小写）"
        )
        sent = None
        if path:
            try:
                sent = await client.send_photo(chat_id, path, caption=caption)
            except Exception as e:  # noqa: BLE001
                self.ctx.log.warning("[发红包] 轮换验证码发图失败，回退文本: %r", e)
        if sent is None:
            sent = await client.send_message(
                chat_id,
                f"🧧 幸运红包  #{rp_id} · 新验证码\n"
                f"⚠️ 上一个已失效\n🔑 新口令：{code}\n"
                f"🎁 剩余 {activity['remaining_count']} / {activity['packet_count']} 个",
            )
        if sent:
            activity["captcha_msg_id"] = sent.id
            activity["msg_ids"].append(sent.id)

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

            # 验证码匹配（不区分大小写、去首尾空白）
            if activity["keyword"].strip().lower() != text.strip().lower():
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
            elif self._cfg("rotate_code", False):
                # 每抢一个换一个防挂码：上一个立即失效，防复制粘贴/脚本
                # （有自定义口令时保留口令前缀，只换后面的随机段）
                await self._rotate_captcha(client, chat_id, activity)
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
            activity = self.active.get(key)
            rp_id = activity.get("rp_id", 0) if activity else 0

            # 先发简洁金额（+xxx），转账bot据此打款（此条务必保持纯金额，勿加装饰）
            msg1 = await client.send_message(
                chat_id=chat_id,
                text=f"{prefix}{int_amount}",
                reply_to_message_id=message.id,
            )
            # 再发祝贺消息（带红包编号，便于事后对照打款记录）
            try:
                congrats = congrats_tpl.format(name=username, amount=int_amount, id=rp_id)
            except (KeyError, IndexError, ValueError):
                congrats = f"恭喜 {username} 抢到 {int_amount} 魔力！"
            congrats = f"🧧 #{rp_id}｜{congrats}"
            msg2 = await client.send_message(
                chat_id=chat_id, text=congrats, reply_to_message_id=message.id
            )

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
            rp_id = activity.get("rp_id", 0)
            sorted_p = sorted(participants, key=lambda p: p["amount"], reverse=True)
            medals = ["🥇", "🥈", "🥉"]
            detail_lines = "\n".join(
                f"{medals[i] if i < 3 else '　•'} {p['username']}　{int(round(p['amount']))} 魔力"
                for i, p in enumerate(sorted_p)
            )
            if sorted_p:
                best = sorted_p[0]
                lucky_line = f"\n\n🏆 手气最佳：{best['username']}（{int(round(best['amount']))} 魔力）"
            else:
                lucky_line = ""

            end_msg = (
                f"🧧 幸运红包  #{rp_id} · 已结束\n"
                f"━━━━━━━━━━━━━\n"
                f"👥 参与人数  {len(participants)} 人\n"
                f"💵 发放金额  {int(round(activity['distributed_amount']))} 魔力\n"
                f"🎁 红包个数  {activity['packet_count']} 个"
                + (f"\n━━━━━━━━━━━━━\n📋 领取明细\n{detail_lines}" if detail_lines else "")
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
            # 清理验证码临时图片
            cpath = activity.get("captcha_path")
            if cpath:
                try:
                    os.remove(cpath)
                except OSError:
                    pass

    # —— 用户手动结束（仅创建者）——
    async def end_activity_by_user(self, client, message) -> bool:
        chat_id = message.chat.id
        key = self._key(client, chat_id)
        activity = self.active.get(key)
        if not activity:
            notice = await client.send_message(chat_id, "当前群组没有进行中的红包活动")
            if notice:
                _track(asyncio.create_task(_auto_delete(notice, 8)))
            return False
        user_id = message.from_user.id if message.from_user else 0
        if activity["creator_id"] != user_id:
            notice = await client.send_message(chat_id, "只有红包创建者才能结束活动")
            if notice:
                _track(asyncio.create_task(_auto_delete(notice, 8)))
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
        rp_id = activity.get("rp_id", 0)

        header = f"🧧 幸运红包  #{rp_id} · 进行中"
        stat_lines = (
            f"━━━━━━━━━━━━━\n"
            f"💰 总金额    {activity['total_amount']} 魔力\n"
            f"🎁 剩余      {activity['remaining_count']} / {activity['packet_count']} 个\n"
            f"💵 剩余金额  {int(round(activity['remaining_amount']))} 魔力\n"
            f"👥 已参与    {len(participants)} 人"
        )
        captcha_path = activity.get("captcha_path")

        # 优先重发验证码图片（让后来者也能看清），不在文本里泄露验证码
        if captcha_path and os.path.exists(captcha_path):
            caption = (
                f"{header}\n{stat_lines}\n"
                f"━━━━━━━━━━━━━\n"
                f"👉 识别上图验证码，发送图中字符参与（不区分大小写）"
            )
            try:
                await client.send_photo(chat_id, captcha_path, caption=caption)
                return
            except Exception as e:  # noqa: BLE001
                self.ctx.log.warning("[发红包] 状态重发验证码图失败，回退文本: %r", e)

        # 图片不可用：文本模式下公布口令
        status_msg = (
            f"{header}\n{stat_lines}\n"
            f"🔑 参与口令  {activity['keyword']}"
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
        for activity in self.active.values():
            cpath = activity.get("captcha_path")
            if cpath:
                try:
                    os.remove(cpath)
                except OSError:
                    pass
        self.active.clear()
        self.locks.clear()
