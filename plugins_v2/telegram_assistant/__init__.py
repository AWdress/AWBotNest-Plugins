"""Telegram 助手：合并消息工具与账号资料自动化。"""
from __future__ import annotations

from typing import Any, Mapping
from ._components import auto_avatar, auto_changename, getmsg, id as id_plugin, message_sticker, msg_forward, self_delete


__plugin__ = {
    "id": "telegram_assistant",
    "name": "Telegram 助手",
    "version": "0.0.12",
    "author": "AWdress",
    "scope": "user",
    "plugin_api_version": 2,
    "requirements": ["Pillow>=10.0"],
    "render_mode": "vue",
    "description": "Telegram 消息与账号工具集合：转发、删除消息、查询 ID、消息结构导出、消息贴图、自动换头像和自动报时昵称。",
    "icon": "https://cdn.simpleicons.org/telegram/26A5E4",
    "tags": ["Telegram", "消息工具", "贴纸生成", "账号自动化"],
    "resources": {"timeout_seconds": 300, "max_concurrency": 8, "max_background_tasks": 32},
    "config_schema": {
        "forward_enable": {"type": "boolean", "default": False, "label": "启用规则转发", "section": "消息转发", "order": 1},
        "forward_album": {"type": "boolean", "default": False, "label": "整组转发相册", "section": "消息转发", "order": 2},
        "forward_backfill_limit": {"type": "integer", "default": 50, "min": 1, "max": 500, "label": "遗漏补全回查条数", "section": "消息转发", "order": 3},
        "forward_auto_backfill": {"type": "boolean", "default": False, "label": "自动检查遗漏", "section": "消息转发", "order": 4},
        "forward_backfill_interval_min": {"type": "number", "default": 60, "min": 1, "max": 1440, "step": 1, "label": "遗漏检查间隔（分钟）", "section": "消息转发", "order": 5},
        "forward_repeat_enabled": {"type": "boolean", "default": False, "label": "启用回复复读", "section": "消息转发", "order": 6},
        "forward_repeat_command": {"type": "string", "default": ".zf", "label": "复读命令", "section": "消息转发", "order": 7},
        "forward_repeat_mode": {"type": "boolean", "default": False, "label": "复制重发", "help": "关闭为原样转发，开启为无署名复制。", "section": "消息转发", "order": 8},
        "forward_repeat_interval": {"type": "number", "default": 0.3, "min": 0, "max": 5, "step": 0.1, "label": "复读间隔（秒）", "section": "消息转发", "order": 9},
        "forward_repeat_max_times": {"type": "number", "default": 50, "min": 1, "max": 500, "step": 1, "label": "最多复读次数", "section": "消息转发", "order": 10},
        "forward_rules": {"type": "list", "default": [], "label": "转发规则", "item_label": "规则", "section": "消息转发", "order": 20, "fields": {
            "source": {"type": "string", "label": "来源会话"}, "targets": {"type": "string", "label": "转发到"},
            "types": {"type": "multiselect", "label": "消息类型", "default": [], "options": [{"value": "text", "label": "文本"}, {"value": "link", "label": "链接"}, {"value": "photo", "label": "图片"}, {"value": "video", "label": "视频"}, {"value": "document", "label": "文件"}, {"value": "audio", "label": "音频"}]},
            "kw": {"type": "string", "label": "关键词"}, "nkw": {"type": "string", "label": "排除词"}, "sender": {"type": "string", "label": "只转谁发的"}, "copy": {"type": "boolean", "label": "复制搬运", "default": False},
        }},
        "forward_resolved_chat_names": {"type": "info", "default": "", "label": "已识别会话名称", "section": "消息转发", "order": 22},
        "forward_backfill": {"type": "action", "label": "立即检查遗漏", "action": "backfill", "help": "按当前规则回查来源历史消息并补发遗漏内容。", "section": "消息转发", "order": 21},
        "delete_enabled": {"type": "boolean", "default": False, "label": "启用删除消息", "section": "消息管理", "order": 29},
        "delete_command": {"type": "string", "default": ".dme", "label": "删除消息命令", "section": "消息管理", "order": 30},
        "delete_tip_seconds": {"type": "number", "default": 2, "min": 0, "max": 10, "step": 1, "label": "删除提示停留（秒）", "section": "消息管理", "order": 31},
        "id_enabled": {"type": "boolean", "default": False, "label": "启用查 ID", "section": "查 ID", "order": 39},
        "id_delete_command": {"type": "boolean", "default": False, "label": "查询后删除命令", "section": "查 ID", "order": 40},
        "id_command": {"type": "string", "default": ".id", "label": "查 ID 命令", "section": "查 ID", "order": 41},
        "id_auto_delete": {"type": "number", "default": 20, "min": 0, "max": 120, "step": 5, "label": "结果自动删除（秒）", "section": "查 ID", "order": 42},
        "getmsg_enabled": {"type": "boolean", "default": False, "label": "启用消息结构", "section": "消息结构", "order": 49},
        "getmsg_delete_command": {"type": "boolean", "default": False, "label": "导出后删除命令", "section": "消息结构", "order": 50},
        "getmsg_command": {"type": "string", "default": ".getmsg", "label": "消息结构命令", "section": "消息结构", "order": 51},
        "sticker_enabled": {"type": "boolean", "default": False, "label": "启用消息贴图", "section": "消息贴图", "order": 54},
        "sticker_command": {"type": "string", "default": ".贴图", "label": "贴图命令", "section": "消息贴图", "order": 55, "help": "回复消息发送该命令，生成带原发送者头像、昵称和正文的 Telegram 贴纸。"},
        "sticker_delete_command": {"type": "boolean", "default": False, "label": "成功后删除命令", "section": "消息贴图", "order": 56},
        "avatar_enabled": {"type": "boolean", "default": False, "label": "启用自动换头像", "section": "自动换头像", "order": 59},
        "avatar_delete_old": {"type": "boolean", "default": False, "label": "删除旧头像", "section": "自动换头像", "order": 60},
        "avatar_interval_min": {"type": "number", "default": 60, "min": 10, "max": 1440, "step": 10, "label": "换头像间隔（分钟）", "section": "自动换头像", "order": 61},
        "avatar_add_command": {"type": "string", "default": ".avataradd", "label": "加图命令", "section": "自动换头像", "order": 62},
        "avatar_list_command": {"type": "string", "default": ".avatarlist", "label": "查看图片池命令", "section": "自动换头像", "order": 63},
        "avatar_clear_command": {"type": "string", "default": ".avatarclear", "label": "清空图片池命令", "section": "自动换头像", "order": 64},
        "nickname_enabled": {"type": "boolean", "default": False, "label": "启用报时昵称", "section": "报时昵称", "order": 69},
        "nickname_interval_min": {"type": "number", "default": 5, "min": 1, "max": 60, "step": 1, "label": "昵称更新时间（分钟）", "section": "报时昵称", "order": 70},
        "nickname_name_format": {"type": "string", "default": "{boldH}:{boldM} {weather_icon} {temp}°C", "label": "昵称模板", "section": "报时昵称", "order": 71, "help": "占位符：{boldH}:{boldM}特殊字体时分，{H}:{M}普通时分，{weather_icon}天气图标，{temp}温度，{emoji}随机表情，{date}日期，{week}星期。"},
        "nickname_name_field": {"type": "select", "default": "last_name", "label": "修改哪个名字（姓 / 名 / 姓和名）", "section": "报时昵称", "order": 72, "help": "可选：姓、名或姓和名。", "options": [{"value": "last_name", "label": "姓"}, {"value": "first_name", "label": "名"}, {"value": "both", "label": "姓和名"}]},
        "nickname_location": {"type": "string", "default": "Guangzhou", "label": "天气城市（英文）", "section": "报时昵称", "order": 73, "help": "例如 Guangzhou、Beijing；用于获取昵称中的天气和温度。"},
        "nickname_weather_interval": {"type": "number", "default": 30, "min": 10, "max": 120, "step": 5, "label": "天气刷新间隔（分钟）", "section": "报时昵称", "order": 74},
    },
    "changelog": "v0.0.12 改用 Vue 分组配置页\n- 消息转发、消息工具、自动头像和报时昵称拆分为四个工作区\n- 保留全部原配置字段、默认值和功能开关，升级后直接读取已有配置\n- 转发规则支持逐条添加删除，并补充保存校验、移动端布局和遗漏检查入口\n\nv0.0.11 补齐全部功能开关\n- 删除消息、查 ID、消息结构、消息贴图和自动换头像新增独立开关\n- 所有功能开关的新安装默认值均为关闭\n- 功能关闭时不注册消息监听或定时任务\n\nv0.0.10 修复贴图昵称特殊字符\n- first_name 与 last_name 完全按 Telegram 原值显示，不再过滤报时昵称\n- 中文字体缺字时按字符回退到符号/Emoji 字体\n- 修复数学粗体时间、天气符号显示为方框的问题\n\nv0.0.9 新增报时昵称开关\n- 报时昵称默认关闭，关闭时不注册改名定时任务\n- Telegram 助手所有布尔开关的新安装默认值统一为关闭\n- 已保存的用户开关值保持不变\n\nv0.0.8 调整贴图姓名与头像\n- 同时显示 first_name 和普通 last_name，任一为空时显示另一项\n- first_name 与 last_name 均按 Telegram 原值显示\n- 移除头像外圈描边\n\nv0.0.7 修复贴图发送方式\n- 移除 Telethon force_file 标记，WebP 改为 Telegram 原生贴纸媒体\n- 昵称仅显示稳定的 first_name，不再带入报时昵称或缺字方框\n\nv0.0.6 新增消息贴图\n- 回复消息发送 .贴图，自动渲染头像、昵称和正文\n- 按 Telegram 静态 WebP 贴纸规格发送，不调用 AI\n- 配置页完整显示贴图命令和删除命令开关的默认值\n\nv0.0.5 补齐默认值与旧配置迁移\n- 新安装完整显示开关、数字、命令、昵称和天气默认值\n- 从旧六个插件迁移配置、转发规则、账号范围和通知渠道\n- 转发默认值按原插件常用设置填入 50 条、60 分钟与复制重发\n\nv0.0.4 完成源码级合并\n- 六项功能源码全部内置到 Telegram 助手安装包\n- 不再依赖或发布六个旧插件，修复独立安装时的导入失败\n\nv0.0.3 修复默认配置为空\n- 自动补全缺失/空白的命令、数值和昵称模板\n- 兼容旧版表单把默认开关全部保存为关闭的情况\n\nv0.0.2 更新自动报时昵称\n- 使用时间特殊字体、天气图标和温度模板\n- 增加天气城市与天气缓存间隔配置\n\nv0.0.1 首次发布\n- 合并消息转发、删除消息、查 ID、消息结构、自动换头像和自动报时昵称\n- 保留原有命令、规则和定时行为，启用时自动迁移旧插件配置\n- 使用 Telegram 官方图标",
}


class _ConfigView(dict):
    """Expose a module's legacy keys while storing namespaced keys centrally."""
    def __init__(self, source: Mapping[str, Any], mapping: Mapping[str, str]):
        # Missing namespaced values must stay absent so legacy ``get`` calls
        # can apply each module's declared default.
        super().__init__({legacy: source[namespaced] for namespaced, legacy in mapping.items() if namespaced in source})


class _ModuleContext:
    def __init__(self, ctx, mapping: Mapping[str, str]):
        self._ctx = ctx
        self._mapping = dict(mapping)

    @property
    def config(self):
        return _ConfigView(self._ctx.config, self._mapping)

    def update_config(self, values):
        reverse = {legacy: namespaced for namespaced, legacy in self._mapping.items()}
        self._ctx.update_config({reverse.get(str(key), str(key)): value for key, value in (values or {}).items()})

    def __getattr__(self, name):
        return getattr(self._ctx, name)


_FORWARD = {
    "forward_enable": "enable", "forward_album": "forward_album", "forward_backfill_limit": "backfill_limit",
    "forward_auto_backfill": "auto_backfill", "forward_backfill_interval_min": "backfill_interval_min",
    "forward_repeat_enabled": "repeat_enabled", "forward_repeat_command": "repeat_command",
    "forward_repeat_mode": "repeat_mode", "forward_repeat_interval": "repeat_interval",
    "forward_repeat_max_times": "repeat_max_times", "forward_rules": "rules",
    "forward_resolved_chat_names": "resolved_chat_names",
}
_DELETE = {"delete_command": "command", "delete_tip_seconds": "tip_seconds"}
_ID = {"id_delete_command": "delete_command", "id_command": "command", "id_auto_delete": "auto_delete"}
_GETMSG = {"getmsg_delete_command": "delete_command", "getmsg_command": "command"}
_STICKER = {"sticker_command": "command", "sticker_delete_command": "delete_command"}
_AVATAR = {"avatar_delete_old": "delete_old", "avatar_interval_min": "interval_min", "avatar_add_command": "add_command", "avatar_list_command": "list_command", "avatar_clear_command": "clear_command"}
_NICKNAME = {"nickname_enabled": "enabled", "nickname_interval_min": "interval_min", "nickname_name_format": "name_format", "nickname_name_field": "name_field", "nickname_location": "location", "nickname_weather_interval": "weather_interval"}


_LEGACY_MAPS = {
    "msg_forward": _FORWARD,
    "self_delete": _DELETE,
    "id": _ID,
    "getmsg": _GETMSG,
    "auto_avatar": _AVATAR,
    "auto_changename": _NICKNAME,
}


async def _migrate_old_configs(ctx):
    """一次性吸收被合并插件的真实已保存配置。"""
    storage = getattr(ctx, "storage", None)
    if storage is not None and await storage.get("legacy_plugins_migrated_v005", False):
        return

    registry = getattr(ctx, "_registry", None)
    saved_getter = getattr(registry, "get_saved_config", None)
    settings = getattr(ctx, "settings", None)
    settings_configs = getattr(settings, "plugin_config", None)
    updates = {}
    migrated_ids = []
    for plugin_id, mapping in _LEGACY_MAPS.items():
        old = None
        if callable(saved_getter):
            try:
                old = saved_getter(plugin_id)
            except Exception:
                old = None
        if not isinstance(old, dict) and isinstance(settings_configs, dict):
            old = settings_configs.get(plugin_id)
        if not isinstance(old, dict) or not old:
            continue
        migrated_ids.append(plugin_id)
        for namespaced, legacy in mapping.items():
            if legacy in old:
                updates[namespaced] = old[legacy]

    if updates:
        ctx.update_config(updates)
        ctx.log.info("[Telegram 助手] 已迁移 %d 个旧插件的 %d 项配置", len(migrated_ids), len(updates))

    # 原消息转发助手的账号范围和通知渠道最能代表合并插件的运行范围。
    if registry is not None and migrated_ids:
        get_scope = getattr(registry, "get_account_scope", None)
        set_scope = getattr(registry, "set_account_scope", None)
        if callable(get_scope) and callable(set_scope):
            scope = get_scope("msg_forward")
            if scope:
                set_scope(__plugin__["id"], scope)
        get_bot = getattr(registry, "get_bot_choice", None)
        set_bot = getattr(registry, "set_bot_choice", None)
        if callable(get_bot) and callable(set_bot):
            bot_choice = get_bot("msg_forward")
            if bot_choice:
                set_bot(__plugin__["id"], bot_choice)
        set_enabled = getattr(registry, "set_enabled", None)
        if callable(set_enabled):
            for plugin_id in migrated_ids:
                set_enabled(plugin_id, False)

    if storage is not None:
        await storage.set("legacy_plugins_migrated_v005", True)


def _saved_plugin_config(ctx) -> dict[str, Any]:
    """读取未叠加 schema 默认值的原始配置（仅用于修复旧表单空值）。"""
    settings = getattr(ctx, "settings", None)
    configs = getattr(settings, "plugin_config", None)
    if isinstance(configs, dict) and isinstance(configs.get(__plugin__["id"]), dict):
        return dict(configs[__plugin__["id"]])
    registry = getattr(ctx, "_registry", None)
    getter = getattr(registry, "get_saved_config", None)
    if callable(getter):
        try:
            value = getter(__plugin__["id"])
            if isinstance(value, dict):
                return dict(value)
        except Exception:
            pass
    return {}


def _restore_defaults(ctx):
    """把默认值写入配置，兼容旧版表单曾保存的空白/全关闭快照。

    平台会以用户保存值覆盖 schema 默认值。旧版表单初始化失败时会把
    文本/数字保存为空、布尔项保存为 False，导致配置页看起来没有默认内容。
    只在检测到这种明显的空白快照时恢复布尔默认值，避免覆盖用户后来
    有意关闭的开关。
    """
    schema = __plugin__["config_schema"]
    saved = _saved_plugin_config(ctx)
    current = ctx.config
    updates = {}

    # 正常的缺省值/空字符串/空数字始终可安全补回。
    for key, spec in schema.items():
        if "default" not in spec or spec.get("type") == "action":
            continue
        value = current.get(key)
        if key not in saved or value is None or (isinstance(value, str) and not value.strip()):
            updates[key] = spec["default"]

    # 识别旧表单产生的“所有文本为空 + 数值为空 + 开关全关”配置快照。
    text_keys = [k for k, s in schema.items() if s.get("type") == "string" and k in saved]
    number_keys = [k for k, s in schema.items() if s.get("type") in {"number", "integer", "slider"} and k in saved]
    true_defaults = [k for k, s in schema.items() if s.get("default") is True and k in saved]
    blank_text = sum(not str(saved.get(k) or "").strip() for k in text_keys)
    blank_number = sum(saved.get(k) in (None, "") for k in number_keys)
    stale_snapshot = (len(text_keys) >= 5 and blank_text >= 3 and len(number_keys) >= 5
                      and blank_number >= 2 and true_defaults
                      and all(saved.get(k) is False for k in true_defaults))
    if stale_snapshot:
        for key, spec in schema.items():
            if "default" in spec and spec.get("type") != "action":
                updates[key] = spec["default"]

    if updates:
        ctx.update_config(updates)
        ctx.log.info("[Telegram 助手] 已补全 %d 项默认配置", len(updates))


async def setup(ctx):
    await _migrate_old_configs(ctx)
    _restore_defaults(ctx)
    modules = [
        (msg_forward, _FORWARD, ("forward_enable", "forward_repeat_enabled")),
        (self_delete, _DELETE, ("delete_enabled",)),
        (id_plugin, _ID, ("id_enabled",)),
        (getmsg, _GETMSG, ("getmsg_enabled",)),
        (message_sticker, _STICKER, ("sticker_enabled",)),
        (auto_avatar, _AVATAR, ("avatar_enabled",)),
        (auto_changename, _NICKNAME, ("nickname_enabled",)),
    ]
    initialized = []
    try:
        for module, mapping, switches in modules:
            if not any(bool(ctx.config.get(key, False)) for key in switches):
                continue
            await module.setup(_ModuleContext(ctx, mapping))
            initialized.append(module)
        ctx.log.info("[Telegram 助手] 已启用 %d 个功能模块", len(initialized))
    except Exception:
        for module in reversed(initialized):
            try:
                await module.teardown(_ModuleContext(ctx, dict()))
            except Exception:
                pass
        raise


async def teardown(ctx):
    for module in (auto_changename, auto_avatar, message_sticker, getmsg, id_plugin, self_delete, msg_forward):
        try:
            await module.teardown(_ModuleContext(ctx, {}))
        except Exception:
            pass
    ctx.log.info("[Telegram 助手] 已停用")
