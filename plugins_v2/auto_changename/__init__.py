"""AWBotNest V2 native automatic clock nickname plugin."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from telethon import functions

__plugin__ = {
    "id": "auto_changename", "name": "自动报时昵称", "version": "2.0.0",
    "author": "AWdress", "scope": "user", "plugin_api_version": 2,
    "description": "定时把你的账号昵称改成当前时间，支持自定义模板（时分秒、日期、星期和随机表情）。",
    "requirements": [],
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cleanup.png",
    "tags": ["昵称报时", "日期模板", "定时任务"], "render_mode": "schema",
    "config_schema": {
        "interval_min": {"type": "number", "default": 5, "label": "改名间隔(分钟)", "min": 1, "max": 60, "step": 1, "order": 10, "section": "更新计划", "help": "每隔多少分钟改一次。修改后需重载插件生效。"},
        "name_format": {"type": "string", "default": "{emoji}{H}:{M}", "label": "昵称模板", "order": 11, "section": "昵称规则", "help": "占位符：{emoji}随机表情 {H}时 {M}分 {S}秒 {date}年-月-日 {md}月-日 {week}星期几"},
        "name_field": {"type": "select", "default": "last_name", "label": "改哪个名", "order": 12, "section": "昵称规则", "options": [{"value": "last_name", "label": "姓 (last name)"}, {"value": "first_name", "label": "名 (first name)"}, {"value": "both", "label": "姓和名都改"}]},
    },
    "changelog": "v2.0.0 原生 AWBotNest V2 迁移\n- 移除 V1 兼容运行层\n- 使用原生 Telethon 账号资料接口\n- 使用平台原生定时任务与生命周期管理",
}

DEFAULT_FORMAT = "{emoji}{H}:{M}"
_EMOJIS = [chr(i) for i in range(0x1F600, 0x1F638)]
_WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_TZ8 = timezone(timedelta(hours=8))

def _render_name(fmt: str, now: datetime) -> str:
    return (fmt.replace("{emoji}", random.choice(_EMOJIS)).replace("{H}", now.strftime("%H"))
            .replace("{M}", now.strftime("%M")).replace("{S}", now.strftime("%S"))
            .replace("{date}", now.strftime("%Y-%m-%d")).replace("{md}", now.strftime("%m-%d"))
            .replace("{week}", _WEEK_CN[now.weekday()]))

def _interval(config: dict) -> int:
    try:
        value = int(config.get("interval_min", 5) or 5)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 60))

async def setup(ctx):
    async def update_names():
        users = tuple(ctx.users)
        if not users:
            ctx.log.debug("[自动报时] 无已连接用户账号，跳过")
            return
        rendered = _render_name(str(ctx.config.get("name_format") or DEFAULT_FORMAT), datetime.now(_TZ8))
        field = str(ctx.config.get("name_field") or "last_name")
        kwargs = {}
        if field in {"last_name", "both"}: kwargs["last_name"] = rendered
        if field in {"first_name", "both"}: kwargs["first_name"] = rendered
        if not kwargs: kwargs["last_name"] = rendered
        for client in users:
            try:
                await client(functions.account.UpdateProfileRequest(**kwargs))
            except Exception as error:
                ctx.log.warning("[自动报时] 账号改名失败: %r", error)

    minutes = _interval(ctx.config)
    ctx.schedule_interval("自动报时昵称", update_names, seconds=minutes * 60)
    ctx.log.info("[自动报时] 原生 V2 插件已启用，每 %d 分钟更新", minutes)

async def teardown(ctx):
    ctx.log.info("[自动报时] 已停用")
