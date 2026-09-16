"""Telegram 助手：合并消息工具与账号资料自动化。"""
from __future__ import annotations

from typing import Any, Mapping

from .. import auto_avatar, auto_changename, getmsg, id as id_plugin, msg_forward, self_delete


__plugin__ = {
    "id": "telegram_assistant",
    "name": "Telegram 助手",
    "version": "0.0.2",
    "author": "AWdress",
    "scope": "user",
    "plugin_api_version": 2,
    "requirements": [],
    "render_mode": "schema",
    "description": "Telegram 消息与账号工具集合：转发、删除消息、查询 ID、消息结构导出、自动换头像和自动报时昵称。",
    "icon": "https://cdn.simpleicons.org/telegram/26A5E4",
    "tags": ["Telegram", "消息工具", "账号自动化"],
    "resources": {"timeout_seconds": 300, "max_concurrency": 8, "max_background_tasks": 32},
    "config_schema": {
        "forward_enable": {"type": "boolean", "default": False, "label": "启用规则转发", "section": "消息转发", "order": 1},
        "forward_album": {"type": "boolean", "default": True, "label": "整组转发相册", "section": "消息转发", "order": 2},
        "forward_backfill_limit": {"type": "integer", "default": 100, "min": 1, "max": 500, "label": "遗漏补全回查条数", "section": "消息转发", "order": 3},
        "forward_auto_backfill": {"type": "boolean", "default": True, "label": "自动检查遗漏", "section": "消息转发", "order": 4},
        "forward_backfill_interval_min": {"type": "number", "default": 10, "min": 1, "max": 1440, "step": 1, "label": "遗漏检查间隔（分钟）", "section": "消息转发", "order": 5},
        "forward_repeat_enabled": {"type": "boolean", "default": True, "label": "启用回复复读", "section": "消息转发", "order": 6},
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
        "delete_command": {"type": "string", "default": ".dme", "label": "删除消息命令", "section": "消息管理", "order": 30},
        "delete_tip_seconds": {"type": "number", "default": 2, "min": 0, "max": 10, "step": 1, "label": "删除提示停留（秒）", "section": "消息管理", "order": 31},
        "id_delete_command": {"type": "boolean", "default": True, "label": "查询后删除命令", "section": "查 ID", "order": 40},
        "id_command": {"type": "string", "default": ".id", "label": "查 ID 命令", "section": "查 ID", "order": 41},
        "id_auto_delete": {"type": "number", "default": 20, "min": 0, "max": 120, "step": 5, "label": "结果自动删除（秒）", "section": "查 ID", "order": 42},
        "getmsg_delete_command": {"type": "boolean", "default": True, "label": "导出后删除命令", "section": "消息结构", "order": 50},
        "getmsg_command": {"type": "string", "default": ".getmsg", "label": "消息结构命令", "section": "消息结构", "order": 51},
        "avatar_delete_old": {"type": "boolean", "default": True, "label": "删除旧头像", "section": "自动换头像", "order": 60},
        "avatar_interval_min": {"type": "number", "default": 60, "min": 10, "max": 1440, "step": 10, "label": "换头像间隔（分钟）", "section": "自动换头像", "order": 61},
        "avatar_add_command": {"type": "string", "default": ".avataradd", "label": "加图命令", "section": "自动换头像", "order": 62},
        "avatar_list_command": {"type": "string", "default": ".avatarlist", "label": "查看图片池命令", "section": "自动换头像", "order": 63},
        "avatar_clear_command": {"type": "string", "default": ".avatarclear", "label": "清空图片池命令", "section": "自动换头像", "order": 64},
        "nickname_interval_min": {"type": "number", "default": 5, "min": 1, "max": 60, "step": 1, "label": "昵称更新时间（分钟）", "section": "报时昵称", "order": 70},
        "nickname_name_format": {"type": "string", "default": "{boldH}:{boldM} {weather_icon} {temp}°C", "label": "昵称模板", "section": "报时昵称", "order": 71, "help": "占位符：{boldH}:{boldM}特殊字体时分，{H}:{M}普通时分，{weather_icon}天气图标，{temp}温度，{emoji}随机表情，{date}日期，{week}星期。"},
        "nickname_name_field": {"type": "select", "default": "last_name", "label": "修改哪个名字（姓 / 名 / 姓和名）", "section": "报时昵称", "order": 72, "help": "可选：姓、名或姓和名。", "options": [{"value": "last_name", "label": "姓"}, {"value": "first_name", "label": "名"}, {"value": "both", "label": "姓和名"}]},
        "nickname_location": {"type": "string", "default": "Guangzhou", "label": "天气城市（英文）", "section": "报时昵称", "order": 73, "help": "例如 Guangzhou、Beijing；用于获取昵称中的天气和温度。"},
        "nickname_weather_interval": {"type": "number", "default": 30, "min": 10, "max": 120, "step": 5, "label": "天气刷新间隔（分钟）", "section": "报时昵称", "order": 74},
    },
    "changelog": "v0.0.2 更新自动报时昵称\n- 使用时间特殊字体、天气图标和温度模板\n- 增加天气城市与天气缓存间隔配置\n\nv0.0.1 首次发布\n- 合并消息转发、删除消息、查 ID、消息结构、自动换头像和自动报时昵称\n- 保留原有命令、规则和定时行为，启用时自动迁移旧插件配置\n- 使用 Telegram 官方图标",
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
_AVATAR = {"avatar_delete_old": "delete_old", "avatar_interval_min": "interval_min", "avatar_add_command": "add_command", "avatar_list_command": "list_command", "avatar_clear_command": "clear_command"}
_NICKNAME = {"nickname_interval_min": "interval_min", "nickname_name_format": "name_format", "nickname_name_field": "name_field", "nickname_location": "location", "nickname_weather_interval": "weather_interval"}


def _migrate_old_configs(ctx):
    settings = getattr(ctx, "settings", None)
    configs = getattr(settings, "plugin_config", None)
    if not isinstance(configs, dict):
        return
    maps = {"msg_forward": _FORWARD, "self_delete": _DELETE, "id": _ID, "getmsg": _GETMSG, "auto_avatar": _AVATAR, "auto_changename": _NICKNAME}
    updates = {}
    for plugin_id, mapping in maps.items():
        old = configs.get(plugin_id)
        if not isinstance(old, dict):
            continue
        for namespaced, legacy in mapping.items():
            if namespaced not in ctx.config and legacy in old:
                updates[namespaced] = old[legacy]
    if updates:
        ctx.update_config(updates)
        ctx.log.info("[Telegram 助手] 已迁移 %s 个旧插件配置项", len(updates))
    enabled = getattr(settings, "enabled_plugins", None)
    if isinstance(enabled, list):
        removed = [name for name in maps if name in enabled]
        for name in removed:
            enabled.remove(name)
        if removed:
            ctx.log.info("[Telegram 助手] 已停用旧插件：%s", ", ".join(removed))


def _restore_defaults(ctx):
    """Materialize schema defaults so the native form can display and save them."""
    updates = {}
    for key, spec in __plugin__["config_schema"].items():
        if "default" not in spec or spec.get("type") == "action":
            continue
        current = ctx.config.get(key)
        if key not in ctx.config or current is None or (isinstance(current, str) and not current.strip()):
            updates[key] = spec["default"]
    if updates:
        ctx.update_config(updates)


async def setup(ctx):
    _migrate_old_configs(ctx)
    _restore_defaults(ctx)
    modules = [
        (msg_forward, _FORWARD), (self_delete, _DELETE), (id_plugin, _ID),
        (getmsg, _GETMSG), (auto_avatar, _AVATAR), (auto_changename, _NICKNAME),
    ]
    initialized = []
    try:
        for module, mapping in modules:
            await module.setup(_ModuleContext(ctx, mapping))
            initialized.append(module)
        ctx.log.info("[Telegram 助手] 已启用 6 个功能模块")
    except Exception:
        for module in reversed(initialized):
            try:
                await module.teardown(_ModuleContext(ctx, dict()))
            except Exception:
                pass
        raise


async def teardown(ctx):
    for module in (auto_changename, auto_avatar, getmsg, id_plugin, self_delete, msg_forward):
        try:
            await module.teardown(_ModuleContext(ctx, {}))
        except Exception:
            pass
    ctx.log.info("[Telegram 助手] 已停用")
