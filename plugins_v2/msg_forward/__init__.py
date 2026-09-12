"""AWBotNest V2 原生消息转发助手。"""
from __future__ import annotations
import asyncio
import re
import time

__plugin__ = {
    "id": "msg_forward",
    "name": "消息转发助手",
    "version": "2.1.5",
    "author": "AWdress",
    "scope": "user",
    "plugin_api_version": 2,
    "requirements": [],
    "render_mode": "schema",
    "description": "统一提供规则转发、复制搬运、历史遗漏补全和回复复读；兼容迁移原“转发复读”配置。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png",
    "tags": ["消息转发", "规则路由", "转发复读"],
    "config_schema": {
        "enable": {
            "type": "boolean", "default": False, "label": "启用规则转发",
            "section": "功能开关", "order": 1,
        },
        "forward_album": {
            "type": "boolean", "default": True, "label": "整组转发相册",
            "section": "功能开关", "order": 2,
        },
        "backfill_limit": {
            "type": "integer", "default": 100, "min": 1, "max": 500, "step": 1,
            "label": "遗漏补全回查条数",
            "help": "执行“补全遗漏”时每条规则最多回查的来源消息数。",
            "section": "功能开关", "order": 3,
        },
        "auto_backfill": {
            "type": "boolean", "default": True, "label": "自动检查遗漏",
            "help": "插件启用或重载后立即回查，之后按设定间隔自动补发遗漏消息。",
            "section": "功能开关", "order": 4,
        },
        "backfill_interval_min": {
            "type": "number", "default": 10, "min": 1, "max": 1440, "step": 1,
            "label": "遗漏检查间隔（分钟）",
            "section": "功能开关", "order": 5,
        },
        "repeat_enabled": {
            "type": "boolean", "default": True, "label": "启用回复复读",
            "help": "回复一条消息并发送复读命令，在当前会话重复转发或复制。",
            "section": "回复复读", "order": 20,
        },
        "repeat_command": {
            "type": "string", "default": ".zf", "label": "复读命令",
            "help": "填写 .zf、/zf 或 zf 均可；实际同时接受点号和斜杠前缀。",
            "section": "回复复读", "order": 21,
        },
        "repeat_mode": {
            "type": "boolean", "default": False, "label": "复制重发",
            "help": "关闭时使用原样转发；开启时复制消息内容后重新发送。旧版 forward/copy 配置会自动转换。",
            "section": "回复复读", "order": 22,
        },
        "repeat_interval": {
            "type": "number", "default": 0.3, "min": 0, "max": 5, "step": 0.1,
            "label": "每次间隔（秒）", "section": "回复复读", "order": 23,
        },
        "repeat_max_times": {
            "type": "number", "default": 50, "min": 1, "max": 500, "step": 1,
            "label": "最多复读次数", "section": "回复复读", "order": 24,
        },
        "resolved_chat_names": {
            "type": "info", "label": "已识别会话名称", "section": "规则", "order": 29,
        },
        "rules": {
            "type": "list", "default": [], "label": "转发规则", "item_label": "规则",
            "section": "规则", "order": 30,
            "fields": {
                "source": {"type": "string", "label": "来源会话"},
                "targets": {"type": "string", "label": "转发到"},
                "types": {
                    "type": "multiselect", "label": "消息类型", "default": [],
                    "options": [
                        {"value": "text", "label": "文本"},
                        {"value": "link", "label": "链接"},
                        {"value": "photo", "label": "图片"},
                        {"value": "video", "label": "视频"},
                        {"value": "document", "label": "文件"},
                        {"value": "audio", "label": "音频"},
                    ],
                },
                "kw": {"type": "string", "label": "关键词"},
                "nkw": {"type": "string", "label": "排除词"},
                "sender": {"type": "string", "label": "只转谁发的"},
                "copy": {"type": "boolean", "label": "复制搬运", "default": False},
            },
        },
        "backfill": {
            "type": "action", "label": "立即检查遗漏", "action": "backfill",
            "help": "自动检查之外，可随时立即按当前规则回查一次；持久化去重后只补发遗漏内容。",
            "section": "维护", "order": 40,
        },
    },
    "resources": {"timeout_seconds": 120, "max_concurrency": 8, "max_background_tasks": 32},
    "changelog": "v2.1.5 适配平台正式调度与整数配置规范\n- 自动遗漏检查直接使用 schedule_interval 注册\n- 遗漏补全回查条数声明为 integer，不再触发配置类型错误\n- 不再探测或静默跳过平台调度能力\n\n"
    "v2.1.4 恢复合并前的复制与转发语义\n- 复制搬运恢复为 Telegram 服务端无署名复制，不再下载图片后重新上传\n- 原样转发继续保留来源标记，两种模式严格按规则执行且不再相互降级\n- 复制与转发只有取得目标消息 ID 才记录成功，失败消息继续由遗漏检查重试\n- 升级后每条复制规则仅重新检查最新一条旧记录，修复 2.1.3 已误记的降级转发且避免批量重复\n\n"
    "v2.1.3 修复历史媒体漏发与立即检查反馈\n- 媒体复制的下载或上传请求失败时自动降级为原样转发，不再因 Telegram 重试耗尽直接漏发\n- 原生转发返回空结果时继续尝试消息 ID 路径，所有路径均无有效结果时不再误记成功\n- 补全日志显示实际投递模式，立即检查按钮点击后马上记录受理或占用状态\n\n"
    "v2.1.2 修复原样转发、配置显示与遗漏补全\n- 复读方式改为清晰的“复制重发”开关，关闭即为原样转发，并自动转换旧配置\n- 原样转发优先使用 Telethon 原生 Message，来源实体不完整时不再直接失败\n- 两种原样转发路径均失败时自动复制补发，并在日志中显示实际投递模式\n- 插件启用或重载后立即自动回查遗漏，之后按配置间隔持续检查并持久化去重\n\n"
    "v2.1.1 调整插件名称\n- 更名为更直观的“消息转发助手”\n- 插件 ID、已有配置、运行状态和全部功能保持不变\n\n"
    "v2.1.0 合并消息转发与转发复读\n- 合并原“消息转发”和“转发复读”，统一提供规则路由、复制搬运、遗漏补全与回复复读\n- 自动迁移 zf 的命令、间隔、次数和账号选择，并停用旧插件避免重复执行\n- 配置页完整展示复读模式及遗漏补全动作，配置字段均使用平台支持的类型\n\n"
    "v2.0.6 修复遗漏补全数值配置\n- backfill_limit 改用平台支持的 number 类型并限制为整数步进\n- 兼容已有数字值，运行时继续执行 1 至 500 的整数边界保护\n\n"
    "v2.0.5 修复原生转发无响应\n- 改用来源会话与消息 ID 调用 Telethon 转发，兼容单条消息和相册\n- 原生转发返回空结果时自动降级为复制搬运\n- 来源频道禁止转发时记录原因并自动复制补发\n\n"
    "v2.0.4 修复复制搬运图片变成 unnamed 文件\n- 内存下载后恢复媒体文件名与扩展名，图片继续按 Telegram 照片发送\n- 文件、视频、音频按原媒体类型设置发送参数，并保留说明文字实体\n\n"
    "v2.0.3 修复市场重复显示更新\n- 将最终版本、描述、遗漏补全配置和 changelog 写入平台可静态读取的元数据\n- 平台扫描版本与市场清单保持一致，不再反复提示更新\n\n"
    "v2.0.2 新增历史遗漏补全\n- 增加‘补全遗漏’动作，按现有规则回查来源历史消息并补发\n- 以来源消息 ID 持久化去重，重复执行不会重复发送\n- 支持相册整组补发、关键词/类型/发送者过滤和复制搬运\n\n"
    "v2.0.1 修复 Telethon 媒体与事件转发\n- 单消息和相册统一传递原生 Message，避免 Event 类型不受支持\n- 媒体下载失败时回退原生转发，不再向 send_file 传入 None\n\n"
    "v2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生消息、相册与实体接口\n- 保留多规则过滤、原生转发和复制搬运\n- 移除 V1 兼容运行层",
}

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
def _parse_repeat(text,command,max_times):
    parts=(text or "").split()
    bare=str(command or "zf").lstrip("/.").strip().lower() or "zf"
    if not parts or parts[0].lower() not in (f"/{bare}",f".{bare}"):return None
    try:value=int(parts[1]) if len(parts)>1 else 1
    except (TypeError,ValueError):value=1
    try:limit=max(1,min(int(max_times or 50),500))
    except (TypeError,ValueError):limit=50
    return max(1,min(value,limit))
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
    if not grouped:return [event.message]
    await asyncio.sleep(.8)
    found=[]
    async for message in client.iter_messages(event.chat_id,min_id=max(0,event.id-20),max_id=event.id+20,reverse=True):
        if getattr(message,"grouped_id",None)==grouped:found.append(message)
    return found or [event.message]

def _delivery_ids(result):
    """只把带 Telegram 消息 ID 的发送结果视为已实际投递。"""
    items=result if isinstance(result,(list,tuple)) else [result]
    direct=[int(value) for item in items if item is not None
            for value in [getattr(item,"id",None)] if isinstance(value,int) and value>0]
    if direct:return direct
    message_ids=[];fallback_ids=[]
    for update in getattr(result,"updates",None) or []:
        message=getattr(update,"message",None)
        value=getattr(message,"id",None)
        if isinstance(value,int) and value>0:message_ids.append(value)
        elif update.__class__.__name__=="UpdateMessageID":
            value=getattr(update,"id",None)
            if isinstance(value,int) and value>0:fallback_ids.append(value)
    return message_ids or fallback_ids

async def _history_entity(client,value):
    """历史回查优先使用本地实体缓存，避免 get_entity 额外请求反复失败。"""
    get_input_entity=getattr(client,"get_input_entity",None)
    if callable(get_input_entity):
        try:return await get_input_entity(value)
        except asyncio.CancelledError:raise
        except Exception:pass
    return await client.get_entity(value)

async def _server_forward(client,target,messages,*,drop_author,top_msg_id=None):
    """复刻 V1 copy/forward：由 Telegram 服务端按消息 ID 复制或转发。"""
    from telethon.helpers import generate_random_long
    from telethon.tl.functions.messages import ForwardMessagesRequest

    ids=[getattr(message,"id",None) for message in messages]
    if not ids or not all(isinstance(value,int) and value>0 for value in ids):
        raise RuntimeError("无法取得来源消息 ID")
    source=None
    get_input_chat=getattr(messages[0],"get_input_chat",None)
    if callable(get_input_chat):
        try:source=await get_input_chat()
        except asyncio.CancelledError:raise
        except Exception:source=None
    source=source or getattr(messages[0],"_input_chat",None)
    source=source or getattr(messages[0],"peer_id",None) or getattr(messages[0],"chat_id",None)
    if source is None:raise RuntimeError("无法取得来源会话")
    get_input_entity=getattr(client,"get_input_entity",None)
    if callable(get_input_entity):
        source=await get_input_entity(source)
        target=await get_input_entity(target)
    result=await client(ForwardMessagesRequest(
        from_peer=source,
        id=ids,
        random_id=[generate_random_long() for _ in ids],
        to_peer=target,
        top_msg_id=int(top_msg_id) if top_msg_id else None,
        drop_author=bool(drop_author),
    ))
    if not _delivery_ids(result):
        mode="复制搬运" if drop_author else "原样转发"
        raise RuntimeError(f"{mode}未返回目标消息 ID")
    return result

async def _native_forward(client,target,messages,top_msg_id=None):
    """恢复合并前的 Telethon 高级转发；论坛话题才使用底层请求。"""
    if top_msg_id:
        return await _server_forward(
            client,target,messages,drop_author=False,top_msg_id=top_msg_id,
        )
    ids=[getattr(message,"id",None) for message in messages]
    if not ids or not all(isinstance(value,int) and value>0 for value in ids):
        raise RuntimeError("无法取得来源消息 ID")
    source=None
    get_input_chat=getattr(messages[0],"get_input_chat",None)
    if callable(get_input_chat):
        try:source=await get_input_chat()
        except asyncio.CancelledError:raise
        except Exception:source=None
    source=source or getattr(messages[0],"_input_chat",None)
    source=source or getattr(messages[0],"peer_id",None) or getattr(messages[0],"chat_id",None)
    if source is None:raise RuntimeError("无法取得来源会话")
    payload=ids[0] if len(ids)==1 else ids
    result=await client.forward_messages(target,payload,from_peer=source)
    if not _delivery_ids(result):raise RuntimeError("原样转发未返回目标消息 ID")
    return result

async def _forward(client,target,messages,log=None,delivery=None):
    """严格执行原样转发，不改变规则选定的模式。"""
    result=await _native_forward(client,target,messages)
    if delivery is not None:
        delivery["mode"]="原样转发"
        delivery["message_ids"]=_delivery_ids(result)
    return result

async def _copy(client,target,messages,reply_to=None,log=None,delivery=None):
    """严格执行 Telegram 服务端无署名复制，不下载媒体且不降级。"""
    result=await _server_forward(
        client,target,messages,drop_author=True,top_msg_id=reply_to,
    )
    if delivery is not None:
        delivery["mode"]="复制搬运"
        delivery["message_ids"]=_delivery_ids(result)
    return result

def _repeat_topic(event,source):
    """取得论坛话题根消息；普通回复不被误当成话题。"""
    for message in (getattr(event,"message",None),source):
        header=getattr(message,"reply_to",None)
        top=getattr(header,"reply_to_top_id",None)
        if top:return top
        if getattr(header,"forum_topic",False):
            value=getattr(header,"reply_to_msg_id",None)
            if value:return value
    return None

async def _repeat_forward(client,chat_id,source,topic_id=None):
    """原样转发回复消息，并保持论坛话题位置。"""
    return await _native_forward(client,chat_id,[source],top_msg_id=topic_id)

def _migrate_zf_config(ctx):
    """一次性吸收旧 zf 配置，并从恢复列表停用旧插件避免重复复读。"""
    settings=getattr(ctx,"settings",None)
    plugin_config=getattr(settings,"plugin_config",None)
    if not isinstance(plugin_config,dict):return False
    legacy=plugin_config.get("zf")
    if not isinstance(legacy,dict):return False
    current=plugin_config.get("msg_forward")
    current=current if isinstance(current,dict) else {}
    mapping={"command":"repeat_command","interval":"repeat_interval","max_times":"repeat_max_times"}
    updates={target:legacy[source] for source,target in mapping.items() if source in legacy and target not in current}
    if "repeat_enabled" not in current:updates["repeat_enabled"]=True
    changed=bool(updates)
    accounts=getattr(settings,"plugin_accounts",None)
    if isinstance(accounts,dict) and not accounts.get("msg_forward") and accounts.get("zf"):
        accounts["msg_forward"]=list(accounts["zf"])
        changed=True
    enabled=getattr(settings,"enabled_plugins",None)
    if isinstance(enabled,list) and "zf" in enabled:
        enabled.remove("zf")
        changed=True
    if not changed:return False
    ctx.update_config(updates)
    ctx.log.info("[消息转发助手] 已迁移旧“转发复读”配置并停用旧插件")
    return True

def _normalize_repeat_mode(ctx):
    """把旧版 select 保存的 forward/copy 原地转换为新版布尔开关。"""
    raw=ctx.config.get("repeat_mode",False)
    if not isinstance(raw,str):return False
    value=raw.strip().lower()=="copy"
    ctx.update_config({"repeat_mode":value})
    ctx.log.info("[消息转发助手] 已将旧复读方式配置转换为%s", "复制重发" if value else "原样转发")
    return True

def _latest_legacy_copy_keys(rules,sent):
    """每个复制目标只挑最新旧检查点，避免升级修复造成整批历史重复。"""
    selected=set()
    for rule in rules or []:
        if not isinstance(rule,dict) or not rule.get("copy"):continue
        source=_peer(rule.get("source"))
        if source is None:continue
        for target in filter(lambda value:value is not None,(_peer(x) for x in _split(rule.get("targets")))):
            prefix=f"{source}:{target}:"
            candidates=[]
            for key in sent:
                if not key.startswith(prefix):continue
                try:ids=tuple(int(value) for value in key[len(prefix):].split(","))
                except (TypeError,ValueError):continue
                if ids:candidates.append((max(ids),ids,key))
            if candidates:selected.add(max(candidates)[2])
    return selected

async def _backfill(client, rules, limit, sent, log, resolve, forward_album=True):
    """回查来源历史并补发遗漏消息，返回 (sent_count, skipped_count)。"""
    sent_count = skipped = 0
    limit = max(1, min(int(limit or 100), 500))
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        source = _peer(rule.get("source"))
        if source is None:
            log.warning("[消息转发助手] 规则 %s 来源无效，已跳过", index + 1)
            continue
        try:
            source_entity = await _history_entity(client,source)
            source_id = getattr(source_entity, "id", source)
            groups = {}
            async for message in client.iter_messages(source_entity, limit=limit):
                if getattr(message, "action", None) is not None:
                    continue
                gid = getattr(message, "grouped_id", None)
                key = ("album", gid) if gid and forward_album else ("message", getattr(message, "id", 0))
                groups.setdefault(key, []).append(message)
            # iter_messages yields newest first; send oldest first.
            for messages in reversed(list(groups.values())):
                messages = sorted(messages, key=lambda m: getattr(m, "id", 0))
                text = next((getattr(m, "raw_text", "") for m in messages if getattr(m, "raw_text", "")), "")
                sender = await messages[0].get_sender() if hasattr(messages[0], "get_sender") else None
                if not _passes(rule, messages, text, sender):
                    continue
                ids = tuple(getattr(m, "id", 0) for m in messages)
                for target in filter(lambda x: x is not None, (_peer(x) for x in _split(rule.get("targets")))):
                    dedupe_key = f"{source}:{target}:{','.join(map(str, ids))}"
                    if dedupe_key in sent:
                        skipped += 1
                        continue
                    try:
                        delivery={}
                        if rule.get("copy"):
                            await _copy(client,target,messages,log=log,delivery=delivery)
                        else:
                            await _forward(client,target,messages,log,delivery)
                        sent.add(dedupe_key)
                        sent_count += 1
                        log.info("[消息转发助手] 补全 %s (%s) -> %s (%s)，来源消息=%s，目标消息=%s，模式=%s", await resolve(client, source), source_id, await resolve(client, target), target, ",".join(map(str, ids)),",".join(map(str,delivery.get("message_ids") or [])),delivery.get("mode","未知"))
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        log.warning("[消息转发助手] 补全失败 %s -> %s: %r", source_id, target, error)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning("[消息转发助手] 回查来源 %s 失败: %r", source, error)
    return sent_count, skipped

async def setup(ctx):
    _migrate_zf_config(ctx)
    _normalize_repeat_mode(ctx)
    seen={};names={}
    sent = set(str(x) for x in (await ctx.storage.get("backfill_sent", []) or []))
    backfill_task = None
    backfill_lock = asyncio.Lock()
    async def persist_sent():
        # Keep the checkpoint bounded while surviving reloads.
        await ctx.storage.set("backfill_sent", list(sent)[-5000:])
    try:
        migrated=bool(await ctx.storage.get("strict_copy_v214_migrated",False))
        pending=set(str(x) for x in (await ctx.storage.get("strict_copy_v214_pending",[]) or []))
        if not migrated:
            if not pending:
                pending=_latest_legacy_copy_keys(ctx.config.get("rules") or [],sent)
                await ctx.storage.set("strict_copy_v214_pending",list(pending))
            if pending:
                sent.difference_update(pending)
                await persist_sent()
                ctx.log.info("[消息转发助手] 已安排重新复制 %s 条旧记录，以修复此前的模式降级",len(pending))
            await ctx.storage.set("strict_copy_v214_migrated",True)
            await ctx.storage.set("strict_copy_v214_pending",[])
    except Exception as error:
        ctx.log.warning("[消息转发助手] 旧复制记录修复准备失败，将在下次重载重试: %r",error)
    async def resolve(client,target):
        key=str(target)
        if key not in names:
            try:names[key]=_label(await client.get_entity(target),target)
            except Exception:names[key]=key
        return names[key]

    async def run_backfill(trigger, *, require_auto=False):
        cfg=ctx.config
        if require_auto and not cfg.get("auto_backfill",True):return None
        if not cfg.get("enable",False) or not ctx.user:return None
        rules=[rule for rule in (cfg.get("rules") or []) if isinstance(rule,dict)]
        if not rules:return None
        if backfill_lock.locked():
            ctx.log.debug("[消息转发助手] %s遗漏检查跳过：已有检查正在运行",trigger)
            return None
        async with backfill_lock:
            count,skipped=await _backfill(
                ctx.user,rules,cfg.get("backfill_limit",100),sent,
                ctx.log,resolve,bool(cfg.get("forward_album",True)),
            )
            await persist_sent()
            message=f"{trigger}遗漏检查完成：补发 {count} 组，跳过 {skipped} 组"
            if count or trigger!="定时":ctx.log.info("[消息转发助手] %s",message)
            else:ctx.log.debug("[消息转发助手] %s",message)
            return count,skipped
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
        else:messages=[event.message]
        chat=await event.get_chat();sender=await event.get_sender();text=next((m.raw_text for m in messages if m.raw_text),"")
        for rule in cfg.get("rules") or []:
            if not isinstance(rule,dict):continue
            source=_peer(rule.get("source"))
            if source is None or not _source_matches(event.chat_id,chat,source) or not _passes(rule,messages,text,sender):continue
            for target in filter(lambda x:x is not None,(_peer(x) for x in _split(rule.get("targets")))):
                try:
                    delivery={}
                    if rule.get("copy"):
                        await _copy(event.client,target,messages,log=ctx.log,delivery=delivery)
                    else:
                        await _forward(event.client,target,messages,ctx.log,delivery)
                    delivery_mode=delivery.get("mode","未知")
                    ids = tuple(getattr(message, "id", 0) for message in messages)
                    sent.add(f"{source}:{target}:{','.join(map(str, ids))}")
                    try:
                        await persist_sent()
                    except Exception as error:
                        ctx.log.warning("[消息转发助手] 转发已完成，但去重检查点保存失败: %r", error)
                    ctx.log.info("[消息转发助手] %s (%s) -> %s (%s)，目标消息=%s，模式=%s",_label(chat,event.chat_id),event.chat_id,await resolve(event.client,target),target,",".join(map(str,delivery.get("message_ids") or [])),delivery_mode)
                except asyncio.CancelledError:raise
                except Exception as error:ctx.log.warning("[消息转发助手] 转发失败 %s -> %s: %r",event.chat_id,target,error)

    @ctx.on_message(incoming=False,outgoing=True)
    async def repeat(event):
        cfg=ctx.config
        if not cfg.get("repeat_enabled",True):return
        times=_parse_repeat(
            event.raw_text or "",cfg.get("repeat_command",".zf"),
            cfg.get("repeat_max_times",50),
        )
        if times is None:return
        source=await event.get_reply_message()
        if source is None:
            await event.edit("请先回复一条要转发或复制的消息")
            return
        try:interval=max(0.0,min(float(cfg.get("repeat_interval",0.3) or 0),5.0))
        except (TypeError,ValueError):interval=0.3
        raw_mode=cfg.get("repeat_mode",False)
        mode="copy" if (raw_mode is True or isinstance(raw_mode,str) and raw_mode.strip().lower()=="copy") else "forward"
        topic=_repeat_topic(event,source)
        completed=0
        for index in range(times):
            if interval:await asyncio.sleep(interval)
            try:
                if mode=="copy":
                    await _copy(event.client,event.chat_id,[source],reply_to=topic,log=ctx.log)
                else:
                    await _repeat_forward(event.client,event.chat_id,source,topic)
                completed+=1
            except asyncio.CancelledError:
                raise
            except Exception as error:
                action="复制" if mode=="copy" else "转发"
                ctx.log.warning("[消息转发助手] 第 %d/%d 次%s失败: %r",index+1,times,action,error)
        try:await event.delete()
        except Exception:pass
        ctx.log.info("[消息转发助手] 回复复读完成：%s/%s，模式=%s，会话=%s",completed,times,mode,event.chat_id)

    @ctx.action("backfill")
    async def action_backfill():
        nonlocal backfill_task
        ctx.log.info("[消息转发助手] 已收到立即检查遗漏请求")
        if not ctx.config.get("enable", False):
            ctx.log.warning("[消息转发助手] 立即检查未启动：规则转发开关未开启")
            return {"ok": False, "message": "请先启用规则转发"}
        if backfill_task is not None and not backfill_task.done():
            ctx.log.info("[消息转发助手] 立即检查未重复启动：已有遗漏检查正在运行")
            return {"ok": False, "message": "遗漏补全任务正在运行"}
        if backfill_lock.locked():
            ctx.log.info("[消息转发助手] 立即检查未重复启动：已有遗漏检查正在运行")
            return {"ok": False, "message": "遗漏检查正在运行"}
        if not ctx.user:
            ctx.log.warning("[消息转发助手] 立即检查未启动：用户客户端尚未连接")
            return {"ok": False, "message": "用户客户端尚未连接"}
        rules = [r for r in (ctx.config.get("rules") or []) if isinstance(r, dict)]
        if not rules:
            ctx.log.warning("[消息转发助手] 立即检查未启动：尚未配置转发规则")
            return {"ok": False, "message": "尚未配置转发规则"}
        backfill_task = ctx.create_task(run_backfill("手动"), name="消息转发助手：立即检查遗漏")
        ctx.log.info("[消息转发助手] 立即检查遗漏任务已启动")
        return {"ok": True, "message": "已开始回查历史消息并补发遗漏，详情见插件日志"}

    if ctx.config.get("auto_backfill",True) and ctx.config.get("enable",False) and ctx.user:
        try:interval=max(1,min(int(ctx.config.get("backfill_interval_min",10) or 10),1440))
        except (TypeError,ValueError):interval=10
        async def scheduled_backfill():
            await run_backfill("定时",require_auto=True)
        ctx.schedule_interval("消息转发助手：自动检查遗漏",scheduled_backfill,seconds=interval*60)
        ctx.log.info("[消息转发助手] 已启用自动遗漏检查，间隔 %s 分钟",interval)
        if ctx.user and ctx.config.get("enable",False) and any(isinstance(rule,dict) for rule in (ctx.config.get("rules") or [])):
            backfill_task=ctx.create_task(run_backfill("启动",require_auto=True),name="消息转发助手：启动检查遗漏")

    def cleanup_backfill():
        if backfill_task is not None and not backfill_task.done():
            backfill_task.cancel()
    ctx.add_cleanup(cleanup_backfill)

async def teardown(ctx):ctx.log.info("[消息转发助手] 已停用")
