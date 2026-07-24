# =============================================================================
# AWBotNest 插件：115 搜索结果转发（trans115search）
#
# 监听指定来源会话里某机器人发出的「列表」消息，转发到你指定的目标会话。
# 用你的用户账号监听，用机器人把内容转发到目标会话。
# =============================================================================

__plugin__ = {
    "name": "115搜索结果转发",
    "id": "trans115search",
    "version": "1.0.4",
    "author": "AWdress",
    "description": "监听来源会话里机器人发的「列表」消息，自动转发到你指定的目标会话。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cloud_media.png",
    "changelog": "v1.0.4 优化配置界面布局\n- 开关字段统一置顶，采用推荐的栅格布局\n- 参数字段添加 order 排序，提升扫描性\n- 符合 AWBotNest 插件开发规范\n\nv1.0.3 更新插件 Logo\n- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "source_chat_id": {
            "type": "string", "default": "-1002466900287", "label": "来源会话ID",
            "section": "基本配置", "help": "监听哪个会话里机器人发的列表消息。",
            "order": 10, "cols": 6,
        },
        "target_chat_id": {
            "type": "string", "default": "", "label": "转发到会话ID",
            "section": "基本配置", "help": "把列表消息转发到这个会话（群/频道ID或@用户名）。留空则不转发。",
            "order": 11, "cols": 6,
        },
        "keyword": {
            "type": "string", "default": "列表", "label": "触发关键词",
            "section": "基本配置", "help": "消息含此关键词才转发。",
            "order": 12, "cols": 6,
        },
    },
}


def _normalize_chat_id(raw):
    s = str(raw or "").strip()
    if not s:
        return None
    if s.startswith("@"):
        return s
    try:
        return int(s)
    except ValueError:
        return None


async def setup(ctx):
    @ctx.on_message(ctx.filters.text | ctx.filters.caption, group=7)
    async def forward_list(client, message):
        cfg = ctx.config
        source = _normalize_chat_id(cfg.get("source_chat_id"))
        target = _normalize_chat_id(cfg.get("target_chat_id"))
        keyword = cfg.get("keyword", "列表")
        if source is None or target is None:
            return
        if message.chat.id != source:
            return
        fu = message.from_user
        if not (fu and fu.is_bot):
            return
        # 文本和实体要取自同一来源：caption 类消息的格式实体在 caption_entities，
        # 普通文本消息的在 entities。取错会把列表里的链接/格式丢掉。
        if message.caption:
            text = message.caption
            entities = message.caption_entities
        else:
            text = message.text or ""
            entities = message.entities
        if keyword and keyword not in text:
            return

        try:
            await ctx.bot.send(
                target, text,
                entities=entities,
                disable_web_page_preview=True,
            )
        except Exception as e:  # noqa: BLE001
            ctx.log.warning("[115列表转发] 转发失败: %r", e)


async def teardown(ctx):
    pass
