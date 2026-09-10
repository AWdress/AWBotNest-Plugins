"""AWBotNest V2 原生 HDHive 抽奖插件。"""
from __future__ import annotations
import asyncio
import re
import time
from random import randint
__plugin__={"id":"hdhive_lottery","name":"HDHive抽奖","version":"2.0.1","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"自动参与 HDHive 抽奖：解析口令、随机等待参与、开奖检测中奖并通知。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/hdhive_lottery.jpg","tags":["HDHive抽奖","口令参与","中奖通知"],"config_schema":{"notify_owner":{"type":"boolean","default":True,"label":"参与/中奖通知我","section":"功能开关","order":1},"wait_min":{"type":"number","default":25,"label":"参与前最短等待(秒)","min":0,"max":300,"step":5,"section":"等待策略","order":10},"wait_max":{"type":"number","default":65,"label":"参与前最长等待(秒)","min":5,"max":600,"step":5,"section":"等待策略","order":11}},"resources":{"timeout_seconds":60,"max_concurrency":8,"max_background_tasks":64},"changelog":"v2.0.1 统一富文本表格通知\n- 参与、失败和中奖通知改为平台结构化表格\n\nv2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生消息与实体接口\n- 随机等待改为平台托管后台任务\n- 运行状态限制在当前插件实例并移除 V1 兼容层"}
_GROUP_ID=-1001379449445;_BOT_ID=5831593155;_TTL=259200
def _parse(text):
    prize=re.search(r"🏆\s*奖励[:：]\s*(.+)",text or "");keyword=re.search(r"🔑\s*参与口令[:：]\s*\n?\s*([\s\S]+?)(?:\n\s*[🏆👥🙋⏰👉🎁💡]|\Z)",text or "")
    return {"prize":prize.group(1).strip() if prize else "","keyword":keyword.group(1).strip() if keyword else ""}
def _link(chat_id,message_id):return f"https://t.me/c/{str(chat_id).removeprefix('-100')}/{message_id}"
async def setup(ctx):
    active={}
    async def participate(event,key,info,delay):
        await asyncio.sleep(delay)
        if key not in active:return
        try:
            await event.client.send_message(event.chat_id,info["keyword"])
            if ctx.config.get("notify_owner",True):await ctx.notify({"状态":"参与成功","奖品":info["prize"],"口令":info["keyword"],"来源":_link(event.chat_id,event.id)},level="success",category="HDHive抽奖",account=event.client)
        except asyncio.CancelledError:raise
        except Exception as error:
            ctx.log.error("[HDHive抽奖] 参与失败: %r",error)
            if ctx.config.get("notify_owner",True):await ctx.notify({"状态":"参与失败","奖品":info["prize"],"错误":type(error).__name__},level="error",category="HDHive抽奖",account=event.client)
    @ctx.on_message(chats=_GROUP_ID,incoming=True,outgoing=False)
    async def lottery(event):
        sender=await event.get_sender();text=event.raw_text or ""
        if getattr(sender,"id",None)!=_BOT_ID or not getattr(sender,"bot",False):return
        now=time.monotonic()
        for key in [key for key,value in active.items() if now-value["created"]>_TTL]:active.pop(key,None)
        if "发起了一个抽奖" in text and "参与口令" in text:
            info=_parse(text);key=f"{event.chat_id}:{event.id}"
            if not info["keyword"] or key in active:return
            active[key]={**info,"created":now};low=int(ctx.config.get("wait_min",25) or 0);high=int(ctx.config.get("wait_max",65) or 65)
            if low>high:low,high=high,low
            delay=randint(max(0,low),max(0,high));ctx.create_task(participate(event,key,info,delay),name=f"hdhive-lottery:{event.id}");return
        if "抽奖结果" not in text or "中奖名单" not in text:return
        winners=[(name.strip(),int(uid)) for name,uid in re.findall(r"\d+\.\s*(.+?)\s*[（(]\s*TGID[:：]\s*(\d+)\s*[)）]",text)]
        me=await event.client.get_me()
        if any(uid==me.id for _,uid in winners) and ctx.config.get("notify_owner",True):
            prize=(re.search(r"🏆\s*奖励[:：]\s*(.+)",text) or [None,""])[1].strip();await ctx.notify({"状态":"中奖","奖品":prize,"来源":_link(event.chat_id,event.id)},level="success",category="HDHive抽奖",account=event.client)
        active.clear()
async def teardown(ctx):ctx.log.info("[HDHive抽奖] 已停用")
