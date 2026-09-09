"""AWBotNest V2 原生消息结构导出插件。"""
from __future__ import annotations
import asyncio
import re
from datetime import datetime

__plugin__={"id":"getmsg","name":"取消息结构","version":"2.0.0","author":"AWdress","scope":"user","plugin_api_version":2,"requirements":[],"render_mode":"schema","description":"回复消息发送 /getmsg，将 Telethon 原始结构导出为文本文件。","icon":"https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png","tags":["消息提取","结构调试","媒体信息"],"config_schema":{"delete_command":{"type":"boolean","default":True,"label":"删除命令消息","section":"功能开关","order":1},"command":{"type":"string","default":".getmsg","label":"触发命令","section":"命令","order":10}},"changelog":"v2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原始消息结构导出\n- 文件仅写入插件数据目录并在发送后清理\n- 移除 V1 兼容运行层"}

def _hit(text,command):
    bare=str(command or "getmsg").lstrip("/.").strip().lower() or "getmsg";parts=(text or "").split()
    return bool(parts and parts[0].lower() in (f"/{bare}",f".{bare}"))

async def setup(ctx):
    @ctx.on_message(incoming=False,outgoing=True)
    async def export(event):
        if not _hit(event.raw_text or "",ctx.config.get("command",".getmsg")):return
        source=await event.get_reply_message()
        if source is None:await event.edit("请先回复一条要查看结构的消息");return
        slug=re.sub(r"[^\w一-鿿-]","",source.raw_text or "msg")[:12] or "msg"
        path=ctx.data_dir/f"{slug}_{datetime.now():%Y%m%d%H%M%S}.txt"
        try:
            path.write_text(repr(source),encoding="utf-8")
            await event.client.send_file("me",path,caption="【取消息结构】Telethon 原始结构")
            await event.edit("已导出消息结构到收藏夹 ✓")
            if ctx.config.get("delete_command",True):
                async def cleanup():
                    await asyncio.sleep(3)
                    try:await event.delete()
                    except Exception:pass
                ctx.create_task(cleanup(),name="getmsg-cleanup")
        except Exception as error:
            ctx.log.error("[取消息结构] 导出失败: %r",error);await event.edit(f"导出失败: {type(error).__name__}")
        finally:
            try:path.unlink(missing_ok=True)
            except Exception:pass

async def teardown(ctx):ctx.log.info("[取消息结构] 已停用")
