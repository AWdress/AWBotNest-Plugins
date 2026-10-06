# =============================================================================
# AWBotNest 插件：自动订阅助手（auto_subscribe）· Vue 模式
#
# 聚合多个榜单源（豆瓣 / Mikan 新番 / 奈飞 / 猫眼），按全局或每源独立过滤条件筛选后，
# 通过 NextFind OpenAPI 自动订阅（POST /subscriptions/add）。定时运行 + 结果推送，
# 配置/管理界面由自带的 Vue 组件渲染（frontend/src/Config.vue，模块联邦）。
#
# 迁移自 MoviePilot 插件 automaticsubscriptionassistant（Aqr-K）。落地后端改为 NextFind：
# 一次 /search 即得 tmdb/类型/年份/评分/是否已订阅/是否入库，识别+去重+库查重+评分合并为一步。
# popular 源依赖 MoviePilot 自建统计服务器，未迁；猫眼网播榜通过平台浏览器读取网页签名请求。
# =============================================================================

import asyncio
import concurrent.futures
import math
import threading
import time
import traceback
from datetime import datetime
from types import SimpleNamespace
from typing import Optional

from ._models import STATUS_LABELS
from ._http_errors import one_line, request_error

__plugin__ = {
    "name": "NextFind 助手",
    "id": "auto_subscribe",
    "version": "2.3.4",
    "author": "AWdress",
    "description": "NextFind 资源、订阅与本地媒体库助手，支持榜单订阅、缺集补订、资源查询和管理。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/auto_subscribe/logo.png",
    "changelog": "v1.4.4 更新 NextFind 助手图标\n- 使用新的 NextFind 品牌图标并改为 V2 插件独立资源\n\nv1.4.3 修复缺集订阅占用额度\n- 缺集列表与现有订阅交叉核对，已订阅项目在新增上限前跳过\n- 兼容 tmdbId/mediaType 字段及接口竞态返回\n\nv1.3.3 适配平台后台任务治理\n- 手动运行改由 ctx.create_task 托管，停用或重载插件时可由平台安全回收\n- 声明长任务超时、并发与后台任务配额，避免重复任务失控\n\nv1.3.2 标明独立运行\n- 插件不依赖用户账号或机器人，安装后会显示“独立运行”\n- 定时订阅、平台 AI 和通知功能保持不变\n\nv1.3.1 增强蜜柑番剧识别\n- 自动拆分蜜柑中英、中日混合标题及常见分隔符标题，逐个交给 NextFind 核验\n- 原标题仍搜不到时，根据蜜柑详情页的 Bangumi ID 获取中文名、原名和别名继续搜索\n- 无需额外服务、Endpoint 或 Token；全部候选仍须取得有效 TMDB 结果才会订阅\n\nv1.2.0 新增平台 AI 辅助识别\n- 可选在常规搜索无结果时调用平台 AI 提取标准电影/剧集名、类型与季号\n- AI 结果必须经 NextFind 再次搜索并取得有效 TMDB 结果后才会订阅\n- 默认关闭，平台 AI 不可用或识别失败时安全降级为原有未识别流程\n\nv1.1.0 新增自动补缺集\n- 接入 NextFind /subscriptions/info 批量查询活跃剧集的入库进度\n- 仅对明确存在缺集的订阅调用 /media/fill_missing，并支持配置每轮处理上限\n- 可在不启用榜单源时独立执行补缺，运行通知会显示检查与触发数量\n\nv1.0.6 修复并发运行\n- 新增整轮运行互斥锁，手动与定时并发时跳过重复轮次，避免去重历史互相覆盖",
    "scope": "standalone",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "default_enabled": False,
    # 配置/管理界面由插件自带 Vue 组件渲染（frontend/src/Config.vue）。
    "render_mode": "vue",
    "resources": {
        "timeout_seconds": 1800,
        "max_concurrency": 2,
        "max_background_tasks": 4,
        "failure_threshold": 5,
        "recovery_seconds": 60,
    },
}

__plugin__["changelog"] = (
    "v2.3.4 修正缺集核对与整轮结果\n"
    "- 已订阅、库中完整和规则过滤均算正常处理，无新增时不因个别异常误报整轮失败\n"
    "- TMDB 普通剧集详情确认不存在时正常跳过，季数据异常及真实请求失败仍保留\n"
    "- 核对异常与缺集示例分开记录，通知和历史保留具体原因\n\n"
    "v2.3.3 支持 Forward 同步移除订阅\n"
    "- 接入按 TMDB 编号和订阅 ID 查询、取消订阅，只取消追更，不删除媒体文件\n"
    "- 取消后核对 NextFind 活跃列表；拒绝媒体类型歧义，单季操作需明确允许整部处理\n"
    "- 补齐 Forward 按用户查询接口，启动及订阅变化时通过平台 SDK 同步具体路由\n\n"
    "v2.3.2 适配 Forward 连接测试探针\n"
    "- 按 Forward 1.3.19 实际请求识别无效编号探针，返回 MoviePilot 结果结构\n"
    "- 测试连接只读取 NextFind 验证连通性，不新增订阅；鉴权或上游失败仍明确拒绝\n\n"
    "v2.3.1 修复 MoviePilot 登录与订阅响应兼容\n"
    "- 支持 URL 编码表单、multipart 表单和 JSON 登录\n"
    "- 订阅列表补齐官方响应字段，未知信息保持为空\n"
    "- 拒绝重复凭据、文件和不完整表单，保留原有鉴权与请求大小限制\n\n"
    "v2.3.0 新增 MoviePilot 订阅接口并修正通知状态\n"
    "- 提供独立密码登录、订阅新增与查询，将 MoviePilot v2 风格请求转交 NextFind\n"
    "- 指定季请求默认拒绝，可明确允许转为整部订阅；不支持删除和高级限制\n"
    "- 已有成功订阅但部分检查失败时显示部分成功，不再标为整轮失败\n\n"
    "v2.2.7 提升大库扫描速度并修复猫眼网播榜单\n"
    "- Emby 使用 5000 条大页并关闭图片和用户状态字段，完整读取校验不变\n"
    "- 服务器 TMDB 核对并发提升至 12，Windows 保持稳定并发；统一限速并遵守服务端等待\n"
    "- 猫眼网播通过平台浏览器的同一网页会话读取新接口，保留媒体与平台筛选并明确报告失败\n\n"
    "v2.2.6 优化大库缺集扫描\n"
    "- 缺集优先执行，批量获取季详情并缓存已验证的 TMDB 元数据\n"
    "- 超时保留核对进度，下轮优先处理未完成剧集，库存始终重新读取\n"
    "- 猫眼取 Cookie 改为异步限时回调，已知旧年份提前过滤\n\n"
    "v2.2.5 修复长任务卡住\n"
    "- 整轮运行与网络请求使用实际截止时间，取消时中断请求并停止后续订阅\n"
    "- 缺集扫描及时显示低频进度，超时明确记录未处理项目\n"
    "- 保留运行互斥与已完成结果，不通过强制清锁启动重复任务\n\n"
    "v2.2.4 修复蜜柑解析与订阅流程\n"
    "- 蜜柑使用内置解析器，不再依赖 lxml；全部榜单与 Bangumi 继承平台代理\n"
    "- 严格校验搜索、额度、媒体类型和布尔标记，鉴权失败中止本轮\n"
    "- 请求失败不当作空榜单；运行中保护历史记录，停用时可取消 AI 请求\n"
    "- 配置读取失败禁止覆盖保存，缺集扫描未完成时明确提示\n\n"
    "v2.2.3 修复请求错误通知与无效 RSS 识别\n"
    "- HTTP 404 等失败保留状态与接口，移除英文帮助链接及地址中的凭据\n"
    "- 豆瓣地址返回 HTML 或无效 RSS 时明确报错，不再当作正常空榜单\n\n"
    "v2.2.2 修复 Emby 缺集扫描分页重复\n"
    "- 使用创建时间优先排序、每页 1000 条，缩短全库读取窗口\n"
    "- 保留重复编号、总数变化和漏页校验；不把未完成扫描显示为缺 0 集\n\n"
    "v2.2.1 修复奈飞榜单平台代理\n"
    "- 富元数据页面与全部 TSV 榜单使用 ctx.http，继承平台代理，不回退直连\n"
    "- 保留 HTTP 状态码、代理错误与超时原因，失败不再静默跳过或缓存空榜单\n"
    "- 更新后重新抓取旧缓存；停用时取消进行中的榜单请求\n\n"
    + __plugin__["changelog"]
)

# 配置默认值（vue 模式无 config_schema，默认值集中在此，供定时任务/后端读取；
# 前端 Config.vue 也用同一套默认初始化表单）。
DEFAULTS = {
    "api_url": "", "api_key": "",
    "mp_api_enabled": False, "mp_api_key": "", "mp_whole_series": False,
    "schedule": "0 8 * * *", "notify": True, "ai_assist_recognition": False,
    "auto_fill_missing": False, "auto_fill_missing_limit": 20,
    # 缺集自动订阅不设每轮上限；保留旧字段仅为兼容历史配置。
    "auto_subscribe_missing": False, "auto_subscribe_missing_limit": 0,
    "emby_server": "", "emby_api_key": "", "tmdb_key": "",
    "missing_air_delay_days": 1,
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


def _notification_outcome(result, missing_subs=None, fill_stats=None, extra_added=None):
    """Classify this round's confirmed work without rewriting history counts."""
    def count(value):
        try:
            return max(0, int(value or 0)) if not isinstance(value, bool) else 0
        except (TypeError, ValueError, OverflowError):
            return 0

    stats = getattr(result, "stats", {}) or {}
    modules = [st for st in (missing_subs, fill_stats) if st]
    rank_added = max(sum(count(st.get("subscribed")) for st in stats.values()),
                     len(getattr(result, "added", []) or []))
    missing_added = max(count((missing_subs or {}).get("added")), len(extra_added or []))
    subscribed = rank_added + missing_added
    triggered = count((fill_stats or {}).get("triggered"))
    failed = sum(count(st.get("error")) for st in stats.values())
    failed += sum(bool(error) for error in (getattr(result, "errors", {}) or {}).values())
    for st in modules:
        known_failed = count(st.get("failed"))
        failed += known_failed or int(bool(st.get("error") or st.get("auth_error") or st.get("scan_error")))
    # Module auth errors already contribute to their failure count. Ranking
    # auth stops before the item status is recorded and needs its own count.
    if getattr(result, "auth_error", "") and not any(st.get("auth_error") for st in modules):
        failed += 1
    succeeded = subscribed + triggered
    # No new subscription can be the correct outcome: existing subscriptions,
    # complete shows and intentionally filtered works are completed checks.
    # Do not mistake a whole inventory/request attempt for completed work.
    completed = sum(count(st.get(key)) for st in stats.values() for key in (
        "exists", "in_library", "already_handled", "filtered", "unrecognized"))
    if not (missing_subs or {}).get("scan_error"):
        completed += sum(count((missing_subs or {}).get(key)) for key in ("complete", "skipped", "tmdb_unavailable"))
        if not ((missing_subs or {}).get("error") or (missing_subs or {}).get("auth_error")):
            completed += count((missing_subs or {}).get("unknown"))
    fill = fill_stats or {}
    if "unprocessed" in fill or not (fill.get("error") or fill.get("auth_error")):
        completed += max(0, count(fill.get("checked")) - count(fill.get("failed")) - count(fill.get("unprocessed")))
    level = ("warning" if succeeded or completed else "error") if failed else ("success" if succeeded else "info")
    return {"level": level, "subscribed": subscribed, "triggered": triggered,
            "succeeded": succeeded, "failed": failed}


def _summary(result, label: str, missing_subs: Optional[dict] = None, fill_stats: Optional[dict] = None, extra_added: Optional[list] = None) -> str:
    """把一轮结果格式化成通知/返回文本。"""
    # 鉴权失败：一目了然地报因，别淹没在一堆「失败N」里。
    lines = [f"📥 自动订阅 · {label}"]
    outcome = _notification_outcome(result, missing_subs, fill_stats, extra_added)
    if outcome["failed"]:
        if outcome["level"] == "error":
            state = "❌ 本轮失败"
        elif outcome["succeeded"]:
            state = "⚠️ 本轮部分成功"
        elif (getattr(result, "auth_error", "") or any(
                st and any(st.get(key) for key in ("error", "auth_error", "scan_error", "unprocessed", "scan_unprocessed", "scan_timed_out"))
                for st in (missing_subs, fill_stats))):
            state = "⚠️ 本轮部分完成"
        else:
            state = "⚠️ 本轮完成，部分项目异常"
    else:
        state = "✅ 本轮成功" if outcome["succeeded"] else "本轮完成，无新增"
    lines.append(f"{state}：新增订阅{outcome['subscribed']}部，补缺触发{outcome['triggered']}部，失败{outcome['failed']}项")
    if getattr(result, "auth_error", ""):
        lines.extend([f"❌ {result.auth_error}", "请更新 NextFind API 密钥后重试。"])
    for src, st in getattr(result, "stats", {}).items():
        parts = [f"{STATUS_LABELS.get(k, k)}{v}" for k, v in st.items() if v]
        lines.append(f"[{SOURCE_NAMES.get(src, src)}] " + ("，".join(parts) if parts else "无产出"))
    for src, err in getattr(result, "errors", {}).items():
        lines.append(f"⚠️ {SOURCE_NAMES.get(src, src)} 抓取失败：{one_line(err)}")

    if missing_subs is not None:
        m_parts = []
        if "scanned" in missing_subs:
            m_parts.append(f"Emby剧集{missing_subs['scanned']}")
            if missing_subs.get("scan_error"):
                m_parts.append("扫描未完成，未执行缺集订阅")
            else:
                m_parts.append(f"缺集剧集{missing_subs.get('checked', 0)}")
                m_parts.append(f"缺{missing_subs.get('missing_episodes', 0)}集")
        if missing_subs.get("unknown"):
            m_parts.append(f"资料不全跳过{missing_subs['unknown']}")
        if missing_subs.get("tmdb_unavailable"):
            m_parts.append(f"TMDB无条目跳过{missing_subs['tmdb_unavailable']}")
        if missing_subs.get("error"):
            m_parts.append(f"查询/执行失败：{missing_subs['error']}")
        if missing_subs.get("checked"):
            m_parts.append(f"检查{missing_subs['checked']}")
        if missing_subs.get("added"):
            m_parts.append(f"已订阅{missing_subs['added']}")
        if missing_subs.get("skipped"):
            m_parts.append(f"已跳过{missing_subs['skipped']}")
        if missing_subs.get("failed"):
            m_parts.append(f"失败{missing_subs['failed']}")
        if missing_subs.get("unprocessed"):
            m_parts.append(f"未处理{missing_subs['unprocessed']}")
        if missing_subs.get("scan_timed_out"):
            m_parts.append(f"扫描超时，未核对{missing_subs.get('scan_unprocessed', 0)}部")
        lines.append("[缺集订阅] " + ("，".join(m_parts) if m_parts else "无缺集项目"))
        for error in (missing_subs.get("scan_errors") or [])[:3]:
            lines.append(f"[缺集核对] TMDB {error['tmdb_id']}：{one_line(error['reason'])}")

    if fill_stats is not None:
        f_parts = [
            f"检查{fill_stats.get('checked', 0)}",
            f"缺集{fill_stats.get('missing', 0)}",
            f"已触发{fill_stats.get('triggered', 0)}",
        ]
        if fill_stats.get("failed"):
            f_parts.append(f"失败{fill_stats['failed']}")
        if fill_stats.get("limited"):
            f_parts.append(f"限额{fill_stats['limited']}")
        if fill_stats.get("error"):
            f_parts.append(f"查询/执行失败：{fill_stats['error']}")
        if fill_stats.get("unprocessed"):
            f_parts.append(f"未处理{fill_stats['unprocessed']}")
        lines.append("[自动补缺] " + "，".join(f_parts))

    all_added = list(getattr(result, "added", []) or [])
    if extra_added:
        all_added.extend(extra_added)

    if all_added:
        shown = "、".join(all_added[:15])
        more = f" 等 {len(all_added)} 部" if len(all_added) > 15 else ""
        lines.append(f"✅ 新增订阅：{shown}{more}")
    elif outcome["subscribed"]:
        lines.append(f"✅ 本轮新增订阅{outcome['subscribed']}部")
    else:
        lines.append("本轮无新增订阅")
    return "\n".join(lines)


# 整轮运行并发互斥：手动（后台 task）与定时可整轮并发，否则 kv "handled" 去重历史后写覆盖先写。
# 在 setup 内创建，避免模块级锁跨事件循环复用。
_run_lock = None
_state: dict = {}
_background_tasks: set[asyncio.Task] = set()
_cancel_events: set[threading.Event] = set()
_sync_workers: set[asyncio.Task] = set()
_RUN_TIMEOUT_SECONDS = 1800.0
_CANCEL_GRACE_SECONDS = 5.0
_FINALIZE_TIMEOUT_SECONDS = 10.0


def _worker_done(worker):
    _sync_workers.discard(worker)
    if not worker.cancelled():
        worker.exception()


def _is_running(ignore_task=None):
    return ((_run_lock is not None and _run_lock.locked())
            or any(task is not ignore_task and not task.done() for task in _background_tasks)
            or any(not task.done() for task in _sync_workers))


async def _run_sync(func, *args, cancel_event, on_result=None):
    """取消在途请求并短暂等待退出；异常慢的线程仍阻止新轮次。"""
    worker = asyncio.create_task(asyncio.to_thread(func, *args))
    _sync_workers.add(worker)
    worker.add_done_callback(_worker_done)
    try:
        value = await asyncio.shield(worker)
        if on_result is not None:
            on_result(value)
        return value
    except asyncio.CancelledError:
        cancel_event.set()
        deadline = time.monotonic() + _CANCEL_GRACE_SECONDS
        while not worker.done() and time.monotonic() < deadline:
            try:
                await asyncio.wait({worker}, timeout=max(0, deadline - time.monotonic()))
            except asyncio.CancelledError:
                continue
        # Do not cancel the to_thread task: cancellation cannot kill its thread,
        # and losing that handle would allow a new round to race old writes.
        if worker.done() and not worker.cancelled():
            if worker.exception() is None and on_result is not None:
                on_result(worker.result())
        raise


def _state_get(key, default=None):
    return _state.get(key, default)


async def _state_set(ctx, key, value) -> None:
    # KV writes are already asynchronous. Spawning one background task per key
    # can exhaust the plugin's quota after subscriptions have succeeded.
    storage = getattr(ctx, "storage", None)
    if storage is not None:
        await storage.set(key, value)
    _state[key] = value


class _PlatformHttpProxy:
    """同步榜单在线程中调用 ctx.http，继承平台代理并支持取消。"""

    def __init__(self, ctx, loop, cancel_event, deadline=None):
        self._http = ctx.http
        self._loop = loop
        self._cancel_event = cancel_event
        self._deadline = deadline

    def get(self, url: str, **kwargs):
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self._loop:
            raise RuntimeError("同步榜单请求不能在平台事件循环中执行")
        if not self._loop.is_running() or self._loop.is_closed():
            raise RuntimeError("平台 HTTP 服务已停止")
        if self._cancel_event.is_set():
            raise RuntimeError("榜单请求已取消")

        # HTTPX 的 timeout 限制每个网络阶段；同时限制整次等待，避免停用时遗留线程。
        deadline = time.monotonic() + float(kwargs.get("timeout", 30)) + 5
        if self._deadline is not None:
            deadline = min(deadline, self._deadline)
        if deadline <= time.monotonic():
            raise TimeoutError("本轮运行已超时")
        request = self._http.get(url, **kwargs)
        try:
            future = asyncio.run_coroutine_threadsafe(request, self._loop)
        except Exception:
            request.close()
            raise
        try:
            while True:
                if self._cancel_event.is_set():
                    raise RuntimeError("榜单请求已取消")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("平台 HTTP 请求超时")
                try:
                    return future.result(timeout=min(0.2, remaining))
                except concurrent.futures.TimeoutError:
                    # 服务本身也可能抛 TimeoutError，不能把已完成的异常误当轮询超时。
                    if future.done():
                        return future.result()
                except concurrent.futures.CancelledError as exc:
                    raise RuntimeError("榜单请求已取消") from exc
        finally:
            if not future.done():
                future.cancel()


class _PlatformAIProxy:
    """让同步榜单流水线安全调用平台异步 AI。"""

    def __init__(self, ctx, loop, cancel_event=None, deadline=None):
        self._ai = ctx.ai
        self._loop = loop
        self._cancel_event = cancel_event if cancel_event is not None else threading.Event()
        self._deadline = deadline

    def is_available(self, capability: str = "text") -> bool:
        checker = getattr(self._ai, "is_available", None)
        if callable(checker):
            return bool(checker(capability))
        return bool(getattr(self._ai, "available", False))

    def chat(self, prompt: str, **kwargs) -> str:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is self._loop:
            raise RuntimeError("同步 AI 请求不能在平台事件循环中执行")
        if not self._loop.is_running() or self._loop.is_closed():
            raise RuntimeError("平台 AI 服务已停止")
        if self._cancel_event.is_set():
            raise RuntimeError("AI 请求已取消")
        # 平台文本 AI 最大网络超时为 300 秒；额外覆盖排队及桥接等待。
        deadline = time.monotonic() + 330
        if self._deadline is not None:
            deadline = min(deadline, self._deadline)
        if deadline <= time.monotonic():
            raise TimeoutError("本轮运行已超时")
        request = self._ai.chat(prompt=prompt, **kwargs)
        try:
            future = asyncio.run_coroutine_threadsafe(request, self._loop)
        except Exception:
            request.close()
            raise
        try:
            while True:
                if self._cancel_event.is_set():
                    raise RuntimeError("AI 请求已取消")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("平台 AI 请求超时")
                try:
                    return str(future.result(timeout=min(0.2, remaining)))
                except concurrent.futures.TimeoutError:
                    if future.done():
                        return str(future.result())
                except concurrent.futures.CancelledError as exc:
                    raise RuntimeError("平台 AI 请求已取消") from exc
        finally:
            if not future.done():
                future.cancel()


def _tmdb_id(item: dict) -> str:
    return str(item.get("tmdb_id") or item.get("tmdbId") or item.get("media_id") or item.get("id") or "").strip()


def _media_type(item: dict) -> str:
    value = str(item.get("media_type") or item.get("mediaType") or item.get("raw_type") or item.get("type") or "").strip().lower()
    return {"电影": "movie", "剧集": "tv", "电视剧": "tv", "series": "tv"}.get(value, value)


def _flag_true(value) -> bool:
    return value is True or (not isinstance(value, bool) and str(value).strip().lower() in ("1", "true"))


def _subscribed(item: dict) -> bool:
    return any(_flag_true(item.get(key)) for key in ("is_subscribed", "subscribed", "has_subscribed"))


def _media_key(item: dict) -> tuple[str, str]:
    # NextFind's active list is treated as whole-media subscriptions. Do not
    # change season granularity without a confirmed server-side contract.
    return _media_type(item), _tmdb_id(item)


def _request_error(exc: Exception) -> str:
    from ._nextfind import NextFindError
    if isinstance(exc, NextFindError):
        return one_line(exc)
    return request_error(exc, "NextFind 请求")


def _round_error(stats: dict, exc: Exception, operation: str, log=None) -> None:
    from ._nextfind import NextFindAuthError
    stats["failed"] += 1
    stats["error"] = _request_error(exc)
    if isinstance(exc, NextFindAuthError):
        stats["auth_error"] = stats["error"]
    if log:
        log.error("[自动订阅] %s失败：%s", operation, stats["error"])


def _response_items(payload, operation: str) -> list:
    """An invalid response is a failed query, not an empty library."""
    from ._nextfind import NextFindError
    data = payload
    for _ in range(3):
        if isinstance(data, list):
            if not all(isinstance(item, dict) for item in data):
                break
            return data
        if not isinstance(data, dict):
            break
        status = str(data.get("status") or "").strip().lower()
        if ("status" in data and status not in ("success", "ok")) or ("success" in data and not _flag_true(data["success"])):
            break
        for key in ("data", "results", "items", "list", "records", "medias", "subscriptions"):
            if key in data:
                data = data[key]
                break
        else:
            break
    raise NextFindError(f"{operation}响应格式无效，无法确认查询结果")


def _has_missing_episodes(item: dict) -> bool:
    """只识别响应明确给出的缺集状态，避免字段未知时误触发全库补缺。"""
    for key in ("has_missing", "has_missing_episodes", "is_missing"):
        if _flag_true(item.get(key)):
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
        local_value = item.get("local_episodes")
        if local_value is None:
            local_value = item.get("downloaded_episodes")
        local = int(local_value)
        if total > 0 and 0 <= local < total:
            return True
    except (TypeError, ValueError):
        pass
    return str(item.get("status") or item.get("library_status") or "").lower() == "missing"


def _fill_missing_round(cfg: dict, log=None, cancel_event=None) -> dict:
    """检查活跃剧集订阅，并只触发明确缺集的项目。"""
    client = _nf_client(cfg)
    stats = {"checked": 0, "missing": 0, "triggered": 0, "failed": 0, "limited": 0, "unprocessed": 0, "error": "", "auth_error": ""}
    if cancel_event is not None and cancel_event.is_set():
        return stats
    if log:
        log.info("[自动订阅] 自动补缺：开始检查 NextFind 活跃剧集订阅...")
    try:
        subscriptions = _response_items(client.list_subscriptions(), "订阅列表")
    except Exception as exc:
        _round_error(stats, exc, "自动补缺：获取活跃订阅", log)
        return stats

    by_id = {_tmdb_id(item): item for item in subscriptions if _media_type(item) == "tv" and _tmdb_id(item)}
    tv_items = list(by_id.values())
    stats["checked"] = len(tv_items)
    query = [{"tmdb_id": _tmdb_id(item), "media_type": "tv"} for item in tv_items]
    if cancel_event is not None and cancel_event.is_set():
        return stats
    try:
        details = _response_items(client.subscription_info(query), "订阅进度") if query else []
    except Exception as exc:
        stats["unprocessed"] = len(tv_items)
        _round_error(stats, exc, "自动补缺：获取订阅进度", log)
        return stats

    for detail in details:
        key = _tmdb_id(detail)
        if key in by_id and _media_type(detail) in ("", "tv"):
            by_id[key] = {**by_id[key], **detail}
    candidates = [item for item in by_id.values() if _has_missing_episodes(item)]
    limit = max(1, min(int(cfg.get("auto_fill_missing_limit", 20) or 20), 100))
    stats["missing"] = len(candidates)
    stats["limited"] = max(0, len(candidates) - limit)
    if log:
        log.info("[自动订阅] 自动补缺：活跃剧集共 %d 部，发现明确缺集 %d 部（本轮上限 %d）",
                 len(tv_items), len(candidates), limit)
    selected = candidates[:limit]
    for index, item in enumerate(selected):
        if cancel_event is not None and cancel_event.is_set():
            stats["unprocessed"] = len(selected) - index
            break
        tmdb_id = _tmdb_id(item)
        title = str(item.get("title") or "")
        try:
            ok, message = client.fill_missing(tmdb_id, "tv", title)
            stats["triggered"] += int(ok)
            stats["failed"] += int(not ok)
            if log:
                log.info("[自动订阅] 自动补缺 · %s(%s) → %s%s", title or "未命名", tmdb_id,
                         "已触发" if ok else "失败", f"（{message}）" if message else "")
        except Exception as exc:  # noqa: BLE001
            _round_error(stats, exc, f"自动补缺 · {title or '未命名'}({tmdb_id})", log)
            if stats["auth_error"]:
                stats["unprocessed"] = len(selected) - index - 1
                break
    if log:
        log_round = log.warning if stats["failed"] else log.info
        log_round("[自动订阅] 自动补缺%s：检查 %d，缺集 %d，已触发 %d，失败 %d%s",
                  "结束，存在失败" if stats["failed"] else "完成",
                  len(tv_items), len(candidates), stats["triggered"], stats["failed"],
                 f"，另有 {len(candidates) - limit} 条受每轮上限限制" if len(candidates) > limit else "")
    return stats


def _subscribe_missing_round(cfg: dict, items: list, log=None, cancel_event=None) -> tuple[dict, list]:
    """只消费 Emby/TMDB 已确认的缺集候选，不调用 NextFind 本地库接口。"""
    client = _nf_client(cfg)
    stats = {"checked": 0, "added": 0, "skipped": 0, "failed": 0, "unprocessed": 0, "error": "", "auth_error": "", "added_items": []}
    stats["checked"] = len(items)
    added_titles: list[str] = []
    if cancel_event is not None and cancel_event.is_set():
        stats["unprocessed"] = len(items)
        return stats, added_titles

    if not items:
        if log:
            log.info("[自动订阅] 本轮没有已确认的缺集候选")
        return stats, added_titles

    # A subscription list is necessary for reliable deduplication. Do not
    # blindly add files when it is unavailable or use it to replace the library.
    try:
        subscriptions = _response_items(client.list_subscriptions(), "订阅列表")
        active_ids = {_media_key(item) for item in subscriptions if _tmdb_id(item) and _media_type(item) in ("movie", "tv")}
        if any(not _tmdb_id(item) or _media_type(item) not in ("movie", "tv") for item in subscriptions):
            from ._nextfind import NextFindError
            raise NextFindError("订阅列表缺少媒体类型或 TMDB ID，无法安全去重")
    except Exception as exc:
        stats["unprocessed"] = len(items)
        _round_error(stats, exc, "缺集订阅：读取现有订阅", log)
        return stats, added_titles

    pending = []
    for item in items:
        if not isinstance(item, dict):
            stats["failed"] += 1
            continue
        tmdb_id = _tmdb_id(item)
        title = item.get("title") or item.get("name") or item.get("cn_name") or str(tmdb_id)
        media_type = _media_type(item) or "tv"
        if not tmdb_id or media_type not in ("tv", "movie"):
            stats["failed"] += 1
            continue
        if _subscribed(item) or (media_type, tmdb_id) in active_ids:
            stats["skipped"] += 1
            continue
        pending.append((item, tmdb_id, title, media_type))

    if log:
        log.info(
            "[自动订阅] 缺集订阅：检索到 %d 条，已订阅跳过 %d 条，待处理 %d 条，本轮不设新增上限",
            len(items), stats["skipped"], len(pending),
        )

    # 缺集补订不再按每轮上限截断；开启该功能即一次处理当前返回的全部未订阅项目。
    attempted = set()
    for index, (item, tmdb_id, title, media_type) in enumerate(pending):
        if cancel_event is not None and cancel_event.is_set():
            stats["unprocessed"] = len(pending) - index
            break
        key = (media_type, tmdb_id)
        if key in active_ids or key in attempted:
            stats["skipped"] += 1
            continue
        attempted.add(key)
        try:
            ok, message = client.add(tmdb_id, media_type, item.get("season"))
            if ok:
                stats["added"] += 1
                added_titles.append(f"{title}(缺集)")
                stats["added_items"].append({"tmdb_id": tmdb_id, "media_type": media_type, "title": title})
                active_ids.add(key)
            elif any(marker in str(message or "").lower() for marker in ("已订阅", "已存在", "already subscribed", "already exists", "subscription exists")):
                # A concurrent/manual subscription may win after the pre-check.
                stats["skipped"] += 1
                active_ids.add(key)
            else:
                stats["failed"] += 1
            if log:
                log.info("[自动订阅] 缺集补订 · %s(%s %s) → %s", title, media_type, tmdb_id, message or ("成功" if ok else "失败"))
        except Exception as exc:
            _round_error(stats, exc, f"缺集补订 · {title}({tmdb_id})", log)
            if stats["auth_error"]:
                stats["unprocessed"] = len(pending) - index - 1
                break

    if log:
        log_round = log.warning if stats["failed"] else log.info
        log_round("[自动订阅] 缺集订阅%s：检索 %d，新增 %d，跳过 %d，失败 %d",
                 "结束，存在失败" if stats["failed"] else "完成",
                 stats["checked"], stats["added"], stats["skipped"], stats["failed"])
    return stats, added_titles


def _merge_missing_history(handled, stats):
    """Merge only confirmed missing subscriptions; keep evidence for cancellation."""
    from ._models import make_history_key
    handled = dict(handled or {})
    for item in (stats or {}).get("added_items", []):
        handled[make_history_key(item["tmdb_id"], item["media_type"], None)] = {
            "title": item["title"], "status": "subscribed", "tmdb_id": item["tmdb_id"],
            "source": "Emby 缺集", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    return handled


async def _save_interrupted(ctx, progress, message):
    """Persist confirmed results only; an interrupted round is never completed."""
    result = progress.get("result")
    if result is not None:
        handled = {**dict(_state_get("handled", {}) or {}), **dict(result.handled)}
        missing = progress.get("missing_subs") or {}
        handled = _merge_missing_history(handled, missing)
        await _state_set(ctx, "handled", handled)
        await _state_set(ctx, "netflix_cache", result.nf_cache)
    for key, name in (("missing_subs", "last_missing_subscription_stats"),
                      ("fill_stats", "last_fill_missing_stats")):
        stats = progress.get(key)
        if stats is not None:
            await _state_set(ctx, name, {k: v for k, v in stats.items() if k != "added_items"})
    agg = {}
    if result is not None:
        for stats in result.stats.values():
            for key, count in stats.items():
                agg[key] = agg.get(key, 0) + count
    agg.update({"interrupted": 1, "error": max(1, agg.get("error", 0)),
                "message": message, "phase": progress["phase"]})
    if progress.get("missing_subs"):
        agg["missing_added"] = progress["missing_subs"].get("added", 0)
        agg["missing_unprocessed"] = (progress["missing_subs"].get("unprocessed", 0)
                                      + progress["missing_subs"].get("scan_unprocessed", 0))
        agg["missing_scan_timed_out"] = int(bool(progress["missing_subs"].get("scan_timed_out")))
        agg["subscribed"] = agg.get("subscribed", 0) + agg["missing_added"]
    await _state_set(ctx, "last_stats", agg)
    await _state_set(ctx, "last_run", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _check_round_running(cancel_event, deadline):
    if deadline is not None and time.monotonic() >= deadline:
        cancel_event.set()
        raise TimeoutError("本轮运行已超时")
    if cancel_event.is_set():
        raise asyncio.CancelledError


def _merge_scan_stats(stats, scan):
    for key in ("scanned", "matched", "complete", "unknown", "missing_episodes", "tmdb_unavailable"):
        stats[key] = scan.get(key, 0)
    stats["scan_errors"] = list(scan.get("scan_errors") or [])[:10]
    stats["failed"] += scan.get("failed", 0)
    stats["scan_unprocessed"] = scan.get("unprocessed", 0)
    stats["scan_timed_out"] = scan.get("timed_out", False)
    stats["scan_error"] = scan.get("error", "")
    if stats["scan_error"]:
        stats["failed"] = max(1, stats["failed"])
        stats["error"] = stats.get("error") or stats["scan_error"]
    return stats


async def _run_missing_phase(ctx, cfg, cancel_event, deadline, progress):
    """Finish the local-library phase before any optional ranking/browser work."""
    from ._emby_missing import scan_missing, LibraryScanError
    missing_added = []
    progress["phase"] = "Emby/TMDB 缺集核对"
    progress["missing_subs"] = {
        "checked": 0, "added": 0, "skipped": 0, "failed": 1,
        "unprocessed": 0, "error": "扫描未完成，未执行缺集订阅", "scan_error": "扫描未完成",
    }
    try:
        scan = await scan_missing(cfg, ctx.http, ctx.log, storage=getattr(ctx, "storage", None))
        if scan.get("error"):
            stats = {"checked": 0, "added": 0, "skipped": 0, "failed": 1,
                     "unprocessed": 0, "error": scan["error"], "auth_error": ""}
            _merge_scan_stats(stats, scan)
            ctx.log.error("[自动订阅] %s，本轮未新增缺集订阅", scan["error"])
        else:
            _check_round_running(cancel_event, deadline)
            progress["phase"] = "缺集订阅"
            stats, missing_added = await _run_sync(
                _subscribe_missing_round, cfg, scan["items"], ctx.log, cancel_event,
                cancel_event=cancel_event,
                on_result=lambda value: progress.update(missing_subs=_merge_scan_stats(value[0], scan)),
            )
            # The callback also runs when a cancelled worker drains. Keep
            # added_items in progress until finalization has persisted history.
    except asyncio.CancelledError:
        cancel_event.set()
        raise
    except Exception as exc:
        message = str(exc) if isinstance(exc, LibraryScanError) else f"缺集检查失败（{type(exc).__name__}）"
        stats = {"checked": 0, "added": 0, "skipped": 0, "failed": 1,
                 "unprocessed": 0, "error": message, "auth_error": ""}
        from ._nextfind import NextFindAuthError
        if isinstance(exc, NextFindAuthError):
            stats["error"] = stats["auth_error"] = _request_error(exc)
        ctx.log.error("[自动订阅] %s，本轮未新增缺集订阅", message)
    progress["missing_subs"] = stats
    _check_round_running(cancel_event, deadline)
    return stats, missing_added


async def _run(ctx, label: str) -> str:
    if _is_running(ignore_task=asyncio.current_task()):
        ctx.log.warning("[自动订阅] 上一轮仍在运行，跳过本次运行(%s)", label)
        return "上一轮仍在运行，已跳过"
    cancel_event = threading.Event()
    progress = {"phase": "准备", "result": None, "missing_subs": None, "fill_stats": None}
    _cancel_events.add(cancel_event)
    try:
        deadline = time.monotonic() + _RUN_TIMEOUT_SECONDS
        try:
            async with asyncio.timeout(_RUN_TIMEOUT_SECONDS) as timeout_scope:
                return await _run_round(ctx, label, cancel_event, deadline=deadline, progress=progress)
        except TimeoutError:
            if not timeout_scope.expired() and time.monotonic() < deadline:
                raise
            cancel_event.set()
            message = f"本轮运行超过 {int(_RUN_TIMEOUT_SECONDS / 60)} 分钟，已停止（阶段：{progress['phase']}）"
            ctx.log.error("[自动订阅] %s", message)
            if any(not worker.done() for worker in _sync_workers):
                ctx.log.error("[自动订阅] 旧工作线程尚未退出，已阻止新轮次，避免重复订阅")
            try:
                async with asyncio.timeout(_FINALIZE_TIMEOUT_SECONDS):
                    await _save_interrupted(ctx, progress, message)
                    if _effective_cfg(ctx).get("notify", True):
                        outcome = _notification_outcome(progress.get("result"), progress.get("missing_subs"),
                                                        progress.get("fill_stats"))
                        await ctx.notify({"状态": "部分成功，运行超时" if outcome["succeeded"] else "运行超时", "详情": message,
                                          "已完成": f"新增订阅{outcome['subscribed']}部，补缺触发{outcome['triggered']}部",
                                          "失败": f"本轮未完成；已记录项目失败{outcome['failed']}项",
                                          "处理结果": "已完成的订阅保留，未处理项目留待下一轮"},
                                         level="warning" if outcome["succeeded"] else "error", category="自动订阅")
            except Exception as exc:
                ctx.log.warning("[自动订阅] 超时结果保存或通知失败：%s", request_error(exc))
            return message
        except asyncio.CancelledError:
            cancel_event.set()
            # A stopped/reloaded plugin must not send another notification.
            try:
                if any(progress.get(key) is not None for key in ("result", "missing_subs", "fill_stats")):
                    async with asyncio.timeout(_FINALIZE_TIMEOUT_SECONDS):
                        await _save_interrupted(ctx, progress, f"任务已取消（阶段：{progress['phase']}）")
            except (Exception, asyncio.CancelledError):
                pass
            raise
    finally:
        _cancel_events.discard(cancel_event)


async def _run_round(ctx, label: str, cancel_event, *, deadline=None, progress=None) -> str:
    """执行一轮：阻塞流水线跑在 to_thread，通知/kv 在事件循环。返回汇总文本。"""
    if _run_lock.locked() or any(not worker.done() for worker in _sync_workers):
        ctx.log.warning("[自动订阅] 上一轮仍在运行，跳过本次运行(%s)", label)
        return "上一轮仍在运行，已跳过"
    async with _run_lock:
        cfg = _effective_cfg(ctx)
        cfg["_cancel_event"] = cancel_event
        cfg["_run_deadline"] = deadline
        progress = progress if progress is not None else {"phase": "准备"}
        if not cfg.get("api_url") or not cfg.get("api_key"):
            msg = "未配置 NextFind 地址或密钥，跳过"
            ctx.log.warning("[自动订阅] %s", msg)
            return msg
        if not any(cfg.get(k) for k in _ENABLE_KEYS) and not cfg.get("auto_fill_missing") and not cfg.get("auto_subscribe_missing"):
            msg = "未启用榜单、缺集订阅或自动补缺，跳过"
            ctx.log.warning("[自动订阅] %s", msg)
            return msg

        from . import _pipeline
        handled = dict(_state_get("handled", {}) or {})
        nf_cache = dict(_state_get("netflix_cache", {}) or {})
        # A seed checkpoint exists before scanning so cancellation during the
        # first phase can preserve already-confirmed local subscription writes.
        result = SimpleNamespace(stats={}, errors={}, added=[], handled=handled,
                                 nf_cache=nf_cache, auth_error="", interrupted="")
        progress["result"] = result
        ctx.log.info("[自动订阅] 开始运行(%s)", label)
        missing_subs = None
        missing_added = []
        if cfg.get("auto_subscribe_missing"):
            missing_subs, missing_added = await _run_missing_phase(
                ctx, cfg, cancel_event, deadline, progress)
            handled = _merge_missing_history(handled, missing_subs)
            result.handled = handled
            await _state_set(ctx, "handled", handled)
            await _state_set(ctx, "last_missing_subscription_stats",
                             {k: v for k, v in missing_subs.items() if k != "added_items"})
            _check_round_running(cancel_event, deadline)
            if missing_subs.get("auth_error"):
                result.auth_error = missing_subs["auth_error"]

        if not result.auth_error:
            # Local missing subscriptions take priority over ranking browsers,
            # provider fetches and title recognition within the same deadline.
            _check_round_running(cancel_event, deadline)
            if cfg.get("maoyan_enabled"):
                progress["phase"] = "猫眼浏览器"
                from ._maoyan_browser import ranking_keys
                if ranking_keys(cfg):
                    session = await _fetch_maoyan_session(ctx, cfg)
                    cfg["maoyan_cookies"] = session["cookies"]
                    cfg["maoyan_web_data"] = session["web_data"]
                    cfg["maoyan_web_errors"] = session["web_errors"]
                else:
                    cfg["maoyan_cookies"] = await _fetch_maoyan_cookies(ctx)
                _check_round_running(cancel_event, deadline)
            if cfg.get("ai_assist_recognition"):
                cfg["_platform_ai"] = _PlatformAIProxy(ctx, asyncio.get_running_loop(), cancel_event, deadline)
            if any(cfg.get(k) for k in _ENABLE_KEYS):
                cfg["_platform_http"] = _PlatformHttpProxy(ctx, asyncio.get_running_loop(), cancel_event, deadline)

            def remember_pipeline(value):
                # A provider result must not overwrite subscriptions confirmed
                # in the earlier phase, even if its handled snapshot is stale.
                value.handled = _merge_missing_history(
                    {**handled, **dict(value.handled)}, missing_subs)
                progress["result"] = value

            progress["phase"] = "榜单查询与订阅"
            try:
                # Still run the empty pipeline when sources are disabled: this
                # keeps its result contract and existing isolated SDK fixtures.
                result = await _run_sync(_pipeline.run, cfg, handled, nf_cache, ctx.log,
                                         cancel_event=cancel_event, on_result=remember_pipeline)
            except Exception as e:  # noqa: BLE001
                message = request_error(e)
                ctx.log.error("[自动订阅] 运行异常：%s", message)
                if missing_subs is not None:
                    await _save_interrupted(ctx, progress, f"榜单运行异常：{message}")
                if cfg.get("notify", True):
                    outcome = _notification_outcome(result, missing_subs, extra_added=missing_added)
                    await ctx.notify({"状态": "部分成功，运行异常" if outcome["succeeded"] else "运行异常", "详情": message,
                                      "已完成": f"新增订阅{outcome['subscribed']}部，补缺触发{outcome['triggered']}部",
                                      "失败": f"本轮未完成；已记录项目失败{outcome['failed']}项"},
                                     level="warning" if outcome["succeeded"] else "error", category="自动订阅")
                return f"运行异常：{message}"

            await _state_set(ctx, "handled", result.handled)
            await _state_set(ctx, "netflix_cache", result.nf_cache)
            _check_round_running(cancel_event, deadline)
            if getattr(result, "interrupted", ""):
                raise asyncio.CancelledError

        fill_stats = None
        if cfg.get("auto_fill_missing") and not getattr(result, "auth_error", ""):
            try:
                progress["phase"] = "活跃订阅补缺"
                fill_stats = await _run_sync(_fill_missing_round, cfg, ctx.log, cancel_event, cancel_event=cancel_event,
                                            on_result=lambda value: progress.update(fill_stats=value))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                fill_stats = {"checked": 0, "missing": 0, "triggered": 0, "failed": 0, "limited": 0, "error": "", "auth_error": ""}
                _round_error(fill_stats, exc, "自动补缺集", ctx.log)
            _check_round_running(cancel_event, deadline)
            progress["fill_stats"] = fill_stats
            await _state_set(ctx, "last_fill_missing_stats", fill_stats)
            if fill_stats.get("auth_error"):
                result.auth_error = fill_stats["auth_error"]

        # 汇总本轮各状态计数（跨来源相加），供前端「订阅历史」顶部统计卡展示。
        progress["phase"] = "结果保存与通知"
        _check_round_running(cancel_event, deadline)
        agg: dict = {}
        for st in result.stats.values():
            for k, v in st.items():
                agg[k] = agg.get(k, 0) + v
        if missing_subs:
            agg["subscribed"] = agg.get("subscribed", 0) + missing_subs.get("added", 0)
            agg["exists"] = agg.get("exists", 0) + missing_subs.get("skipped", 0)
            agg["missing_checked"] = missing_subs.get("checked", 0)
            agg["missing_added"] = missing_subs.get("added", 0)
            agg["missing_skipped"] = missing_subs.get("skipped", 0)
            agg["missing_failed"] = missing_subs.get("failed", 0)
            agg["missing_scanned"] = missing_subs.get("scanned", 0)
            agg["missing_episodes"] = missing_subs.get("missing_episodes", 0)
            agg["missing_unknown"] = missing_subs.get("unknown", 0)
            agg["missing_tmdb_unavailable"] = missing_subs.get("tmdb_unavailable", 0)
            agg["missing_unprocessed"] = missing_subs.get("unprocessed", 0) + missing_subs.get("scan_unprocessed", 0)
            agg["missing_scan_timed_out"] = int(bool(missing_subs.get("scan_timed_out")))
        if fill_stats:
            agg["fill_checked"] = fill_stats.get("checked", 0)
            agg["fill_triggered"] = fill_stats.get("triggered", 0)
            agg["fill_failed"] = fill_stats.get("failed", 0)
        module_failures = sum(st.get("failed", 0) for st in (missing_subs, fill_stats) if st)
        if module_failures:
            agg["error"] = agg.get("error", 0) + module_failures
        elif result.auth_error:
            agg["error"] = max(1, agg.get("error", 0))
        await _state_set(ctx, "last_run", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        await _state_set(ctx, "last_stats", agg)

        summary = _summary(result, label, missing_subs=missing_subs, fill_stats=fill_stats, extra_added=missing_added)
        outcome = _notification_outcome(result, missing_subs, fill_stats, missing_added)
        has_err = bool(outcome["failed"])

        # 通知是「尽力而为」：投递失败（无在线账号/Bot 无目标等）只告警，绝不让整轮运行失败
        # （订阅其实已经落地）。notifier.submit 无可用账号时会抛 RuntimeError。
        if cfg.get("notify", True):
            level = outcome["level"]
            try:
                lines = [line.strip() for line in str(summary or "").splitlines() if line.strip()]
                rows = [
                    {"项目": "状态" if index == 0 else f"详情 {index}", "内容": line}
                    for index, line in enumerate(lines)
                ]
                await ctx.notify(
                    rows or [{"项目": "详情", "内容": "暂无内容"}],
                    level=level,
                    category="自动订阅",
                )
            except Exception as e:  # noqa: BLE001 - 通知失败不影响运行结果
                ctx.log.warning("[自动订阅] 结果通知投递失败（不影响运行）：%r", e)
        total_added_count = len(result.added) + len(missing_added)
        _check_round_running(cancel_event, deadline)
        log_round = ctx.log.warning if has_err else ctx.log.info
        log_round("[自动订阅] %s(%s)：新增 %d 部（榜单 %d，缺集 %d），触发补缺 %d 部",
                  ("本轮失败" if outcome["level"] == "error" else "本轮存在项目异常") if has_err else "完成", label,
                  total_added_count, len(result.added), len(missing_added),
                  fill_stats.get("triggered", 0) if fill_stats else 0)
        return summary


def _nf_client(cfg):
    """构造 NextFind 客户端（局部 import 避免顶层依赖）。"""
    from ._nextfind import NextFindClient
    return NextFindClient(cfg.get("api_url", ""), cfg.get("api_key", ""),
                          cancel_event=cfg.get("_cancel_event"), deadline=cfg.get("_run_deadline"))


async def _fetch_maoyan_session(ctx, cfg, *, timeout_seconds: float = 75.0) -> dict:
    """Read signed public web rankings in one configured, host-owned session."""
    from ._maoyan_browser import MAOYAN_WEB_URL, collect_web_rankings, ranking_keys

    expected = ranking_keys(cfg)
    empty = {"cookies": {}, "web_data": {}, "web_errors": {}}
    if not expected:
        return empty
    round_deadline = cfg.get("_run_deadline")
    if (isinstance(round_deadline, (int, float)) and not isinstance(round_deadline, bool)
            and math.isfinite(round_deadline)):
        timeout_seconds = min(timeout_seconds, max(0.0, round_deadline - time.monotonic()))
    deadline = time.monotonic() + timeout_seconds

    async def collect(page):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        return await collect_web_rankings(page, cfg, timeout_seconds=min(45.0, remaining))

    def failed(message):
        # Browser errors may embed headers or licensing credentials. Only
        # controlled messages enter the provider, notification or logs.
        ctx.log.warning("[自动订阅] %s", message)
        return {"cookies": {}, "web_data": {}, "web_errors": dict.fromkeys(expected, message)}

    try:
        async with asyncio.timeout(timeout_seconds):
            value = await ctx.browser.run(MAOYAN_WEB_URL, collect, headless=True,
                                          timeout=min(60.0, max(0.01, timeout_seconds)))
        if (not isinstance(value, dict)
                or any(not isinstance(value.get(key), dict) for key in empty)):
            return failed("猫眼网播浏览器返回无效结果")
        ctx.log.info("[自动订阅] 猫眼网播读取：成功 %d/%d 个榜单", len(value["web_data"]), len(expected))
        return {key: value[key] for key in empty}
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        return failed(f"猫眼网播读取超过 {timeout_seconds:g} 秒，未完成的榜单本轮跳过")
    except Exception as exc:
        return failed(f"猫眼网播浏览器读取失败（{type(exc).__name__}）")


async def _fetch_maoyan_cookies(ctx, *, timeout_seconds: float = 35.0) -> dict:
    """用平台 ctx.browser 预取猫眼 Cookie（{name: value}）；失败降级空 dict（无 Cookie）。

    provider 跑在 to_thread 里不能直接 await 浏览器，故在事件循环里先取好再注入 cfg。
    异步 Page 回调避免 SDK 的同步线程分支在取消后无限等待；整次浏览器阶段
    共用截止时间，启动、导航和 Cookie 读取不各自重新获得完整预算。
    SDK 首次同步下载内核等阻塞代码仍无法由 asyncio 取消强停。
    """
    from ._maoyan import MAOYAN_URL

    async def _grab(page):
        try:
            return {c["name"]: c["value"] for c in await page.context.cookies()}
        except Exception:  # noqa: BLE001 - 引擎不支持 context.cookies 时降级
            return {}
    try:
        # Let the SDK retain ownership of Page/context/browser cleanup. Its
        # async branch also navigates before invoking _grab, so do not goto twice.
        async with asyncio.timeout(timeout_seconds):
            return await ctx.browser.run(MAOYAN_URL, _grab, headless=True, timeout=30) or {}
    except asyncio.CancelledError:
        # Stop/unload and the enclosing round deadline must not become a
        # successful no-Cookie fallback that continues the ranking pipeline.
        raise
    except TimeoutError:
        ctx.log.warning("[自动订阅] 猫眼 Cookie 阶段超过 %g 秒，降级无 Cookie", timeout_seconds)
        return {}
    except Exception as e:  # noqa: BLE001 - 浏览器不可用/超时降级无 Cookie
        ctx.log.warning("[自动订阅] 猫眼 Cookie 获取失败，降级无 Cookie：%s", request_error(e))
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
    _state.clear()
    runtime_keys = ("last_run", "last_stats", "last_missing_subscription_stats", "last_fill_missing_stats")
    state_keys = ("handled", "netflix_cache", *runtime_keys)
    storage = getattr(ctx, "storage", None)
    if storage is not None:
        getter = getattr(storage, "get", None)
        if callable(getter):
            absent = object()
            for key in state_keys:
                value = await getter(key, absent)
                if value is not absent:
                    _state[key] = value
        else:
            # Compatibility for minimal test/legacy facades exposing items()
            # only. Never retain TMDB metadata caches or unrelated KV in state.
            values = dict(await storage.items())
            _state.update({key: values[key] for key in state_keys if key in values})

    # 调度器回调受平台治理超时约束，不能直接等待抓榜/逐条订阅这种分钟级流水线。
    # 所有手动和定时运行统一交给平台托管的后台任务，回调本身立即返回。
    def _spawn_run(label: str) -> asyncio.Task:
        async def _bg():
            try:
                await _run(ctx, label)
            except asyncio.CancelledError:
                # 停用/重载时平台会取消后台任务；这是正常生命周期事件，不输出异常堆栈。
                ctx.log.warning("[自动订阅] %s任务已取消", label)
            except Exception as exc:  # noqa: BLE001
                ctx.log.error("[自动订阅] %s运行后台异常：%s\n%s", label, exc, traceback.format_exc())

        task = ctx.create_task(_bg(), name=f"自动订阅{label}运行")
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task
    # 旧版曾把只读运行统计写进可编辑配置；迁入 KV 后从配置中清理，避免“后端使用但页面不显示”。
    legacy=ctx.config or {}
    for key in runtime_keys:
        if key in legacy and key not in _state:
            await _state_set(ctx, key, legacy[key])
    settings=getattr(ctx,"settings",None)
    plugin_config=getattr(settings,"plugin_config",None)
    saved=plugin_config.get("auto_subscribe") if isinstance(plugin_config,dict) else None
    if isinstance(saved,dict) and any(key in saved for key in runtime_keys):
        for key in runtime_keys:saved.pop(key,None)
        ctx.update_config({})
    # ── 前端(Config.vue)用的后端接口 ──
    @ctx.on_api("/meta", methods=["GET"])
    async def _api_meta(req):
        from ._mp_compat import BASE_PATH, LOGIN_USER
        return {"countries": _country_options(), "mp_base_path": BASE_PATH, "mp_username": LOGIN_USER}

    @ctx.on_api("/mp/key", methods=["POST"])
    async def _api_mp_key(req):
        import secrets
        # Only the authenticated admin API can generate a new credential.
        # It is not active until explicitly saved in the plugin configuration.
        return {"key": secrets.token_urlsafe(32)}

    if _effective_cfg(ctx).get("mp_api_enabled") is True:
        from ._mp_compat import MoviePilotCompat
        mp_bridge = MoviePilotCompat(ctx, lambda: _effective_cfg(ctx))
        mp_bridge.register()
        ctx.create_task(mp_bridge.sync_routes(), name="MoviePilot 订阅路由同步")

    @ctx.on_api("/test", methods=["GET"])
    async def _api_test(req):
        cfg = _effective_cfg(ctx)
        if not cfg.get("api_url") or not cfg.get("api_key"):
            return {"ok": False, "message": "请先填写 NextFind 地址与密钥"}
        try:
            data = await asyncio.to_thread(lambda: _nf_client(cfg).quota())
            return {"ok": True, "quota": data}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": _request_error(e)}

    @ctx.on_api("/run", methods=["POST"])
    async def _api_run(req):
        # 整轮可能跑几分钟（抓榜 + 逐条搜索/订阅），同步等会让 HTTP 请求超时，
        # 前端就只看到无内容的 "Error"（而服务端其实还在跑）。故改为**后台任务**：
        # 立即返回，运行结果通过通知 + 写入「订阅历史」落地，异常记完整堆栈到日志。
        if _is_running():
            return {"ok": False, "message": "上一轮仍在运行，请等待完成后再试"}
        _spawn_run("手动")
        return {"ok": True, "started": True,
                "message": "已在后台开始运行。完成后结果会推送通知并写入「订阅历史」，"
                           "稍后刷新「订阅历史 / 订阅管理」查看；失败原因见平台「运行日志」（来源：自动订阅）。"}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        handled = _state_get("handled", {})
        items = [{"key": k, **v} for k, v in handled.items()]
        items.sort(key=lambda x: x.get("time", ""), reverse=True)
        return {
            "items": items,
            "last_run": _state_get("last_run", ""),
            "stats": _state_get("last_stats", {}),
            "missing": _state_get("last_missing_subscription_stats", {}),
        }

    @ctx.on_api("/test-library", methods=["GET"])
    async def _api_test_library(req):
        from ._emby_missing import test_connections, LibraryScanError
        try:
            result = await test_connections(_effective_cfg(ctx), ctx.http)
            return {"ok": True, **result}
        except LibraryScanError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "message": f"连接检查失败（{type(exc).__name__}）"}

    @ctx.on_api("/history/delete", methods=["POST"])
    async def _api_history_delete(req):
        data = req.json or {}
        if not isinstance(data, dict):
            return {"ok": False, "message": "请求数据必须是对象"}
        if _is_running():
            return {"ok": False, "message": "订阅任务正在运行，请完成后再修改历史"}
        async with _run_lock:
            if _flag_true(data.get("clear")):
                await _state_set(ctx, "handled", {})
                return {"ok": True, "cleared": True}
            key = data.get("key")
            if not isinstance(key, str) or not key:
                return {"ok": False, "message": "请提供要删除的历史记录"}
            handled = dict(_state_get("handled", {}))
            if key in handled:
                handled.pop(key)
                await _state_set(ctx, "handled", handled)
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
            return {"items": [], "error": _request_error(e)}

    @ctx.on_api("/subscriptions/remove", methods=["POST"])
    async def _api_subscriptions_remove(req):
        data = req.json or {}
        if not isinstance(data, dict):
            return {"ok": False, "message": "请求数据必须是对象"}
        cfg = _effective_cfg(ctx)
        tmdb_id, media_type = data.get("tmdb_id"), data.get("media_type")
        identity = str(tmdb_id or "").strip()
        try:
            valid_id = (not isinstance(tmdb_id, bool) and identity.isdecimal() and int(identity) > 0)
        except ValueError:
            valid_id = False
        media_type = str(media_type or "").strip().lower()
        if not valid_id or media_type not in ("movie", "tv"):
            return {"ok": False, "message": "请提供有效的 TMDB ID 和媒体类型（movie/tv）"}
        try:
            ok, msg = await asyncio.to_thread(lambda: _nf_client(cfg).remove(identity, media_type))
            return {"ok": ok, "message": msg}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": _request_error(e)}

    # ── 定时任务（cron 无效时仅告警，手动运行仍可用）──
    # 回调只负责投递后台任务并立即返回，避免平台 scheduler 对长流水线触发 TimeoutError。
    async def _scheduled_run():
        if _is_running():
            ctx.log.warning("[自动订阅] 上一轮仍在运行，跳过本次定时触发")
            return
        _spawn_run("定时")
        ctx.log.info("[自动订阅] 定时任务已投递后台执行")

    expr = str(_effective_cfg(ctx).get("schedule") or "").strip()
    if expr:
        try:
            parts = expr.split()
            if len(parts) != 5:
                raise ValueError("Cron 必须包含分、时、日、月、星期五个字段")
            minute, hour, day, month, day_of_week = parts
            ctx.schedule_cron(
                "定时订阅(%s)" % expr,
                _scheduled_run,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
            ctx.log.info("[自动订阅] 已注册定时任务：%s", expr)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[自动订阅] 定时表达式无效(%s): %r", expr, e)


async def teardown(ctx):
    for event in list(_cancel_events):
        event.set()
    for task in list(_background_tasks):
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)
    _background_tasks.clear()
    _cancel_events.clear()
    _state.clear()
