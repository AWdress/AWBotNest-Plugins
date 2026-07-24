# =============================================================================
# AWBotNest 插件：自动换头像（auto_avatar）
#
# 定时把你的用户账号头像换成图片池里随机一张。图片池存在插件独享目录
# ctx.data_dir/<账号名>/ 下，每账号一份。
#
# 怎么往池子加图（用你的账号操作，任意会话如「收藏夹」均可）：
#   - 回复一张图片，发送  .avataradd      → 把该图存入当前账号图片池
#   - 直接发图并把图片说明(caption)写成  .avataradd  → 同上
#   .avatarlist   查看池内图片数量
#   .avatarclear  清空当前账号图片池
#
# 换的是用户账号自己的头像；删除旧头像只删本插件上次设置的那张，不动你的其它头像。
# =============================================================================

import random

__plugin__ = {
    "name": "自动换头像",
    "id": "auto_avatar",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "定时把账号头像换成图片池里随机一张。回复图片发 .avataradd 加入池子，.avatarlist/.avatarclear 管理。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png",
    "changelog": "v1.0.3 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "delete_old": {
            "type": "boolean", "default": True, "label": "删除旧头像",
            "cols": 3, "order": 1, "section": "功能开关",
            "help": "换新头像后删掉本插件上次设的那张（不动你原有的真实头像）。",
        },
        "interval_min": {
            "type": "slider", "default": 60, "label": "换头像间隔(分钟)",
            "min": 10, "max": 1440, "step": 10, "order": 10, "section": "头像轮换",
            "help": "每隔多少分钟随机换一次。最小 10 分钟，防 Telegram 限流。改这个值后需「重载」插件生效。",
        },
        "add_command": {
            "type": "string", "default": ".avataradd", "label": "加图命令",
            "order": 20, "section": "图片池命令",
            "help": "回复图片或发图带此说明，把图存入池子。",
        },
        "list_command": {
            "type": "string", "default": ".avatarlist", "label": "查看命令",
            "order": 21, "section": "图片池命令",
        },
        "clear_command": {
            "type": "string", "default": ".avatarclear", "label": "清空命令",
            "order": 22, "section": "图片池命令",
        },
    },
}

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _account_name(client) -> str:
    me = getattr(client, "me", None)
    if me:
        return (me.username or str(me.id)) if (me.username or me.id) else "default"
    return getattr(client, "name", "default")


def _pool_dir(ctx, client):
    """本账号图片池目录（ctx.data_dir/<账号>/），自动建。"""
    d = ctx.data_dir / _account_name(client)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _list_pool(ctx, client) -> list:
    d = _pool_dir(ctx, client)
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in _IMG_EXTS)


def _matches(text: str, command: str) -> bool:
    bare = (command or "").lstrip("/.").strip()
    if not bare:
        return False
    head = (text or "").strip().split(maxsplit=1)[0].lower() if text else ""
    return head in (f"/{bare}", f".{bare}")


async def _change_one(ctx, client):
    """给当前账号换一张随机头像。"""
    pool = _list_pool(ctx, client)
    if not pool:
        ctx.log.debug("[自动换头像] 账号 %s 图片池为空，跳过", _account_name(client))
        return
    img = random.choice(pool)
    kv_key = f"last_file_id:{_account_name(client)}"
    old_file_id = ctx.kv.get(kv_key, "")

    # 设置新头像（photo 传文件路径字符串）
    await client.set_profile_photo(photo=str(img))

    # 取刚设置的头像 file_id 并记录
    new_file_id = ""
    try:
        async for photo in client.get_chat_photos("me", limit=1):
            new_file_id = photo.file_id
            break
    except Exception as e:  # noqa: BLE001
        ctx.log.debug("[自动换头像] 取新头像ID失败: %r", e)
    if new_file_id:
        ctx.kv.set(kv_key, new_file_id)

    # 删除本插件上次设置的旧头像
    if ctx.config.get("delete_old", True) and old_file_id and old_file_id != new_file_id:
        try:
            await client.delete_profile_photos(old_file_id)
        except Exception as e:  # noqa: BLE001
            ctx.log.debug("[自动换头像] 删旧头像失败: %r", e)
    ctx.log.info("[自动换头像] 账号 %s 已换头像: %s", _account_name(client), img.name)


async def setup(ctx):
    # ── 定时换头像 ──
    async def _tick():
        for app in ctx.user_apps:
            try:
                await _change_one(ctx, app)
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[自动换头像] 换头像失败: %r", e)

    try:
        interval = int(ctx.config.get("interval_min", 60) or 60)
    except (ValueError, TypeError):
        interval = 60
    interval = max(10, min(interval, 1440))
    ctx.schedule(_tick, "interval", minutes=interval, id="自动换头像")
    ctx.log.info("[自动换头像] 已启用，每 %d 分钟", interval)

    # ── 管理命令（自己发出）──
    @ctx.on_message(ctx.filters.outgoing & (ctx.filters.text | ctx.filters.photo), group=-10)
    async def manage(client, message):
        cfg = ctx.config
        # 命令可能在 text（回复图）或 caption（发图带说明）
        cmd_text = message.text or message.caption or ""

        # 加图
        if _matches(cmd_text, cfg.get("add_command", ".avataradd")):
            # 图片来源：自身这条消息的图，或被回复消息的图
            src = message if message.photo else message.reply_to_message
            if not src or not getattr(src, "photo", None):
                return await message.edit("请回复一张图片，或发图并把说明写成加图命令")
            try:
                pool_dir = _pool_dir(ctx, client)
                dest = pool_dir / f"{src.id}.jpg"
                await client.download_media(src, file_name=str(dest))
                count = len(_list_pool(ctx, client))
                await message.edit(f"已存入图片池（账号 {_account_name(client)}，共 {count} 张）")
            except Exception as e:  # noqa: BLE001
                ctx.log.error("[自动换头像] 存图失败: %r", e)
                await message.edit(f"存图失败: {e.__class__.__name__}")
            return

        # 查看
        if _matches(cmd_text, cfg.get("list_command", ".avatarlist")):
            count = len(_list_pool(ctx, client))
            return await message.edit(f"账号 {_account_name(client)} 图片池：{count} 张")

        # 清空
        if _matches(cmd_text, cfg.get("clear_command", ".avatarclear")):
            removed = 0
            for p in _list_pool(ctx, client):
                try:
                    p.unlink()
                    removed += 1
                except Exception:
                    pass
            return await message.edit(f"已清空 {removed} 张（账号 {_account_name(client)}）")


async def teardown(ctx):
    pass
