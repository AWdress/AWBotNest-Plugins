"""AWBotNest V2 原生举牌图片插件。"""
from __future__ import annotations
from io import BytesIO
import re
from urllib.parse import urlencode

__plugin__={"id":"jupai","name":"举牌","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"发送 /jupai 文字（或回复消息）生成举牌图片。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png","tags":["举牌生成","文字图片","群组互动"],"config_schema":{"command":{"type":"string","default":".jupai","label":"触发命令","section":"命令","order":10},"api_url":{"type":"string","default":"https://api.txqq.pro/api/zt.php","label":"举牌接口地址","section":"接口","order":11}},"resources":{"timeout_seconds":30,"max_concurrency":4},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用平台 HTTP 服务下载举牌图片\n- 使用 Telethon 原生文件发送\n- 移除 V1 兼容运行层"}

def _argument(text,command):
    bare=re.escape(str(command or "jupai").lstrip("/.").strip() or "jupai");match=re.match(rf"^[/\.]{{1}}{bare}(?:\s+(.+))?$",text or "",re.I|re.S)
    return None if not match else (match.group(1) or "").strip()

async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def generate(event):
        arg=_argument(event.raw_text or "",ctx.config.get("command",".jupai"))
        if arg is None:return
        source=await event.get_reply_message();text=(source.raw_text or "").strip() if source else arg
        if not text:await event.edit("请回复一条消息或输入文字\n例如: /jupai 你好");return
        try:
            url=str(ctx.config.get("api_url") or "https://api.txqq.pro/api/zt.php");separator="&" if "?" in url else "?"
            response=await ctx.http.get(url+separator+urlencode({"msg":text}),timeout=20);response.raise_for_status()
            image=BytesIO(response.content);image.name="jupai.jpg"
            await event.client.send_file(event.chat_id,image);await event.delete()
        except Exception as error:
            ctx.log.error("[举牌] 生成失败: %r",error);await event.edit(f"获取失败: {type(error).__name__}")

async def teardown(ctx):ctx.log.info("[举牌] 已停用")
