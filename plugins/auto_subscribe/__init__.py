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
import concurrent.futures
import traceback
from datetime import datetime

from ._models import STATUS_LABELS

__plugin__ = {
    "name": "自动订阅助手",
    "id": "auto_subscribe",
    "version": "1.3.0",
    "author": "AWdress",
    "description": "聚合豆瓣/Mikan新番/奈飞(全球+国家榜)/猫眼榜单，支持蜜柑中外文拆分、Bangumi 别名及平台 AI 辅助识别。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/auto_subscribe.png",
    "changelog": "v1.3.0 增强蜜柑番剧识别\n- 自动拆分蜜柑中英、中日混合标题及常见分隔符标题，逐个交给 NextFind 核验\n- 原标题仍搜不到时，根据蜜柑详情页的 Bangumi ID 获取中文名、原名和别名继续搜索\n- 无需额外服务、Endpoint 或 Token；全部候选仍须取得有效 TMDB 结果才会订阅\n\nv1.2.0 新增平台 AI 辅助识别\n- 可选在常规搜索无结果时调用平台 AI 提取标准电影/剧集名、类型与季号\n- AI 结果必须经 NextFind 再次搜索并取得有效 TMDB 结果后才会订阅\n- 默认关闭，平台 AI 不可用或识别失败时安全降级为原有未识别流程\n\nv1.1.0 新增自动补缺集\n- 接入 NextFind /subscriptions/info 批量查询活跃剧集的入库进度\n- 仅对明确存在缺集的订阅调用 /media/fill_missing，并支持配置每轮处理上限\n- 可在不启用榜单源时独立执行补缺，运行通知会显示检查与触发数量\n\nv1.0.6 修复并发运行\n- 新增整轮运行互斥锁，手动与定时并发时跳过重复轮次，避免去重历史互相覆盖",
    "scope": "user",
    "default_enabled": False,
    # 配置/管理界面由插件自带 Vue 组件渲染（frontend/src/Config.vue）。
    "render_mode": "vue",
}

# 配置默认值（vue 模式无 config_schema，默认值集中在此，供定时任务/后端读取；
# 前端 Config.vue 也用同一套默认初始化表单）。
DEFAULTS = {
    "api_url": "", "api_key": "",
    "schedule": "0 8 * * *", "notify": True, "ai_assist_recognition": False,
    "auto_fill_missing": False, "auto_fill_missing_limit": 20,
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


# 整轮运行并发互斥：手动（后台 task）与定时可整轮并发，否则 kv "handled" 去重历史后写覆盖先写。
# 在 setup 内创建，避免模块级锁跨事件循环复用。
_run_lock = None


class _PlatformAIProxy:
    """让同步榜单流水线安全调用平台异步 AI。"""

    def __init__(self, ctx, loop):
        self._ai = ctx.ai
        self._loop = loop

    def is_available(self, capability: str = "text") -> bool:
        checker = getattr(self._ai, "is_available", None)
        if callable(checker):
            return bool(checker(capability))
        return bool(getattr(self._ai, "available", False))

    def chat(self, prompt: str, **kwargs) -> str:
        future = asyncio.run_coroutine_threadsafe(
            self._ai.chat(prompt=prompt, **kwargs),
            self._loop,
        )
        try:
            return str(future.result())
        except concurrent.futures.CancelledError as exc:
            raise RuntimeError("平台 AI 请求已取消") from exc


def _tmdb_id(item: dict) -> str:
    return str(item.get("tmdb_id") or item.get("id") or "").strip()


def _media_type(item: dict) -> str:
    return str(item.get("media_type") or item.get("raw_type") or item.get("type") or "").lower()


def _has_missing_episodes(item: dict) -> bool:
    """只识别响应明确给出的缺集状态，避免字段未知时误触发全库补缺。"""
    for key in ("has_missing", "has_missing_episodes", "is_missing"):
        if item.get(key) is True:
            return True
    for key in ("missing_count", "missing_episode_count"):
        try:
            if int(item.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    missing = item.get("missing_episodes")
    if isinstance(missing, (list, tuple, set, dict)) and len(missing) > 0:
        return True
    try:
        total = int(item.get("total_episodes") or 0)
        local = int(item.get("local_episodes") or item.get("downloaded_episodes") or 0)
        if total > 0 and local < total:
            return True
    except (TypeError, ValueError):
        pass
    return str(item.get("status") or item.get("library_status") or "").lower() == "missing"


def _fill_missing_round(cfg: dict, log=None) -> dict:
    """检查活跃剧集订阅，并只触发明确缺集的项目。"""
    client = _nf_client(cfg)
    subscriptions = client.list_subscriptions()
    tv_items = [item for item in subscriptions if _media_type(item) == "tv" and _tmdb_id(item)]
    query = [{"tmdb_id": _tmdb_id(item), "media_type": "tv"} for item in tv_items]
    details = client.subscription_info(query) if query else []
    by_id = {_tmdb_id(item): item for item in tv_items}
    for detail in details:
        key = _tmdb_id(detail)
        if key:
            by_id[key] = {**by_id.get(key, {}), **detail}
    candidates = [item for item in by_id.values() if _has_missing_episodes(item)]
    limit = max(1, min(int(cfg.get("auto_fill_missing_limit", 20) or 20), 100))
    triggered = failed = 0
    for item in candidates[:limit]:
        tmdb_id = _tmdb_id(item)
        title = str(item.get("title") or "")
        try:
            ok, message = client.fill_missing(tmdb_id, "tv", title)
            triggered += int(ok)
            failed += int(not ok)
            if log:
                log.info("[自动订阅] 补缺集 · %s(%s) → %s%s", title or "未命名", tmdb_id,
                         "已触发" if ok else "失败", f"（{message}）" if message else "")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            if log:
                log.error("[自动订阅] 补缺集 · %s(%s) 调用失败: %r", title or "未命名", tmdb_id, exc)
    return {
        "checked": len(tv_items), "missing": len(candidates),
        "triggered": triggered, "failed": failed,
        "limited": max(0, len(candidates) - limit),
    }


async def _run(ctx, label: str) -> str:
    """执行一轮：阻塞流水线跑在 to_thread，通知/kv 在事件循环。返回汇总文本。"""
    if _run_lock.locked():
        ctx.log.warning("[自动订阅] 上一轮仍在运行，跳过本次运行(%s)", label)
        return "上一轮仍在运行，已跳过"
    async with _run_lock:
        cfg = _effective_cfg(ctx)
        if not cfg.get("api_url") or not cfg.get("api_key"):
            msg = "未配置 NextFind 地址或密钥，跳过"
            ctx.log.warning("[自动订阅] %s", msg)
            return msg
        if not any(cfg.get(k) for k in _ENABLE_KEYS) and not cfg.get("auto_fill_missing"):
            msg = "未启用任何榜单源或自动补缺集，跳过"
            ctx.log.warning("[自动订阅] %s", msg)
            return msg

        from . import _pipeline

        # 猫眼启用时先在事件循环里用平台浏览器取 Cookie，注入 cfg 供流水线（跑在线程里）用。
        if cfg.get("maoyan_enabled"):
            cfg["maoyan_cookies"] = await _fetch_maoyan_cookies(ctx)
        if cfg.get("ai_assist_recognition"):
            cfg["_platform_ai"] = _PlatformAIProxy(ctx, asyncio.get_running_loop())

        handled = ctx.kv.get("handled", {})
        nf_cache = ctx.kv.get("netflix_cache", {})
        ctx.log.info("[自动订阅] 开始运行(%s)", label)
        try:
            result = await asyncio.to_thread(_pipeline.run, cfg, handled, nf_cache, ctx.log)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动订阅] 运行异常：%s\n%s", e, traceback.format_exc())
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
        if cfg.get("auto_fill_missing") and not result.auth_error:
            try:
                fill_stats = await asyncio.to_thread(_fill_missing_round, cfg, ctx.log)
                ctx.update_config({"last_fill_missing_stats": fill_stats})
                extra = (f"补缺集：检查{fill_stats['checked']}，缺集{fill_stats['missing']}，"
                         f"已触发{fill_stats['triggered']}，失败{fill_stats['failed']}")
                if fill_stats["limited"]:
                    extra += f"，另有{fill_stats['limited']}条受每轮上限限制"
                summary += "\n" + extra
            except Exception as exc:  # noqa: BLE001
                ctx.log.error("[自动订阅] 自动补缺集失败: %r", exc)
                summary += f"\n⚠️ 自动补缺集失败：{exc}"
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
    global _run_lock
    _run_lock = asyncio.Lock()
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
        # 整轮可能跑几分钟（抓榜 + 逐条搜索/订阅），同步等会让 HTTP 请求超时，
        # 前端就只看到无内容的 "Error"（而服务端其实还在跑）。故改为**后台任务**：
        # 立即返回，运行结果通过通知 + 写入「订阅历史」落地，异常记完整堆栈到日志。
        async def _bg():
            try:
                await _run(ctx, "手动")
            except Exception as e:  # noqa: BLE001
                ctx.log.error("[自动订阅] 手动运行后台异常：%s\n%s", e, traceback.format_exc())
        asyncio.create_task(_bg())
        return {"ok": True, "started": True,
                "message": "已在后台开始运行。完成后结果会推送通知并写入「订阅历史」，"
                           "稍后刷新「订阅历史 / 订阅管理」查看；失败原因见平台「运行日志」（来源：自动订阅）。"}

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
    # 必须把「协程函数」交给 ctx.schedule（AsyncIOScheduler 在事件循环里 await 它）；用
    # lambda: asyncio.create_task(...) 会在线程池里跑、无运行中的事件循环，create_task 抛
    # "no running event loop"，任务看似注册却永不触发。
    async def _scheduled_run():
        await _run(ctx, "定时")

    expr = str(_effective_cfg(ctx).get("schedule") or "").strip()
    if expr:
        try:
            from apscheduler.triggers.cron import CronTrigger
            trigger = CronTrigger.from_crontab(expr)
            ctx.schedule(_scheduled_run, trigger, id="定时订阅(%s)" % expr)
            ctx.log.info("[自动订阅] 已注册定时任务：%s", expr)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动订阅] 定时表达式无效(%s): %r", expr, e)


async def teardown(ctx):
    pass
