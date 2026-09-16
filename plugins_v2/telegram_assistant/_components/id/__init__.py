"""AWBotNest V2 原生查 ID 插件。"""
from __future__ import annotations
import asyncio

__plugin__ = {"id":"id","name":"查ID","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"发送 /id 或 .id（可回复某条消息）查询群组ID、用户ID、用户名。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png","tags":["身份查询","用户信息","Telegram账号"],"config_schema":{"delete_command":{"type":"boolean","default":True,"label":"删除命令消息","section":"功能开关","order":1},"command":{"type":"string","default":".id","label":"触发命令","section":"命令","order":10},"auto_delete":{"type":"number","default":20,"label":"结果自动删除(秒)","min":0,"max":120,"step":5,"section":"自动清理","order":11}},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 移除 V1 兼容运行层\n- 使用 Telethon 原生回复消息与实体接口\n- 自动删除任务纳入平台生命周期管理"}

def _commands(value):
    bare=str(value or "id").lstrip("/.").strip() or "id"
    return f"/{bare}".lower(),f".{bare}".lower()

def _format(chat_id,sender):
    user_id=getattr(sender,"id",None)
    if user_id:
        username=getattr(sender,"username",None)
        name=f"@{username}" if username else getattr(sender,"first_name",None)
        return f"**用户信息查询**\n\n群组ID: `{chat_id}`\n用户ID: `{user_id}`\n用户名: {name or '-'}\n\n点击ID数字即可复制"
    signature=getattr(sender,"author_signature",None)
    return f"**群组信息**\n\n群组ID: `{chat_id}`"+(f"\n作者签名: {signature}" if signature else "")+"\n\n点击ID数字即可复制"

async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def query_id(event):
        text=(event.raw_text or "").strip()
        if not text or text.split(maxsplit=1)[0].lower() not in _commands(ctx.config.get("command",".id")): return
        target=await event.get_reply_message() or event
        result=await event.reply(_format(int(event.chat_id),await target.get_sender()))
        delay=max(0,int(ctx.config.get("auto_delete",20) or 0))
        if delay:
            async def remove_later():
                await asyncio.sleep(delay)
                try: await result.delete()
                except Exception: pass
            ctx.create_task(remove_later(),name="id-auto-delete")
        if ctx.config.get("delete_command",True):
            try: await event.delete()
            except Exception: pass

async def teardown(ctx): ctx.log.info("[查ID] 已停用")
