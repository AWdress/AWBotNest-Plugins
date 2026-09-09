"""AWBotNest V2 原生规则消息转发插件。"""
from __future__ import annotations
import asyncio
import re
import time

__plugin__={"id":"msg_forward","name":"消息转发","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"把来源会话的消息按规则转发到目标会话，支持多规则、类型、关键词、发送者过滤、相册及复制搬运。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png","tags":["消息转发","规则路由","跨群同步"],"config_schema":{"enable":{"type":"boolean","default":False,"label":"启用转发","section":"功能开关","order":1},"forward_album":{"type":"boolean","default":True,"label":"整组转发相册","section":"功能开关","order":2},"resolved_chat_names":{"type":"info","label":"已识别会话名称","section":"规则","order":9},"rules":{"type":"list","default":[],"label":"转发规则","item_label":"规则","section":"规则","order":10,"fields":{"source":{"type":"string","label":"来源会话"},"targets":{"type":"string","label":"转发到"},"types":{"type":"multiselect","label":"消息类型","default":[],"options":[{"value":"text","label":"文本"},{"value":"link","label":"链接"},{"value":"photo","label":"图片"},{"value":"video","label":"视频"},{"value":"document","label":"文件"},{"value":"audio","label":"音频"}]},"kw":{"type":"string","label":"关键词"},"nkw":{"type":"string","label":"排除词"},"sender":{"type":"string","label":"只转谁发的"},"copy":{"type":"boolean","label":"复制搬运","default":False}}}},"resources":{"timeout_seconds":120,"max_concurrency":8,"max_background_tasks":32},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生消息、相册与实体接口\n- 保留多规则过滤、原生转发和复制搬运\n- 移除 V1 兼容运行层"}

_URL_RE=re.compile(r"https?://",re.I)
def _split(raw):
    if isinstance(raw,(list,tuple,set)):return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or "").replace("，",",").split(",") if x.strip()]
def _peer(raw):
    value=str(raw or "").strip()
    if not value:return None
    if value.startswith("@"):return value
    try:return int(value)
    except ValueError:return None
def _label(entity,fallback):
    return getattr(entity,"title",None) or " ".join(filter(None,(getattr(entity,"first_name",None),getattr(entity,"last_name",None)))) or (f"@{entity.username}" if getattr(entity,"username",None) else str(fallback))
def _source_matches(chat_id,chat,source):
    if isinstance(source,int):return chat_id==source
    return bool(isinstance(source,str) and source.startswith("@") and (getattr(chat,"username","") or "").lower()==source[1:].lower())
def _has_media(message):return bool(getattr(message,"media",None))
def _type_ok(messages,text,types):
    if not types:return True
    for message in messages:
        if "text" in types and message.raw_text and not _has_media(message):return True
        if "photo" in types and getattr(message,"photo",None):return True
        if "video" in types and (getattr(message,"video",None) or getattr(message,"gif",None)):return True
        if "document" in types and getattr(message,"document",None):return True
        if "audio" in types and (getattr(message,"audio",None) or getattr(message,"voice",None)):return True
    return bool("link" in types and _URL_RE.search(text))
def _sender_ok(sender,filters):
    if not filters:return True
    for value in filters:
        low=value.lower()
        if low=="bot" and getattr(sender,"bot",False):return True
        if low.startswith("@") and (getattr(sender,"username","") or "").lower()==low[1:]:return True
        try:
            if getattr(sender,"id",None)==int(value):return True
        except ValueError:pass
    return False
def _passes(rule,messages,text,sender):
    if not _type_ok(messages,text,rule.get("types") or []):return False
    include=_split(rule.get("kw"));exclude=_split(rule.get("nkw"))
    return (not include or any(x in text for x in include)) and not any(x in text for x in exclude) and _sender_ok(sender,_split(rule.get("sender")))

async def _album(client,event):
    grouped=getattr(event,"grouped_id",None)
    if not grouped:return [event]
    await asyncio.sleep(.8)
    found=[]
    async for message in client.iter_messages(event.chat_id,min_id=max(0,event.id-20),max_id=event.id+20,reverse=True):
        if getattr(message,"grouped_id",None)==grouped:found.append(message)
    return found or [event]

async def _copy(client,target,messages):
    if len(messages)==1 and not messages[0].media:return await client.send_message(target,messages[0].raw_text or "")
    files=[]
    for message in messages:
        if message.media:files.append(await client.download_media(message,bytes))
    caption=next((m.raw_text for m in messages if m.raw_text),None)
    if files:return await client.send_file(target,files if len(files)>1 else files[0],caption=caption)
    return await client.send_message(target,caption or "")

async def setup(ctx):
    seen={};names={}
    async def resolve(client,target):
        key=str(target)
        if key not in names:
            try:names[key]=_label(await client.get_entity(target),target)
            except Exception:names[key]=key
        return names[key]
    if ctx.user:
        values=[]
        for rule in ctx.config.get("rules") or []:
            if isinstance(rule,dict):values.extend([p for key in ("source","targets") for p in (_peer(x) for x in _split(rule.get(key))) if p is not None])
        labels=[f"{await resolve(ctx.user,value)} ({value})" for value in dict.fromkeys(values)]
        if labels:ctx.update_config({"resolved_chat_names":", ".join(labels)})

    @ctx.on_message(incoming=True,outgoing=False)
    async def relay(event):
        cfg=ctx.config
        if not cfg.get("enable",False):return
        grouped=getattr(event,"grouped_id",None)
        if grouped and cfg.get("forward_album",True):
            now=time.monotonic()
            for key in [key for key,value in seen.items() if now-value>=60]:seen.pop(key,None)
            if grouped in seen:return
            seen[grouped]=now;messages=await _album(event.client,event)
        else:messages=[event]
        chat=await event.get_chat();sender=await event.get_sender();text=next((m.raw_text for m in messages if m.raw_text),"")
        for rule in cfg.get("rules") or []:
            if not isinstance(rule,dict):continue
            source=_peer(rule.get("source"))
            if source is None or not _source_matches(event.chat_id,chat,source) or not _passes(rule,messages,text,sender):continue
            for target in filter(lambda x:x is not None,(_peer(x) for x in _split(rule.get("targets")))):
                try:
                    if rule.get("copy"):await _copy(event.client,target,messages)
                    else:await event.client.forward_messages(target,messages if len(messages)>1 else messages[0])
                    ctx.log.info("[消息转发] %s (%s) -> %s (%s)",_label(chat,event.chat_id),event.chat_id,await resolve(event.client,target),target)
                except asyncio.CancelledError:raise
                except Exception as error:ctx.log.warning("[消息转发] 转发失败 %s -> %s: %r",event.chat_id,target,error)

async def teardown(ctx):ctx.log.info("[消息转发] 已停用")
