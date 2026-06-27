# =============================================================================
# AWBotNest 插件：自动报时昵称（auto_changename）
#
# 定时把你的用户账号昵称改成当前时间（按模板渲染）。多账号会逐个改。
# 启用插件即生效；间隔/格式/改哪个名都在配置里调。
#
# 注意：改了「间隔分钟」后需在平台「重载」本插件让新间隔生效（定时任务在
#       setup 时按当前间隔注册）；格式/字段改完即时生效（每次运行读最新配置）。
# =============================================================================

import random
from datetime import datetime, timedelta, timezone

__plugin__ = {
    "name": "自动报时昵称",
    "id": "auto_changename",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "定时把你的账号昵称改成当前时间，支持自定义模板（时分秒/日期/星期/随机表情）。",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "interval_min": {
            "type": "slider", "default": 5, "label": "改名间隔(分钟)",
            "min": 1, "max": 60, "step": 1, "section": "参数",
            "help": "每隔多少分钟改一次。改这个值后需「重载」插件生效。",
        },
        "name_format": {
            "type": "string", "default": "{emoji}{H}:{M}", "label": "昵称模板",
            "section": "参数",
            "help": "占位符：{emoji}随机表情 {H}时 {M}分 {S}秒 {date}年-月-日 {md}月-日 {week}星期几",
        },
        "name_field": {
            "type": "select", "default": "last_name", "label": "改哪个名",
            "section": "参数",
            "options": [
                {"value": "last_name", "label": "姓 (last name)"},
                {"value": "first_name", "label": "名 (first name)"},
                {"value": "both", "label": "姓和名都改"},
            ],
        },
    },
}

DEFAULT_FORMAT = "{emoji}{H}:{M}"
_EMOJIS = [chr(i) for i in range(0x1F600, 0x1F637 + 1)]  # 56 个表情
_WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_TZ8 = timezone(timedelta(hours=8))


def _render_name(fmt: str, now: datetime) -> str:
    """按模板渲染昵称；每次调用 {emoji} 随机取一个。"""
    return (
        fmt.replace("{emoji}", random.choice(_EMOJIS))
        .replace("{H}", now.strftime("%H"))
        .replace("{M}", now.strftime("%M"))
        .replace("{S}", now.strftime("%S"))
        .replace("{date}", now.strftime("%Y-%m-%d"))
        .replace("{md}", now.strftime("%m-%d"))
        .replace("{week}", _WEEK_CN[now.weekday()])
    )


def _make_action(ctx):
    async def _action():
        user_apps = ctx.user_apps
        if not user_apps:
            ctx.log.debug("[自动报时] 无已连接用户账号，跳过")
            return

        cfg = ctx.config
        fmt = cfg.get("name_format") or DEFAULT_FORMAT
        field = cfg.get("name_field") or "last_name"
        now = datetime.now(_TZ8)

        for app in user_apps:
            acct = getattr(app, "name", "未知账号")
            try:
                rendered = _render_name(fmt, now)
                kwargs = {}
                if field in ("last_name", "both"):
                    kwargs["last_name"] = rendered
                if field in ("first_name", "both"):
                    kwargs["first_name"] = rendered
                if not kwargs:  # 配置异常兜底
                    kwargs["last_name"] = rendered
                await app.update_profile(**kwargs)
            except Exception as e:  # noqa: BLE001
                ctx.log.warning("[自动报时] 账号 %s 改名失败: %r", acct, e)

    return _action


async def setup(ctx):
    try:
        interval = int(ctx.config.get("interval_min", 5) or 5)
    except (ValueError, TypeError):
        interval = 5
    interval = max(1, min(interval, 60))

    # cron 每 interval 分钟（与旧实现一致：minute=*/interval）
    ctx.schedule(_make_action(ctx), "cron", minute=f"*/{interval}", id="自动报时昵称")
    ctx.log.info("[自动报时] 已启用，每 %d 分钟", interval)


async def teardown(ctx):
    # ctx.schedule 注册的任务由平台停用时自动移除
    pass
