# =============================================================================
# AWBotNest 插件：删除自己的消息（self_delete）
#
# 由 .dme 命令触发：删除当前会话里自己最近发的若干条消息。
# 用法：/dme 10 或 .dme 10 —— 删除最近 10 条自己发的消息。
# =============================================================================

import asyncio
import re

__plugin__ = {
    "name": "删除自己消息",
    "id": "self_delete",
    "version": "1.0.2",
    "author": "AWdress",
    "description": "发送 /dme 数字 或 .dme 数字，删除当前会话里自己最近发的若干条消息。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "command": {
            "type": "string", "default": ".dme", "label": "触发命令",
            "section": "命令", "help": "自己发出、以此开头的消息会触发。/dme 与 .dme 等价。",
        },
        "tip_seconds": {
            "type": "slider", "default": 2, "label": "提示停留(秒)",
            "min": 0, "max": 10, "step": 1, "section": "完成提示",
            "help": "删除完成后的「已删除 N 条」提示停留多少秒再消失。",
        },
    },
}


def _parse(text: str, command: str):
    """匹配命令并取出数量。返回 (是否命中, 数量或None)。"""
    bare = re.escape(command.lstrip("/.").strip() or "dme")
    m = re.match(rf"^[/\.]{bare}(?:\s+(\d+))?\s*$", text or "", re.IGNORECASE)
    if not m:
        return False, None
    return True, (int(m.group(1)) if m.group(1) else None)


async def setup(ctx):
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-11)
    async def self_delete(client, message):
        cfg = ctx.config
        hit, count = _parse(message.text or "", cfg.get("command", ".dme"))
        if not hit:
            return

        cmd = cfg.get("command", ".dme")
        if count is None or count <= 0:
            return await message.edit(f"格式：{cmd} 数字\n例如：{cmd} 10")

        tip_secs = int(cfg.get("tip_seconds", 2) or 0)

        # 收集自己发的消息（排除命令消息本身）
        msgs = []
        try:
            me_id = client.me.id
            async for msg in client.get_chat_history(message.chat.id, limit=count + 100):
                if len(msgs) >= count:
                    break
                if msg.from_user and msg.from_user.id == me_id and msg.id != message.id:
                    msgs.append(msg.id)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("获取聊天历史失败: %r", e)

        if not msgs:
            await message.edit("没有找到要删除的消息")
            if tip_secs > 0:
                await asyncio.sleep(tip_secs)
            try:
                await message.delete()
            except Exception:
                pass
            return

        try:
            await client.delete_messages(message.chat.id, msgs)
            ctx.log.info("已删除 %d 条消息", len(msgs))
            await message.edit(f"已删除 {len(msgs)} 条消息")
            if tip_secs > 0:
                await asyncio.sleep(tip_secs)
            await message.delete()
        except Exception as e:  # noqa: BLE001
            ctx.log.error("删除消息失败: %r", e)


async def teardown(ctx):
    pass
