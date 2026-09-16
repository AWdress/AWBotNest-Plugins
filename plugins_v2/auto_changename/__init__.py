"""AWBotNest V2 自动报时昵称：时间、特殊字体数字与天气。"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

__plugin__ = {
    "id": "auto_changename", "name": "自动报时昵称", "version": "2.0.5",
    "author": "AWdress", "scope": "user", "plugin_api_version": 2,
    "description": "定时把昵称改成当前时间、天气图标和温度，支持特殊字体与自定义模板。",
    "requirements": [],
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cleanup.png",
    "tags": ["昵称报时", "天气", "定时任务"], "render_mode": "schema",
    "resources": {"timeout_seconds": 60, "max_concurrency": 4, "max_background_tasks": 8, "failure_threshold": 5},
    "config_schema": {
        "interval_min": {"type": "slider", "default": 5, "label": "改名间隔(分钟)", "min": 1, "max": 60, "step": 1, "order": 10, "section": "更新计划", "help": "每隔多少分钟改一次。修改后需重载插件生效。"},
        "name_format": {"type": "string", "default": "{boldH}:{boldM} {weather_icon} {temp}°C", "label": "昵称模板", "order": 11, "section": "昵称规则", "help": "占位符：{boldH}:{boldM}特殊字体时分，{H}:{M}普通时分，{weather_icon}天气图标，{temp}温度，{emoji}随机表情，{date}日期，{week}星期。"},
        "name_field": {"type": "select", "default": "last_name", "label": "修改哪个名字（姓 / 名 / 姓和名）", "order": 12, "section": "昵称规则", "help": "可选：姓、名或姓和名。", "options": [{"value": "last_name", "label": "姓 (last name)"}, {"value": "first_name", "label": "名 (first name)"}, {"value": "both", "label": "姓和名都改"}]},
        "location": {"type": "string", "default": "Guangzhou", "label": "城市(英文)", "order": 5, "section": "天气", "help": "城市英文名，如 Guangzhou、Beijing、Shanghai；留空使用 Guangzhou。"},
        "weather_interval": {"type": "slider", "default": 30, "label": "天气刷新间隔(分钟)", "min": 10, "max": 120, "step": 5, "order": 6, "section": "天气", "help": "天气数据缓存时间，避免频繁请求。"},
    },
    "changelog": "v2.0.5 接入时间与天气昵称模板\n- 支持特殊字体数字、天气图标、温度和城市配置\n- 使用平台 HTTP 代理获取 wttr.in 天气并缓存结果\n- 保留原有账号选择、定时任务和昵称字段设置",
}

DEFAULT_FORMAT = "{boldH}:{boldM} {weather_icon} {temp}°C"
_EMOJIS = [chr(i) for i in range(0x1F600, 0x1F637 + 1)]
_WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
_TZ8 = timezone(timedelta(hours=8))
_BOLD_DIGITS = str.maketrans("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗")
_WEATHER_CACHE = {"key": "", "data": None, "time": 0.0}


def _to_bold(value: str) -> str:
    return value.translate(_BOLD_DIGITS)


async def _get_weather(ctx, location: str, cache_minutes: int = 30) -> dict:
    now = datetime.now(_TZ8).timestamp()
    key = str(location or "Guangzhou").strip() or "Guangzhou"
    if (_WEATHER_CACHE["data"] and _WEATHER_CACHE["key"].casefold() == key.casefold()
            and now - _WEATHER_CACHE["time"] < max(10, int(cache_minutes or 30)) * 60):
        return _WEATHER_CACHE["data"]
    result = {"temp": "?", "desc": "", "icon": "🌤", "humidity": "?", "wind": "?"}
    try:
        response = await ctx.http.get(f"https://wttr.in/{key}?format=j1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = (data.get("current_condition") or [{}])[0]
            result = {
                "temp": current.get("temp_C", "?"),
                "desc": (current.get("weatherDesc") or [{}])[0].get("value", ""),
                "icon": _weather_code_to_icon(current.get("weatherCode", 0)),
                "humidity": current.get("humidity", "?"),
                "wind": current.get("windspeedKmph", "?"),
            }
            _WEATHER_CACHE.update({"key": key, "data": result, "time": now})
    except Exception:
        pass
    return result


def _weather_code_to_icon(code: int) -> str:
    icons = {113: "☀️", 116: "⛅", 119: "☁️", 122: "☁️", 143: "🌫", 176: "🌦", 179: "🌧", 182: "🌧", 185: "🌧", 200: "⛈", 227: "🌨", 230: "🌨", 248: "🌫", 260: "🌫", 263: "🌦", 266: "🌦", 281: "🌧", 284: "🌧", 293: "🌦", 296: "🌦", 299: "🌧", 302: "🌧", 305: "🌧", 308: "🌧", 311: "🌧", 314: "🌧", 317: "🌧", 320: "🌨", 323: "🌨", 326: "🌨", 329: "🌨", 332: "🌨", 335: "🌨", 338: "🌨", 350: "🌧", 353: "🌦", 356: "🌧", 359: "🌧", 362: "🌧", 365: "🌧", 368: "🌨", 371: "🌨", 374: "🌧", 377: "🌧", 386: "⛈", 389: "⛈", 392: "⛈", 395: "🌨"}
    try:
        return icons.get(int(code), "🌤")
    except (TypeError, ValueError):
        return "🌤"


def _render_name(fmt: str, now: datetime, weather: dict) -> str:
    return (str(fmt or DEFAULT_FORMAT).replace("{emoji}", random.choice(_EMOJIS))
            .replace("{H}", now.strftime("%H")).replace("{M}", now.strftime("%M")).replace("{S}", now.strftime("%S"))
            .replace("{boldH}", _to_bold(now.strftime("%H"))).replace("{boldM}", _to_bold(now.strftime("%M"))).replace("{boldS}", _to_bold(now.strftime("%S")))
            .replace("{date}", now.strftime("%Y-%m-%d")).replace("{md}", now.strftime("%m-%d"))
            .replace("{week}", _WEEK_CN[now.weekday()]).replace("{weather_icon}", weather.get("icon", "🌤"))
            .replace("{temp}", str(weather.get("temp", "?"))).replace("{desc}", weather.get("desc", ""))
            .replace("{humidity}", str(weather.get("humidity", "?"))).replace("{wind}", str(weather.get("wind", "?"))))


def _restore_defaults(ctx) -> None:
    updates = {}
    for key, spec in __plugin__["config_schema"].items():
        if "default" not in spec:
            continue
        current = ctx.config.get(key)
        if key not in ctx.config or current is None or (isinstance(current, str) and not current.strip()):
            updates[key] = spec["default"]
    if updates:
        ctx.update_config(updates)


async def setup(ctx):
    _restore_defaults(ctx)
    try:
        interval = max(1, min(int(ctx.config.get("interval_min", 5) or 5), 60))
    except (TypeError, ValueError):
        interval = 5

    async def update_names():
        users = tuple(ctx.users)
        if not users:
            return
        cfg = ctx.config
        weather = await _get_weather(ctx, str(cfg.get("location", "Guangzhou") or "Guangzhou"), int(cfg.get("weather_interval", 30) or 30))
        now = datetime.now(_TZ8)
        field = str(cfg.get("name_field") or "last_name")
        rendered = _render_name(str(cfg.get("name_format") or DEFAULT_FORMAT), now, weather)
        kwargs = {}
        if field in {"last_name", "both"}:
            kwargs["last_name"] = rendered
        if field in {"first_name", "both"}:
            kwargs["first_name"] = rendered
        if not kwargs:
            kwargs["last_name"] = rendered
        from telethon.tl.functions.account import UpdateProfileRequest
        for app in users:
            try:
                await app(UpdateProfileRequest(first_name=kwargs.get("first_name"), last_name=kwargs.get("last_name")))
            except Exception as error:
                ctx.log.warning("[自动报时] 改名失败：%r", error)

    ctx.schedule_interval("自动报时昵称", update_names, seconds=interval * 60)
    ctx.log.info("[自动报时] 已启用，每 %d 分钟，城市：%s", interval, ctx.config.get("location", "Guangzhou"))


async def teardown(ctx):
    pass
