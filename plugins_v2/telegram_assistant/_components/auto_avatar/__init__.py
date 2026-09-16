"""AWBotNest V2 原生自动换头像插件。"""
from __future__ import annotations
import random
from telethon import functions

__plugin__={"id":"auto_avatar","name":"自动换头像","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"定时从每账号图片池随机更换头像，并提供添加、查看和清空命令。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png","tags":["头像轮换","图片池","定时任务"],"config_schema":{"delete_old":{"type":"boolean","default":True,"label":"删除旧头像","section":"功能开关","order":1},"interval_min":{"type":"number","default":60,"label":"换头像间隔(分钟)","min":10,"max":1440,"step":10,"section":"头像轮换","order":10},"add_command":{"type":"string","default":".avataradd","label":"加图命令","section":"图片池命令","order":20},"list_command":{"type":"string","default":".avatarlist","label":"查看命令","section":"图片池命令","order":21},"clear_command":{"type":"string","default":".avatarclear","label":"清空命令","section":"图片池命令","order":22}},"resources":{"timeout_seconds":120,"max_concurrency":4},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生头像上传与删除接口\n- 使用平台异步存储记录插件设置的头像\n- 图片池限制在插件数据目录并移除 V1 兼容层"}

_EXTENSIONS={".jpg",".jpeg",".png",".webp"}
async def _identity(client):
    me=await client.get_me();return getattr(me,"username",None) or str(me.id)
def _pool(ctx,name):
    path=ctx.data_dir/name;path.mkdir(parents=True,exist_ok=True);return path
def _images(ctx,name):return sorted(p for p in _pool(ctx,name).iterdir() if p.is_file() and p.suffix.lower() in _EXTENSIONS)
def _matches(text,command):
    bare=str(command or "").lstrip("/.").strip().lower();parts=(text or "").strip().split(maxsplit=1)
    return bool(bare and parts and parts[0].lower() in (f"/{bare}",f".{bare}"))

async def _change(ctx,client):
    name=await _identity(client);pool=_images(ctx,name)
    if not pool:ctx.log.debug("[自动换头像] 账号 %s 图片池为空",name);return False
    key=f"last_photo:{name}";old_id=str(await ctx.storage.get(key,"") or "");old_photo=None
    if old_id and ctx.config.get("delete_old",True):
        try:
            for photo in await client.get_profile_photos("me",limit=20):
                if str(photo.id)==old_id:old_photo=photo;break
        except Exception as error:ctx.log.debug("[自动换头像] 查找旧头像失败: %r",error)
    uploaded=await client.upload_file(random.choice(pool));result=await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
    new_photo=getattr(result,"photo",None)
    if new_photo:await ctx.storage.set(key,str(new_photo.id))
    if old_photo:
        try:await client(functions.photos.DeletePhotosRequest(id=[old_photo]))
        except Exception as error:ctx.log.warning("[自动换头像] 删除旧头像失败: %r",error)
    ctx.log.info("[自动换头像] 账号 %s 已完成头像轮换",name);return True

async def setup(ctx):
    async def tick():
        for client in tuple(ctx.users):
            try:await _change(ctx,client)
            except Exception as error:ctx.log.warning("[自动换头像] 轮换失败: %r",error)
    try:minutes=max(10,min(int(ctx.config.get("interval_min",60) or 60),1440))
    except (TypeError,ValueError):minutes=60
    ctx.schedule_interval("自动换头像",tick,seconds=minutes*60)

    @ctx.on_message(incoming=False,outgoing=True)
    async def manage(event):
        text=event.raw_text or "";name=await _identity(event.client)
        if _matches(text,ctx.config.get("add_command",".avataradd")):
            source=event if getattr(event,"photo",None) else await event.get_reply_message()
            if not source or not getattr(source,"photo",None):await event.edit("请回复一张图片，或发图并附加图命令");return
            target=_pool(ctx,name)/f"{source.id}.jpg";await event.client.download_media(source,file=target)
            await event.edit(f"已存入图片池（账号 {name}，共 {len(_images(ctx,name))} 张）");return
        if _matches(text,ctx.config.get("list_command",".avatarlist")):await event.edit(f"账号 {name} 图片池：{len(_images(ctx,name))} 张");return
        if _matches(text,ctx.config.get("clear_command",".avatarclear")):
            removed=0
            for path in _images(ctx,name):
                try:path.unlink();removed+=1
                except OSError:pass
            await event.edit(f"已清空 {removed} 张（账号 {name}）")

async def teardown(ctx):ctx.log.info("[自动换头像] 已停用")
