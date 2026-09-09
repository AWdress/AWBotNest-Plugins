"""AWBotNest V2 原生 115 搜索结果转发插件。"""
from __future__ import annotations
__plugin__={"id":"trans115search","name":"115搜索结果转发","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"监听来源会话里机器人发送的列表消息，并转发到指定目标会话。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cloud_media.png","tags":["115资源搜索","网盘检索","列表转发"],"config_schema":{"resolved_chat_names":{"type":"info","label":"已识别会话名称","section":"基本配置","order":9},"source_chat_id":{"type":"chat","default":-1002466900287,"label":"来源会话ID","section":"基本配置","order":10,"chat_types":["group","channel"],"multi":False},"target_chat_id":{"type":"chat","default":0,"label":"转发到会话ID","section":"基本配置","order":11,"chat_types":["group","channel"],"multi":False},"keyword":{"type":"string","default":"列表","label":"触发关键词","section":"基本配置","order":12}},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生实体与格式实体发送\n- 保留来源、目标名称解析和机器人过滤\n- 移除 V1 兼容运行层"}
def _peer(raw):
    value=str(raw or "").strip()
    if not value:return None
    if value.startswith("@"):return value
    try:return int(value)
    except ValueError:return None
def _label(entity,fallback):return getattr(entity,"title",None) or getattr(entity,"first_name",None) or (f"@{entity.username}" if getattr(entity,"username",None) else str(fallback))
async def _name(client,value):
    try:return _label(await client.get_entity(value),value)
    except Exception:return str(value)
async def setup(ctx):
    source=_peer(ctx.config.get("source_chat_id"));target=_peer(ctx.config.get("target_chat_id"))
    if ctx.user:
        labels=[]
        for prefix,value in (("来源",source),("目标",target)):
            if value is not None:labels.append(f"{prefix}: {await _name(ctx.user,value)} ({value})")
        if labels:ctx.update_config({"resolved_chat_names":"；".join(labels)})
    @ctx.on_message(incoming=True,outgoing=False)
    async def forward(event):
        source=_peer(ctx.config.get("source_chat_id"));target=_peer(ctx.config.get("target_chat_id"))
        if source is None or target is None:return
        chat=await event.get_chat()
        if isinstance(source,int):matched=event.chat_id==source
        else:matched=(getattr(chat,"username","") or "").lower()==source[1:].lower()
        if not matched:return
        sender=await event.get_sender()
        if not getattr(sender,"bot",False):return
        text=event.raw_text or "";keyword=str(ctx.config.get("keyword","列表") or "")
        if keyword and keyword not in text:return
        client=ctx.bot or event.client
        try:
            await client.send_message(target,text,formatting_entities=getattr(event.message,"entities",None),link_preview=False)
            ctx.log.info("[115列表转发] %s (%s) -> %s (%s)",_label(chat,event.chat_id),event.chat_id,await _name(event.client,target),target)
        except Exception as error:ctx.log.warning("[115列表转发] 转发失败 %s -> %s: %r",event.chat_id,target,error)
async def teardown(ctx):ctx.log.info("[115列表转发] 已停用")
