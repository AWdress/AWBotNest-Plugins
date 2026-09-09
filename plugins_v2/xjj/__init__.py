"""AWBotNest V2 原生随机短视频插件。"""
from __future__ import annotations
from uuid import uuid4
__plugin__={"id":"xjj","name":"小姐姐视频","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"发送 /xjj 或 .xjj 获取一条随机短视频。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png","tags":["随机短视频","视频发送","群组娱乐"],"config_schema":{"command":{"type":"string","default":".xjj","label":"触发命令","section":"命令","order":10},"api_url":{"type":"string","default":"http://47.115.231.249/API/sjsp/api.php?msg=热舞","label":"视频接口地址","section":"接口","order":20},"video_key":{"type":"string","default":"url","label":"直链字段名","section":"接口","order":21},"timeout":{"type":"number","default":15,"label":"请求超时(秒)","min":5,"max":60,"step":5,"section":"接口","order":22}},"resources":{"timeout_seconds":120,"max_concurrency":4},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用平台 HTTP 服务访问接口及下载视频\n- 使用 Telethon 原生视频发送\n- 移除 V1 兼容运行层和直接 httpx 依赖"}
def _matches(text,command):
    bare=str(command or "xjj").lstrip("/.").strip().lower() or "xjj";parts=(text or "").split();return bool(parts and parts[0].lower() in (f"/{bare}",f".{bare}"))
async def _url(ctx,api,key,timeout):
    response=await ctx.http.get(api,timeout=timeout);response.raise_for_status();data=response.json();value=data.get(key) if isinstance(data,dict) else None
    if not value and isinstance(data,dict) and isinstance(data.get("data"),dict):value=data["data"].get(key)
    if not value:raise ValueError("接口未返回视频直链")
    value=str(value);return "https:"+value if value.startswith("//") else ("https://"+value if not value.startswith(("http://","https://")) else value)
async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def send_video(event):
        if not _matches(event.raw_text or "",ctx.config.get("command",".xjj")):return
        await event.edit("小姐姐视频生成中…");path=ctx.data_dir/f"{uuid4().hex}.mp4"
        try:
            timeout=max(5,min(float(ctx.config.get("timeout",15) or 15),60));url=await _url(ctx,str(ctx.config.get("api_url") or ""),str(ctx.config.get("video_key") or "url"),timeout)
            await ctx.http.download(url,path);await event.client.send_file(event.chat_id,path,supports_streaming=True,reply_to=event.reply_to_msg_id);await event.delete()
        except Exception as error:ctx.log.warning("[小姐姐视频] 获取或发送失败: %r",error);await event.edit(f"获取失败: {type(error).__name__}")
        finally:
            try:path.unlink(missing_ok=True)
            except OSError:pass
async def teardown(ctx):ctx.log.info("[小姐姐视频] 已停用")
