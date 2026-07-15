# =============================================================================
# AWBotNest 插件：自动订阅助手（auto_subscribe）· Vue 模式
#
# 聚合多个榜单源（豆瓣 / Mikan 新番 / 奈飞 / 猫眼），按全局或每源独立过滤条件筛选后，
# 通过 NextFind OpenAPI 自动订阅（POST /subscriptions/add）。定时运行 + 结果推送，
# 配置/管理界面由自带的 Vue 组件渲染（frontend/src/Config.vue，模块联邦）。
#
# 迁移自 MoviePilot 插件 automaticsubscriptionassistant（Aqr-K）。落地后端改为 NextFind：
# 一次 /search 即得 tmdb/类型/年份/评分/是否已订阅/是否入库，识别+去重+库查重+评分合并为一步。
# popular 源依赖 MoviePilot 自建统计服务器，未迁；猫眼用平台 ctx.browser 预取 Cookie（取不到降级）。
# =============================================================================

import asyncio
from datetime import datetime

from ._models import STATUS_LABELS

__plugin__ = {
    "name": "自动订阅助手",
    "id": "auto_subscribe",
    "version": "0.0.9",
    "author": "AWdress",
    "description": "聚合豆瓣/Mikan新番/奈飞(全球+国家榜)/猫眼榜单，按全局或每源独立过滤自动订阅到 NextFind。定时运行 + 结果推送，自带 Vue 管理界面。",
    "scope": "user",
    "default_enabled": False,
    # 配置/管理界面由插件自带 Vue 组件渲染（frontend/src/Config.vue）。
    "render_mode": "vue",
}

# 配置默认值（vue 模式无 config_schema，默认值集中在此，供定时任务/后端读取；
# 前端 Config.vue 也用同一套默认初始化表单）。
DEFAULTS = {
    "api_url": "", "api_key": "",
    "schedule": "0 8 * * *", "notify": True,
    "min_year": 0, "min_vote": 0, "min_popularity": 0, "media_type": "all",
    # 豆瓣
    "douban_enabled": False, "douban_ranks": ["movie-hot-gaia", "tv-hot"],
    "douban_rsshub": "https://rsshub.app", "douban_rss_custom": "",
    "douban_filter_custom": False, "douban_min_year": 0, "douban_min_vote": 0,
    "douban_media_type": "all",
    # Mikan
    "mikan_enabled": False, "mikan_season": "当前", "mikan_year": 0,
    "mikan_resolve_detail": True,
    "mikan_filter_custom": False, "mikan_min_year": 0, "mikan_min_vote": 0,
    # 奈飞
    "netflix_enabled": False, "netflix_global": True,
    "netflix_dataset": "all-weeks-global",
    "netflix_media_types": ["Films (English)", "Films (Non-English)", "TV (English)", "TV (Non-English)"],
    "netflix_countries": [], "netflix_country_types": ["Films", "TV"],
    "netflix_limit": 10, "netflix_rich": True,
    "netflix_filter_custom": False, "netflix_min_year": 0, "netflix_min_vote": 0,
    "netflix_media_type": "all",
    # 猫眼
    "maoyan_enabled": False, "maoyan_movie_box": True,
    "maoyan_web_platforms": [], "maoyan_web_types": [], "maoyan_num": 10,
    "maoyan_filter_custom": False, "maoyan_min_year": 0, "maoyan_min_vote": 0,
    "maoyan_media_type": "all",
}

# 来源 id -> 展示名（通知汇总用）。
SOURCE_NAMES = {
    "douban": "豆瓣榜单", "mikan": "Mikan新番", "netflix": "奈飞榜单", "maoyan": "猫眼榜单",
}
_ENABLE_KEYS = ("douban_enabled", "mikan_enabled", "netflix_enabled", "maoyan_enabled")


def _effective_cfg(ctx) -> dict:
    """默认值 + 已保存配置合并（保存的覆盖默认）。"""
    return {**DEFAULTS, **dict(ctx.config or {})}


def _summary(result, label: str) -> str:
    """把一轮结果格式化成通知/返回文本。"""
    # 鉴权失败：一目了然地报因，别淹没在一堆「失败N」里。
    if getattr(result, "auth_error", ""):
        return (f"📥 自动订阅 · {label}\n❌ {result.auth_error}\n"
                f"请到「设置」页更新 NextFind API 密钥（可点「测试连接」验证）后重试。")
    lines = [f"📥 自动订阅 · {label}"]
    for src, st in result.stats.items():
        parts = [f"{STATUS_LABELS.get(k, k)}{v}" for k, v in st.items() if v]
        lines.append(f"[{SOURCE_NAMES.get(src, src)}] " + ("，".join(parts) if parts else "无产出"))
    for src, err in result.errors.items():
        lines.append(f"⚠️ {SOURCE_NAMES.get(src, src)} 抓取失败：{str(err)[:80]}")
    if result.added:
        shown = "、".join(result.added[:15])
        more = f" 等 {len(result.added)} 部" if len(result.added) > 15 else ""
        lines.append(f"✅ 新增订阅：{shown}{more}")
    else:
        lines.append("本轮无新增订阅")
    return "\n".join(lines)


async def _run(ctx, label: str) -> str:
    """执行一轮：阻塞流水线跑在 to_thread，通知/kv 在事件循环。返回汇总文本。"""
    cfg = _effective_cfg(ctx)
    if not cfg.get("api_url") or not cfg.get("api_key"):
        msg = "未配置 NextFind 地址或密钥，跳过"
        ctx.log.warning("[自动订阅] %s", msg)
        return msg
    if not any(cfg.get(k) for k in _ENABLE_KEYS):
        msg = "未启用任何榜单源，跳过"
        ctx.log.warning("[自动订阅] %s", msg)
        return msg

    from . import _pipeline

    # 猫眼启用时先在事件循环里用平台浏览器取 Cookie，注入 cfg 供流水线（跑在线程里）用。
    if cfg.get("maoyan_enabled"):
        cfg["maoyan_cookies"] = await _fetch_maoyan_cookies(ctx)

    handled = ctx.kv.get("handled", {})
    nf_cache = ctx.kv.get("netflix_cache", {})
    ctx.log.info("[自动订阅] 开始运行(%s)", label)
    try:
        result = await asyncio.to_thread(_pipeline.run, cfg, handled, nf_cache, ctx.log)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[自动订阅] 运行异常: %r", e)
        if cfg.get("notify", True):
            await ctx.notify(f"自动订阅运行异常：{e}", level="error", category="自动订阅")
        return f"运行异常：{e}"

    ctx.kv.set("handled", result.handled)
    ctx.kv.set("netflix_cache", result.nf_cache)
    # 汇总本轮各状态计数（跨来源相加），供前端「订阅历史」顶部统计卡展示。
    agg: dict = {}
    for st in result.stats.values():
        for k, v in st.items():
            agg[k] = agg.get(k, 0) + v
    ctx.update_config({
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_stats": agg,
    })

    summary = _summary(result, label)
    # 通知是「尽力而为」：投递失败（无在线账号/Bot 无目标等）只告警，绝不让整轮运行失败
    # （订阅其实已经落地）。notifier.submit 无可用账号时会抛 RuntimeError。
    if cfg.get("notify", True):
        level = "error" if result.errors else ("success" if result.added else "info")
        try:
            await ctx.notify(summary, level=level, category="自动订阅")
        except Exception as e:  # noqa: BLE001 - 通知失败不影响运行结果
            ctx.log.warning("[自动订阅] 结果通知投递失败（不影响运行）：%r", e)
    ctx.log.info("[自动订阅] 完成(%s)：新增 %d 部", label, len(result.added))
    return summary


def _nf_client(cfg):
    """构造 NextFind 客户端（局部 import 避免顶层依赖）。"""
    from ._nextfind import NextFindClient
    return NextFindClient(cfg.get("api_url", ""), cfg.get("api_key", ""))


async def _fetch_maoyan_cookies(ctx) -> dict:
    """用平台 ctx.browser 预取猫眼 Cookie（{name: value}）；失败降级空 dict（无 Cookie）。

    provider 跑在 to_thread 里不能直接 await 浏览器，故在事件循环里先取好再注入 cfg。
    首次调用会触发平台下载浏览器内核（之后有缓存）。
    """
    from ._maoyan import MAOYAN_URL

    def _grab(page):
        try:
            return {c["name"]: c["value"] for c in page.context.cookies()}
        except Exception:  # noqa: BLE001 - 引擎不支持 context.cookies 时降级
            return {}
    try:
        return await ctx.browser.run(MAOYAN_URL, _grab, headless=True, timeout=30) or {}
    except Exception as e:  # noqa: BLE001 - 浏览器不可用/超时降级无 Cookie
        ctx.log.warning("[自动订阅] 猫眼 Cookie 获取失败，降级无 Cookie：%r", e)
        return {}


# 奈飞国家常用地区中文名（其余用英文名），供前端下拉展示。
_COUNTRY_ZH = {
    "US": "美国", "GB": "英国", "JP": "日本", "KR": "韩国", "TW": "台湾", "HK": "香港",
    "FR": "法国", "DE": "德国", "IT": "意大利", "ES": "西班牙", "CA": "加拿大",
    "AU": "澳大利亚", "BR": "巴西", "IN": "印度", "TH": "泰国", "SG": "新加坡",
    "MY": "马来西亚", "ID": "印度尼西亚", "PH": "菲律宾", "VN": "越南", "RU": "俄罗斯",
    "MX": "墨西哥", "NL": "荷兰", "SE": "瑞典", "NO": "挪威", "DK": "丹麦", "FI": "芬兰",
    "PL": "波兰", "TR": "土耳其", "SA": "沙特阿拉伯", "AE": "阿联酋", "EG": "埃及", "ZA": "南非",
}


def _country_options() -> list:
    """奈飞国家下拉选项（单一数据源来自 _netflix.COUNTRIES）。"""
    from ._netflix import COUNTRIES
    return [{"value": iso2, "label": _COUNTRY_ZH.get(iso2, name)} for iso2, name in COUNTRIES.items()]


async def setup(ctx):
    # ── 前端(Config.vue)用的后端接口 ──
    @ctx.on_api("/meta", methods=["GET"])
    async def _api_meta(req):
        return {"countries": _country_options()}

    @ctx.on_api("/test", methods=["GET"])
    async def _api_test(req):
        cfg = _effective_cfg(ctx)
        if not cfg.get("api_url") or not cfg.get("api_key"):
            return {"ok": False, "message": "请先填写 NextFind 地址与密钥"}
        try:
            data = await asyncio.to_thread(lambda: _nf_client(cfg).quota())
            return {"ok": True, "quota": data}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    @ctx.on_api("/run", methods=["POST"])
    async def _api_run(req):
        # 兜底捕获，把真实原因回给前端（否则平台 dispatcher 只回 500，UI 显示 "Error"）。
        try:
            summary = await _run(ctx, "手动")
            return {"ok": True, "summary": summary}
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动订阅] 手动运行失败: %r", e)
            return {"ok": False, "summary": f"运行失败：{e}"}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        handled = ctx.kv.get("handled", {})
        items = [{"key": k, **v} for k, v in handled.items()]
        items.sort(key=lambda x: x.get("time", ""), reverse=True)
        return {
            "items": items,
            "last_run": ctx.config.get("last_run", ""),
            "stats": ctx.config.get("last_stats", {}),
        }

    @ctx.on_api("/history/delete", methods=["POST"])
    async def _api_history_delete(req):
        data = req.json or {}
        if data.get("clear"):
            ctx.kv.set("handled", {})
            return {"ok": True, "cleared": True}
        handled = ctx.kv.get("handled", {})
        key = data.get("key")
        if key in handled:
            handled.pop(key)
            ctx.kv.set("handled", handled)
        return {"ok": True}

    @ctx.on_api("/subscriptions", methods=["GET"])
    async def _api_subscriptions(req):
        cfg = _effective_cfg(ctx)
        if not cfg.get("api_url") or not cfg.get("api_key"):
            return {"items": [], "error": "未配置地址或密钥"}
        try:
            data = await asyncio.to_thread(lambda: _nf_client(cfg).list_subscriptions())
            return {"items": data}
        except Exception as e:  # noqa: BLE001
            return {"items": [], "error": str(e)}

    @ctx.on_api("/subscriptions/remove", methods=["POST"])
    async def _api_subscriptions_remove(req):
        data = req.json or {}
        cfg = _effective_cfg(ctx)
        tmdb_id, media_type = data.get("tmdb_id"), data.get("media_type")
        if not tmdb_id or not media_type:
            return {"ok": False, "message": "缺少 tmdb_id 或 media_type"}
        try:
            ok, msg = await asyncio.to_thread(lambda: _nf_client(cfg).remove(tmdb_id, media_type))
            return {"ok": ok, "message": msg}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    # ── 定时任务（cron 无效时仅告警，手动运行仍可用）──
    expr = str(_effective_cfg(ctx).get("schedule") or "").strip()
    if expr:
        try:
            from apscheduler.triggers.cron import CronTrigger
            trigger = CronTrigger.from_crontab(expr)
            ctx.schedule(lambda: asyncio.create_task(_run(ctx, "定时")),
                         trigger, id="auto_subscribe")
            ctx.log.info("[自动订阅] 已注册定时任务：%s", expr)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动订阅] 定时表达式无效(%s): %r", expr, e)


async def teardown(ctx):
    pass
