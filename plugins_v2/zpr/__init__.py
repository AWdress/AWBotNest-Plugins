"""AWBotNest V2 原生二次元图片插件。"""
from __future__ import annotations
import re
from uuid import uuid4

__plugin__={"id":"zpr","name":"P站图片","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"发送 /zpr [关键词] [数量] [r18] 获取二次元图片；/zp 同时发送原图文件。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png","tags":["二次元图片","Pixiv图片","原图下载"],"config_schema":{"allow_r18":{"type":"boolean","default":False,"label":"允许 R18","section":"功能开关","order":1},"spoiler":{"type":"boolean","default":True,"label":"图片加遮罩","section":"功能开关","order":2},"default_num":{"type":"number","default":3,"label":"默认数量","min":1,"max":10,"step":1,"section":"数量限制","order":10},"max_num":{"type":"number","default":6,"label":"最大数量","min":1,"max":20,"step":1,"section":"数量限制","order":11}},"resources":{"timeout_seconds":180,"max_concurrency":3},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用平台 HTTP 服务访问图片接口和下载资源\n- 使用 Telethon 原生图片、遮罩及文件发送\n- 修正插件市场功能标签并移除 V1 兼容层"}
_API="https://api.lolicon.app/setu/v2";_HEADERS={"User-Agent":"Mozilla/5.0 AWBotNest/2"}
def _command(text):
    match=re.match(r"^[/\.](zp[r]?)(?:\s|$)",text or "",re.I);return None if not match else match.group(1).lower()=="zp"
def _args(text):
    parts=(text or "").split()[1:];tag=parts[0] if parts else "";number=int(parts[1]) if len(parts)>1 and parts[1].isdigit() else None;r18=int(parts[2]) if len(parts)>2 and parts[2].isdigit() and int(parts[2])<=2 else 0;return tag,number,r18
async def _fetch(ctx,r18,num,size,tag):
    response=await ctx.http.get(_API,params={"num":num,"r18":r18,"size":size,"tag":tag},headers=_HEADERS,timeout=15);response.raise_for_status();data=response.json().get("data",[]);paths=[]
    for index,item in enumerate(data):
        url=str(item.get("urls",{}).get(size,"")).replace("i.pixiv.re","i.pixiv.re")
        if not url:continue
        path=ctx.data_dir/f"zpr_{uuid4().hex}_{item.get('pid',index)}.jpg"
        try:await ctx.http.download(url,path);paths.append(path)
        except Exception as error:ctx.log.warning("[P站图片] 下载失败: %r",error)
    return paths
async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def pictures(event):
        as_file=_command(event.raw_text or "")
        if as_file is None:return
        tag,number,r18=_args(event.raw_text or "");maximum=max(1,min(int(ctx.config.get("max_num",6) or 6),20));num=max(1,min(number or int(ctx.config.get("default_num",3) or 3),maximum))
        if not ctx.config.get("allow_r18",False):r18=0
        await event.edit("正在获取图片…");paths=[]
        try:
            paths=await _fetch(ctx,r18,num,"original" if as_file else "regular",tag)
            if not paths:await event.edit("出错了，没有纸片人看了。");return
            for path in paths:await event.client.send_file(event.chat_id,path,reply_to=event.reply_to_msg_id,spoiler=bool(ctx.config.get("spoiler",True)))
            if as_file:
                for path in paths:await event.client.send_file(event.chat_id,path,reply_to=event.reply_to_msg_id,force_document=True)
            await event.delete()
        except Exception as error:ctx.log.error("[P站图片] 发送失败: %r",error);await event.edit(f"发生错误：{type(error).__name__}")
        finally:
            for path in paths:
                try:path.unlink(missing_ok=True)
                except OSError:pass
async def teardown(ctx):ctx.log.info("[P站图片] 已停用")
