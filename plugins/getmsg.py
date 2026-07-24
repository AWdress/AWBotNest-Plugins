# =============================================================================
# AWBotNest 插件：取消息结构（getmsg）
#
# 由 /getmsg 或 .getmsg 触发：把你回复的那条消息的原始结构（repr）导出成
# 一个 txt 文件，通过 Bot 发到「平台通知」（即主人 Bot 私聊），方便调试取参数。
# =============================================================================

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path

__plugin__ = {
    "name": "取消息结构",
    "id": "getmsg",
    "version": "1.0.6",
    "author": "AWdress",
    "description": "回复一条消息再发 /getmsg，把该消息的原始结构导出为 txt 通过 Bot 发到平台通知，便于调试。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "changelog": "v1.0.6 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\nv1.0.5 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "delete_command": {
            "type": "boolean", "default": True, "label": "删除命令消息",
            "cols": 3, "order": 1, "section": "功能开关",
            "help": "导出后是否删除你发出的 /getmsg 命令本身。",
        },
        "command": {
            "type": "string", "default": ".getmsg", "label": "触发命令",
            "order": 10, "section": "命令",
            "help": "自己发出、以此开头的消息会触发。/getmsg 与 .getmsg 等价。",
        },
    },
}


def _bare(command: str) -> str:
    return (command or "").lstrip("/.").strip().lower() or "getmsg"


def _safe_slug(text: str | None, fallback: str = "msg") -> str:
    """把任意文本压成可安全做文件名的短片段：去掉路径分隔符/控制字符/各种非法字符。"""
    raw = (text or "").strip()
    # 只保留中英文、数字、下划线、连字符；其余（含 / \ : 空格 换行 emoji）一律丢弃
    slug = re.sub(r"[^\w一-鿿-]", "", raw)[:12]
    return slug or fallback


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
            return await message.edit("请先回复一条要查看结构的消息")

        # 生成临时 txt 文件（文件名做安全清洗，避免回复内容里的 / : 换行等把路径搞坏）
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        prefix = _safe_slug(reply.text or reply.caption)
        tmp_dir = Path(tempfile.mkdtemp(prefix="getmsg_"))
        file_path = tmp_dir / f"{prefix}_{ts}.txt"
        try:
            file_path.write_text(str(reply), encoding="utf-8")
            # 通过 Bot 把结构文件发到「平台通知」（主人 Bot 私聊）。
            # Bot 未连接/没有主人 ID 时回退到当前用户账号收藏夹，避免彻底丢失。
            bot = ctx.bot
            sent_to = "Bot 通知"
            if bot.connected and ctx.owner_id:
                await bot.raw.send_document(
                    ctx.owner_id, str(file_path),
                    caption="【取消息结构】导出的原始结构",
                )
            else:
                await client.send_document("me", str(file_path))
                sent_to = "收藏夹（Bot 不可用回退）"
            # 给个可见反馈：把命令本身改成「已导出」，几秒后再删，避免看起来「没任何效果」
            try:
                await message.edit(f"已导出消息结构到{sent_to} ✓")
            except Exception:
                pass
            if cfg.get("delete_command", True):
                async def _cleanup_cmd(m=message):
                    await asyncio.sleep(3)
                    try:
                        await m.delete()
                    except Exception:
                        pass
                asyncio.create_task(_cleanup_cmd())
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[取消息结构] 导出失败: %r", e)
            try:
                await message.edit(f"导出失败: {e.__class__.__name__}: {e}")
            except Exception:
                pass
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def teardown(ctx):
    pass
