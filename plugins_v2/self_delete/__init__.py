"""AWBotNest V2 原生消息自删插件。"""
from __future__ import annotations
import asyncio
import re

__plugin__={"id":"self_delete","name":"删除自己消息","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"发送 /dme 数字 或 .dme 数字，删除当前会话里自己最近发的若干条消息。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cleanup.png","tags":["消息自删","批量清理","聊天管理"],"config_schema":{"command":{"type":"string","default":".dme","label":"触发命令","section":"基础配置","order":10},"tip_seconds":{"type":"number","default":2,"label":"提示停留(秒)","min":0,"max":10,"step":1,"section":"基础配置","order":11}},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 移除 V1 兼容运行层\n- 使用 Telethon 原生历史消息迭代和批量删除"}

def _count(text,command):
    bare=re.escape(str(command or "dme").lstrip("/.").strip() or "dme")
    match=re.fullmatch(rf"[/\.]{{1}}{bare}(?:\s+(\d+))?\s*",text or "",re.I)
    return None if not match else int(match.group(1) or 0)

async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def delete_own(event):
        count=_count(event.raw_text or "",ctx.config.get("command",".dme"))
        if count is None:return
        if count<=0:
            await event.edit(f"格式：{ctx.config.get('command','.dme')} 数字")
            return
        me=await event.client.get_me(); ids=[]
        async for message in event.client.iter_messages(event.chat_id,limit=count+100):
            if len(ids)>=count:break
            if message.id!=event.id and getattr(message,"sender_id",None)==me.id:ids.append(message.id)
        if ids:await event.client.delete_messages(event.chat_id,ids)
        await event.edit(f"已删除 {len(ids)} 条消息" if ids else "没有找到要删除的消息")
        delay=max(0,int(ctx.config.get("tip_seconds",2) or 0))
        if delay:await asyncio.sleep(delay)
        try:await event.delete()
        except Exception:pass

async def teardown(ctx):ctx.log.info("[删除自己消息] 已停用")
