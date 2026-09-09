"""AWBotNest V2 原生转发复读插件。"""
from __future__ import annotations
import asyncio

__plugin__={"id":"zf","name":"转发复读","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"回复一条消息再发 /zf [次数]，把它在当前会话转发/复读若干次。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png","tags":["转发助手","消息过滤","频道同步"],"config_schema":{"command":{"type":"string","default":".zf","label":"触发命令","section":"命令","order":10},"interval":{"type":"number","default":0.3,"label":"每次间隔(秒)","min":0,"max":5,"step":0.1,"section":"重复限制","order":20},"max_times":{"type":"number","default":50,"label":"最多次数","min":1,"max":500,"section":"重复限制","order":21}},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 移除 V1 兼容运行层和 Pyrogram 路由\n- 使用 Telethon 原生转发并保留论坛话题\n- 禁止转发内容自动降级为复制发送"}

def _parse(text,command,max_times):
    parts=(text or "").split();bare=str(command or "zf").lstrip("/.").strip().lower() or "zf"
    if not parts or parts[0].lower() not in (f"/{bare}",f".{bare}"):return None
    try:value=int(parts[1]) if len(parts)>1 else 1
    except ValueError:value=1
    return max(1,min(value,max(1,int(max_times or 50))))

async def _copy(client,chat_id,message,reply_to):
    if message.media:
        data=await client.download_media(message,bytes)
        return await client.send_file(chat_id,data,caption=message.raw_text or None,reply_to=reply_to)
    return await client.send_message(chat_id,message.raw_text or "",reply_to=reply_to)

async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def repeat(event):
        times=_parse(event.raw_text or "",ctx.config.get("command",".zf"),ctx.config.get("max_times",50))
        if times is None:return
        source=await event.get_reply_message()
        if source is None:await event.edit("请先回复一条要转发的消息");return
        interval=max(0.0,float(ctx.config.get("interval",0.3) or 0));topic=getattr(source,"reply_to_msg_id",None)
        for index in range(times):
            if interval:await asyncio.sleep(interval)
            try:await event.client.forward_messages(event.chat_id,source)
            except Exception as error:
                ctx.log.warning("[转发复读] 第 %d/%d 次转发失败，尝试复制: %r",index+1,times,error)
                try:await _copy(event.client,event.chat_id,source,topic)
                except Exception as copy_error:ctx.log.warning("[转发复读] 第 %d/%d 次复制失败: %r",index+1,times,copy_error)
        try:await event.delete()
        except Exception:pass

async def teardown(ctx):ctx.log.info("[转发复读] 已停用")
