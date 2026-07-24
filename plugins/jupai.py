# =============================================================================
# AWBotNest 插件：举牌（jupai）
#
# 由 /jupai 或 .jupai 触发：把文字转成「举牌人」图片。
#   /jupai 你好        —— 把「你好」做成举牌图
#   回复某条消息 + /jupai —— 把被回复消息的文字做成举牌图
# =============================================================================

import re
import urllib.parse

__plugin__ = {
    "name": "举牌",
    "id": "jupai",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "发送 /jupai 文字（或回复一条消息再发 /jupai），把文字转成举牌人图片。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png",
    "changelog": "v1.0.3 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "command": {
            "type": "string", "default": ".jupai", "label": "触发命令",
            "section": "命令", "help": "自己发出、以此开头的消息会触发。/jupai 与 .jupai 等价。",
            "order": 10,
        },
        "api_url": {
            "type": "string", "default": "https://api.txqq.pro/api/zt.php",
            "label": "举牌接口地址", "section": "接口",
            "help": "接口以 ?msg=文字 拼接，返回举牌图片。",
            "order": 11,
        },
    },
}


def _bare(command: str) -> str:
    return re.escape(command.lstrip("/.").strip() or "jupai")


async def setup(ctx):
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-12)
    async def ju_pai(client, message):
        cfg = ctx.config
        bare = _bare(cfg.get("command", ".jupai"))
        # 命令后须是空白或结束
        if not re.match(rf"^[/\.]{bare}(?:\s|$)", message.text or "", re.IGNORECASE):
            return

        text = None
        # 优先取被回复消息的文字
        try:
            if message.reply_to_message:
                text = message.reply_to_message.text
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("获取回复消息失败: %r", e)

        # 否则取命令后的参数
        if not text:
            m = re.match(rf"^[/\.]{bare}(?:\s+(.+))?$", message.text or "", re.IGNORECASE)
            if m and m.group(1):
                text = m.group(1).strip()

        if not text:
            return await message.edit("请回复一条消息或输入文字\n例如: /jupai 你好")

        api_url = cfg.get("api_url", "https://api.txqq.pro/api/zt.php")
        try:
            image_url = f"{api_url}?msg={urllib.parse.quote(text)}"
            await message.reply_photo(
                image_url,
                quote=False,
                reply_to_message_id=None,  # 不带 reply_to，避免 PeerIdInvalid
            )
            await message.delete()
        except Exception as e:  # noqa: BLE001
            ctx.log.error("举牌失败: %r", e)
            try:
                await message.edit(f"获取失败: {e.__class__.__name__}")
            except Exception:
                pass


async def teardown(ctx):
    pass
