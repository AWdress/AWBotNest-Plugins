# =============================================================================
# AWBotNest 插件：取消息结构（getmsg）
#
# 由 /getmsg 或 .getmsg 触发：把你回复的那条消息的原始结构（repr）导出成
# 一个 txt 文件，发到你自己账号的「收藏夹」（Saved Messages），方便调试取参数。
# =============================================================================

import tempfile
from datetime import datetime
from pathlib import Path

__plugin__ = {
    "name": "取消息结构",
    "id": "getmsg",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "回复一条消息再发 /getmsg，把该消息的原始结构导出为 txt 发到你的收藏夹，便于调试。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "command": {
            "type": "string", "default": ".getmsg", "label": "触发命令",
            "section": "参数", "help": "自己发出、以此开头的消息会触发。/getmsg 与 .getmsg 等价。",
        },
        "delete_command": {
            "type": "boolean", "default": True, "label": "删除命令消息",
            "section": "参数", "help": "导出后是否删除你发出的 /getmsg 命令本身。",
        },
    },
}


def _bare(command: str) -> str:
    return (command or "").lstrip("/.").strip().lower() or "getmsg"


async def setup(ctx):
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-16)
    async def get_message(client, message):
        cfg = ctx.config
        bare = _bare(cfg.get("command", ".getmsg"))
        text = message.text or ""
        head = text.split(maxsplit=1)[0].lower() if text else ""
        if head not in (f"/{bare}", f".{bare}"):
            return

        reply = message.reply_to_message
        if not reply:
            return await message.edit("❌ 请先回复一条要查看结构的消息")

        # 生成临时 txt 文件
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        prefix = (reply.text[:6] if reply.text else "") or "msg"
        tmp_dir = Path(tempfile.mkdtemp(prefix="getmsg_"))
        file_path = tmp_dir / f"{prefix}_{ts}.txt"
        try:
            file_path.write_text(str(reply), encoding="utf-8")
            # 发到自己账号的收藏夹（Saved Messages）
            await client.send_document("me", str(file_path))
            if cfg.get("delete_command", True):
                try:
                    await message.delete()
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[取消息结构] 导出失败: %r", e)
            try:
                await message.edit(f"❌ 导出失败: {e.__class__.__name__}")
            except Exception:
                pass
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def teardown(ctx):
    pass
