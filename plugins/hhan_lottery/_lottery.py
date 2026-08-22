"""憨憨转盘：使用平台同步 Cookie 调用 HHCLUB 幸运转盘。"""

from __future__ import annotations

import asyncio
import html
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ._auth import cookie_header


__plugin__ = {
    "name": "憨憨转盘",
    "id": "hhan_lottery",
    "version": "1.3.10",
    "author": "AWdress",
    "description": "读取平台同步的 HHCLUB Cookie，通过配置页控制自动抽取幸运转盘并推送、保存结果。",
    "icon": "https://hhanclub.net/favicon.ico",
    "changelog": "v1.3.2 修复 Vue 资源缓存兼容\n- 发布包保留旧哈希资源，避免缓存入口引用文件不存在\n\nv1.3.1 新增实时净盈亏\n- 结构化状态、完成摘要和累计文本统一计算憨豆净盈亏\n\nv1.3.0 新增实时奖品统计\n- 状态接口实时返回当前任务与合并后的累计奖品结构\n\nv1.2.1 修复重启续跑启动\n- 平台恢复阶段 Cookie 或网络暂不可用时保留计划并退避重试\n\nv1.1.0 同步庆典版功能\n- 新增保留余额抽取、大奖止损与自定义关键词停止\n- 每 N 抽校准真实余额，可选自动清理转盘通知\n- 新增手动定向清理，只删除‘幸运大转盘’站内信\n- 增强 VIP 折算憨豆识别与限流退避\n\nv1.0.3 修复配置页布局\n- 三个功能开关调整为同一行三等分，消除第三项单独换行和大面积留白\n- 保持任务操作首行三按钮、次行两按钮的对称栅格结构\n\nv1.0.2 修复后台任务与跳转安全\n- 后台抽奖任务改由平台统一托管，确保插件停用或重载时可靠清理\n- 页面和抽奖接口仅允许跟随 hhanclub.net 站内跳转，避免 Cookie 随跨站跳转泄露\n- 插件重载时修复残留的运行中状态\n\nv1.0.1 改为配置页控制\n- 移除聊天命令，抽奖次数直接在插件配置中填写\n- 配置页提供开始、停止、查看最近结果和累计统计操作\n- 抽奖完成后通过平台通知推送，并保存最近一次结果\n\nv1.0.0 初始版本\n- 使用平台 Cookie 同步读取 HHCLUB 登录态\n- 支持按次数自动抽奖、手动停止和统计查询\n- 自动识别余额与单次消耗，并对重复点击进行退避\n- 保存累计抽奖、消耗、憨豆收益与奖品统计",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": ["hhanclub.net", "*.hhanclub.net"],
    "default_enabled": False,
    "resources": {
        "timeout_seconds": 43200,
        "max_concurrency": 2,
        "max_background_tasks": 8,
        "failure_threshold": 5,
        "recovery_seconds": 60,
    },
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12", "lxml>=5.0"],
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": True, "label": "启用憨憨转盘",
            "section": "功能开关", "cols": 4, "order": 1,
        },
        "notify_cookie_error": {
            "type": "boolean", "default": True, "label": "Cookie 异常时通知",
            "section": "功能开关", "cols": 4, "order": 2,
        },
        "notify_result": {
            "type": "boolean", "default": True, "label": "完成后推送结果",
            "section": "功能开关", "cols": 4, "order": 3,
        },
        "lottery_count": {
            "type": "number", "default": 10, "label": "抽奖次数",
            "min": 1, "section": "抽奖设置", "cols": 6, "order": 20,
        },
        "lottery_mode": {
            "type": "select", "default": "fixed", "label": "抽奖方式",
            "options": [{"label": "指定次数", "value": "fixed"}, {"label": "按余额抽完", "value": "balance"}],
            "section": "抽奖设置", "cols": 6, "order": 21,
        },
        "interval_seconds": {
            "type": "slider", "default": 7, "label": "抽奖间隔（秒）",
            "min": 3, "max": 60, "step": 1, "section": "抽奖设置", "cols": 4,
            "order": 22, "help": "连续遇到重复点击或请稍后时会自动延长，最长 30 秒。",
        },
        "start_lottery": {
            "type": "action", "label": "开始抽奖", "action": "start_lottery",
            "section": "任务控制", "cols": 4, "order": 30,
        },
        "stop_lottery": {
            "type": "action", "label": "停止抽奖", "action": "stop_lottery",
            "section": "任务控制", "cols": 4, "order": 31,
        },
        "view_result": {
            "type": "action", "label": "查看最近结果", "action": "view_result",
            "section": "任务控制", "cols": 4, "order": 32,
        },
        "view_stats": {
            "type": "action", "label": "查看累计统计", "action": "view_stats",
            "section": "任务控制", "cols": 6, "order": 33,
        },
        "test_cookie": {
            "type": "action", "label": "检查平台 Cookie", "action": "test_cookie",
            "section": "任务控制", "cols": 6, "order": 34,
        },
        "command_help": {
            "type": "info", "default": (
                "在“抽奖次数”中填写数量并保存，然后点击“开始抽奖”。\n"
                "完成结果可通过平台通知推送，也可点击“查看最近结果”。\n"
                "Cookie 由平台同步读取；请先在浏览器登录 hhanclub.net。"
            ),
            "label": "使用说明", "section": "说明", "cols": 12, "order": 40,
        },
    },
}


_PAGE_URL = "https://hhanclub.net/lucky.php"
_API_URL = "https://hhanclub.net/plugin/lucky-draw"
_DOMAIN = "hhanclub.net"
_STATS_KEY = "lottery_stats"
_LAST_RESULT_KEY = "last_result"
_STATUS_KEY = "task_status"
_PLAN_KEY = "lottery_resume_plan"
_MAILBOX_URL = "https://hhanclub.net/messages.php?action=viewmailbox&box=1&page=0"
_MAIL_KEYWORD = "幸运大转盘"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_SEGMENT_MAX_DRAWS = 150
_SEGMENT_MAX_SECONDS = 1200
_RESUME_DELAY_SECONDS = 2
_RESUME_BOOT_DELAY_SECONDS = 3
_active_task: asyncio.Task | None = None
_resume_task: asyncio.Task | None = None
_resume_handle: asyncio.TimerHandle | None = None
_stop_event: asyncio.Event | None = None


def _int(value, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _stop_at(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or "").strip())
    except (TypeError, ValueError):
        return None


def _headers(cookie: str, *, ajax: bool = False, referer: str = _PAGE_URL) -> dict[str, str]:
    headers = {
        "Accept": "*/*" if ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie,
        "Origin": "https://hhanclub.net",
        "Referer": referer,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    return headers


async def _cookie_header(ctx, *, request_sync: bool = True) -> tuple[str, str]:
    return await cookie_header(ctx, path="/lucky.php", request_sync=request_sync)


def _looks_like_login(resp: httpx.Response) -> bool:
    path = urlparse(str(resp.url)).path.lower()
    text = (resp.text or "").lower()
    return path.endswith(("/login.php", "/takelogin.php")) or (
        "takelogin.php" in text
        or ('name="username"' in text and 'name="password"' in text)
    )


def _has_challenge(text: str) -> bool:
    low = (text or "").lower()
    return any(x in low for x in (
        "cf-chl-", "challenge-platform", "cloudflare ray id", "checking your browser"
    ))


async def _same_site_request(client: httpx.AsyncClient, method: str, url: str,
                             headers: dict[str, str], *, content: bytes | None = None) -> tuple[httpx.Response, str]:
    """请求并只跟随 HHCLUB 站内跳转，避免显式 Cookie 泄露给其他域名。"""
    current_method = method.upper()
    resp = await client.request(current_method, url, headers=headers, content=content, follow_redirects=False)
    for _ in range(5):
        if resp.status_code not in _REDIRECT_CODES:
            return resp, ""
        location = str(resp.headers.get("location", "") or "").strip()
        if not location:
            return resp, f"HTTP {resp.status_code}（缺少 Location）"
        target = httpx.URL(str(resp.url)).join(location)
        if target.scheme not in {"http", "https"} or target.host != _DOMAIN:
            return resp, f"站点返回了不安全的跳转：{target}"
        current_method = "GET" if resp.status_code in {301, 302, 303} else current_method
        next_headers = dict(headers)
        if current_method == "GET":
            next_headers.pop("Origin", None)
            next_headers.pop("X-Requested-With", None)
            content = None
        resp = await client.request(
            current_method, str(target), headers=next_headers, content=content, follow_redirects=False
        )
    return resp, "站点跳转次数过多"


async def _page_info(ctx) -> tuple[bool, str, int, int]:
    cookie, error = await _cookie_header(ctx)
    if error:
        return False, error, 0, 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp, redirect_error = await _same_site_request(client, "GET", _PAGE_URL, _headers(cookie))
        if redirect_error:
            return False, redirect_error, 0, 0
        if resp.status_code != 200:
            return False, f"网站返回 HTTP {resp.status_code}", 0, 0
        if _looks_like_login(resp):
            return False, "Cookie 已失效，网站返回登录页", 0, 0
        if _has_challenge(resp.text):
            return False, "站点触发了 Cloudflare 安全验证，请重新同步 Cookie", 0, 0
        soup = BeautifulSoup(resp.text or "", "lxml")
        balance_el = soup.select_one(".bean-number")
        cost_el = soup.select_one(".use-bean")
        balance_match = re.search(r"([\d,]+(?:\.\d+)?)", balance_el.get_text(" ", strip=True)) if balance_el else None
        cost_match = re.search(r"([\d,]+)", cost_el.get_text(" ", strip=True)) if cost_el else None
        if not balance_match:
            return False, "登录成功，但未识别到转盘余额，网页结构可能已更新", 0, 0
        balance = int(float(balance_match.group(1).replace(",", "")))
        cost = int(cost_match.group(1).replace(",", "")) if cost_match else 2000
        return True, "Cookie 有效，已识别幸运转盘", balance, cost
    except Exception as exc:  # noqa: BLE001
        return False, f"访问 HHCLUB 失败：{exc}", 0, 0


async def _draw(client: httpx.AsyncClient, cookie: str) -> tuple[bool, str, bool]:
    """返回 (成功, 奖品或错误, 是否可重试)。"""
    try:
        resp, redirect_error = await _same_site_request(
            client, "POST", _API_URL, _headers(cookie, ajax=True)
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"请求失败：{exc}", True
    if redirect_error:
        return False, redirect_error, False
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}", resp.status_code >= 500
    if _looks_like_login(resp):
        return False, "Cookie 已失效，站点要求重新登录", False
    if _has_challenge(resp.text):
        return False, "站点触发了 Cloudflare 安全验证", False
    try:
        data = resp.json()
    except Exception:
        return False, "站点返回了非 JSON 响应", False
    if not isinstance(data, dict):
        return False, "站点返回的数据格式异常", False
    if data.get("ret") == 0:
        prize = data.get("data") or {}
        if not isinstance(prize, dict):
            prize = {}
        return True, str(prize.get("prize_text") or "未知奖品"), False
    detail = str(data.get("msg") or "未知错误")
    terminal_markers = ("次数", "用完", "余额不足", "憨豆不足")
    retryable = not any(marker in detail for marker in terminal_markers)
    return False, detail, retryable


def _bean_value(prize: str) -> int:
    if "憨豆" not in prize and "魔力" not in prize:
        return 0
    converted = re.search(r"已转换为憨豆\s*([\d,]+)", prize)
    if converted:
        return int(converted.group(1).replace(",", ""))
    match = re.search(r"(\d[\d,]*)", prize)
    return int(match.group(1).replace(",", "")) if match else 0


def _stop_target(prize: str, cfg: dict) -> str:
    if not cfg.get("stop_on_prize", False):
        return ""
    if cfg.get("stop_on_vip", True) and re.search(r"\bVIP\b", prize, re.IGNORECASE):
        return "VIP"
    if cfg.get("stop_on_invite", True) and "邀请" in prize:
        return "邀请"
    threshold = _int(cfg.get("big_bean_threshold"), 500_000, 1)
    if cfg.get("stop_on_big_beans", True) and _bean_value(prize) >= threshold:
        return f"大额憨豆（≥{threshold:,}）"
    keywords = [item.strip() for item in re.split(r"[,，\n]", str(cfg.get("stop_prize_keywords", "") or "")) if item.strip()]
    return next((f"关键词：{item}" for item in keywords if item in prize), "")


async def _clean_lottery_mail(ctx, *, max_rounds: int = 20) -> int:
    """只删除标题包含“幸运大转盘”的通知，保留其他站内信。"""
    cookie, error = await _cookie_header(ctx)
    if error:
        raise RuntimeError(error)
    removed = 0
    previous: tuple[str, ...] = ()
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
        for _ in range(max_rounds):
            resp, redirect_error = await _same_site_request(client, "GET", _MAILBOX_URL, _headers(cookie, referer=_MAILBOX_URL))
            if redirect_error:
                raise RuntimeError(redirect_error)
            if resp.status_code != 200 or _looks_like_login(resp):
                raise RuntimeError("读取转盘通知失败，Cookie 已失效或网站返回异常")
            soup = BeautifulSoup(resp.text or "", "lxml")
            targets = []
            box = soup.select_one("#mail-table-display")
            for checkbox in soup.select('#mail-table-display input[name="messages[]"]'):
                row = checkbox
                while box and row.parent and row.parent is not box:
                    row = row.parent
                if row and _MAIL_KEYWORD in row.get_text(" ", strip=True):
                    value = str(checkbox.get("value") or "").strip()
                    if value:
                        targets.append(value)
            targets = targets[:100]
            fingerprint = tuple(targets)
            if not targets or fingerprint == previous:
                break
            previous = fingerprint
            button = soup.select_one('input[type="submit"][name="delete"], button[name="delete"], input[type="submit"][name="del"], button[name="del"]')
            if not button:
                button = next((item for item in soup.select('input[type="submit"][name], button[name]') if "删除" in str(item.get("value") or item.get_text() or "")), None)
            if not button:
                raise RuntimeError("未识别到站内信删除表单")
            form = button.find_parent("form")
            action = urljoin(str(resp.url), str(form.get("action") or resp.url)) if form else str(resp.url)
            fields = []
            if form:
                fields.extend((str(item.get("name")), str(item.get("value") or "")) for item in form.select('input[type="hidden"][name]'))
            fields.extend(("messages[]", value) for value in targets)
            fields.append((str(button.get("name") or "delete"), str(button.get("value") or "删除")))
            headers = _headers(cookie, referer=_MAILBOX_URL)
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            deleted, redirect_error = await _same_site_request(
                client, "POST", action, headers,
                content=urlencode(fields, doseq=True).encode("utf-8"),
            )
            if redirect_error or deleted.status_code >= 400:
                raise RuntimeError(redirect_error or f"删除转盘通知失败：HTTP {deleted.status_code}")
            removed += len(targets)
    return removed


def _load_stats(ctx) -> dict:
    raw = ctx.kv.get(_STATS_KEY, {}) or {}
    return raw if isinstance(raw, dict) else {}


def _save_result(ctx, prizes: list[str], total_cost: int) -> None:
    stats = _load_stats(ctx)
    prize_stats = Counter(stats.get("prizes", {}) or {})
    prize_stats.update(prizes)
    stats.update({
        "count": _int(stats.get("count"), 0) + len(prizes),
        "cost": _int(stats.get("cost"), 0) + total_cost,
        "beans": _int(stats.get("beans"), 0) + sum(_bean_value(x) for x in prizes),
        "prizes": dict(prize_stats),
    })
    ctx.kv.set(_STATS_KEY, stats)


def _save_stats_payload(ctx, current: dict) -> None:
    """把已持久化的本轮聚合数据一次性并入累计统计。"""
    stats = _stats_payload(_load_stats(ctx))
    current = _stats_payload(current)
    prize_stats = Counter(stats.get("prizes", {}) or {})
    prize_stats.update(current.get("prizes", {}) or {})
    ctx.kv.set(_STATS_KEY, {
        "count": stats["count"] + current["count"],
        "cost": stats["cost"] + current["cost"],
        "beans": stats["beans"] + current["beans"],
        "prizes": dict(prize_stats),
    })


def _summary(title: str, prizes: list[str], total_cost: int, balance: int, detail: str = "") -> str:
    counts = Counter(prizes)
    bean_rewards = sum(_bean_value(item) for item in prizes)
    lines = [
        title, "",
        f"🎲 完成次数：{len(prizes)}",
        f"💸 本轮消耗：{total_cost:,} 憨豆",
        f"📈 憨豆净盈亏：{bean_rewards - total_cost:+,}",
        f"🫘 开始余额：{balance:,} 憨豆",
    ]
    if counts:
        lines.extend(["", "🎁 奖品统计："])
        lines.extend(f"• {name} × {count}" for name, count in counts.most_common())
    if detail:
        lines.extend(["", f"ℹ️ {detail}"])
    return "\n".join(lines)


def _summary_payload(title: str, current: dict, balance: int, detail: str = "") -> str:
    """从聚合状态生成完整摘要，续跑时无需保留庞大的逐条奖品列表。"""
    current = _stats_payload(current)
    lines = [
        title, "",
        f"🎲 完成次数：{current['count']}",
        f"💸 本轮消耗：{current['cost']:,} 憨豆",
        f"📈 憨豆净盈亏：{current['profit']:+,}",
        f"🫘 开始余额：{balance:,} 憨豆",
    ]
    counts = Counter(current["prizes"])
    if counts:
        lines.extend(["", "🎁 奖品统计："])
        lines.extend(f"• {name} × {count}" for name, count in counts.most_common())
    if detail:
        lines.extend(["", f"ℹ️ {detail}"])
    return "\n".join(lines)


def _stats_text(stats: dict) -> str:
    counts = Counter(stats.get("prizes", {}) or {})
    total_cost = _int(stats.get("cost"), 0)
    total_beans = _int(stats.get("beans"), 0)
    lines = [
        "📊 憨憨转盘累计统计", "",
        f"🎲 抽奖次数：{_int(stats.get('count'), 0):,}",
        f"💸 累计消耗：{total_cost:,} 憨豆",
        f"🫘 憨豆奖品：{total_beans:,}",
        f"📈 憨豆净盈亏：{total_beans - total_cost:+,}",
    ]
    if counts:
        lines.extend(["", "🎁 奖品明细："])
        lines.extend(f"• {html.unescape(str(name))} × {count}" for name, count in counts.most_common(20))
    return "\n".join(lines)


def _stats_payload(stats: dict) -> dict:
    """返回前端可直接渲染的统计结构，统一清理数值和 HTML 实体。"""
    cost = _int(stats.get("cost"), 0)
    beans = _int(stats.get("beans"), 0)
    return {
        "count": _int(stats.get("count"), 0),
        "cost": cost,
        "beans": beans,
        "profit": beans - cost,
        "prizes": {
            html.unescape(str(name)): _int(count, 0)
            for name, count in (stats.get("prizes", {}) or {}).items()
            if _int(count, 0) > 0
        },
    }


def _merge_stats(base: dict, current: dict) -> dict:
    """把尚未落盘的本轮统计合并到累计统计，供实时状态展示。"""
    base = _stats_payload(base)
    current = _stats_payload(current)
    counts = Counter(base["prizes"])
    counts.update(current["prizes"])
    return {
        "count": base["count"] + current["count"],
        "cost": base["cost"] + current["cost"],
        "beans": base["beans"] + current["beans"],
        "profit": base["profit"] + current["profit"],
        "prizes": dict(counts),
    }


async def setup(ctx):
    global _active_task, _resume_task, _resume_handle, _stop_event
    _active_task = None
    _resume_task = None
    _resume_handle = None
    _stop_event = asyncio.Event()
    stale_status = ctx.kv.get(_STATUS_KEY, {}) or {}
    if isinstance(stale_status, dict) and stale_status.get("running"):
        stale_status.update({"running": False, "detail": "插件已重载，正在检查续跑计划"})
        ctx.kv.set(_STATUS_KEY, stale_status)

    async def _notify_cookie(detail: str):
        if ctx.config.get("notify_cookie_error", True) and "Cookie" in detail:
            try:
                await ctx.notify(detail, level="warning", category="憨憨转盘")
            except Exception:
                pass

    async def _push_result(text: str, *, success: bool):
        if not ctx.config.get("notify_result", True):
            return
        try:
            await ctx.notify(
                text,
                level="success" if success else "warning",
                category="憨憨转盘",
            )
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("[憨憨转盘] 推送结果失败：%r", exc)

    async def _run(count: int | None, *, resumed: bool = False):
        global _active_task
        prizes: list[str] = []
        cfg = dict(ctx.config or {})
        mode = str(cfg.get("lottery_mode", "fixed"))
        reserve = _int(cfg.get("reserve_beans"), 0) if mode == "reserve" else 0
        sync_every = _int(cfg.get("sync_every_draws"), 20, 1)
        saved_plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
        restored = _stats_payload(saved_plan.get("current_stats", {}) or {}) if resumed else _stats_payload({})
        base_completed = restored["count"]
        current_counts: Counter = Counter(restored["prizes"])
        current_cost = restored["cost"]
        current_beans = restored["beans"]
        deadline = _stop_at(saved_plan.get("stop_at")) if resumed else (
            _stop_at(cfg.get("scheduled_stop_at")) if cfg.get("scheduled_stop_enabled", False) else None
        )
        mail_cleaned = 0
        requested = count or 0
        initial_target = base_completed + requested
        current_payload = {
            "count": base_completed, "cost": current_cost,
            "beans": current_beans, "prizes": dict(current_counts),
        }
        ctx.kv.set(_STATUS_KEY, {
            "running": True, "completed": base_completed, "target": initial_target,
            "detail": "正在恢复未完成任务" if resumed else "", "current_stats": current_payload,
        })
        startup_attempt = 0
        while True:
            ok, detail, balance, cost = await _page_info(ctx)
            if ok:
                break
            if not resumed:
                break
            if _stop_event and _stop_event.is_set():
                detail = "用户已手动停止恢复任务"
                ctx.kv.set(_PLAN_KEY, {})
                break
            if deadline and datetime.now() >= deadline:
                detail = f"平台恢复时已超过定时停止时间 {deadline:%Y-%m-%d %H:%M}"
                ctx.kv.set(_PLAN_KEY, {})
                break
            startup_attempt += 1
            delay = min(60, max(5, startup_attempt * 5))
            ctx.kv.set(_STATUS_KEY, {
                "running": True, "completed": base_completed, "target": initial_target,
                "detail": f"续跑等待平台就绪：{detail}；{delay} 秒后重试",
                "current_stats": current_payload,
            })
            if startup_attempt == 1 or startup_attempt % 10 == 0:
                ctx.log.warning(
                    "[憨憨转盘] 续跑启动检查失败（第 %s 次）：%s；%s 秒后重试",
                    startup_attempt, detail, delay,
                )
                await _notify_cookie(detail)
            await asyncio.sleep(delay)
        if not ok:
            if not resumed:
                ctx.kv.set(_PLAN_KEY, {})
            await _notify_cookie(detail)
            result_text = f"⚠️ 憨憨转盘无法启动\n\n{detail}"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": base_completed, "target": initial_target, "detail": detail, "current_stats": current_payload})
            await _push_result(result_text, success=False)
            _active_task = None
            return
        possible = max(0, balance - reserve) // cost if cost > 0 else 0
        remaining_target = possible if count is None else min(count, possible)
        target = base_completed + remaining_target
        estimated_balance = balance
        start_balance = _int(saved_plan.get("start_balance"), balance) if resumed else balance
        active_plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
        if active_plan.get("active"):
            active_plan["start_balance"] = start_balance
            active_plan["current_stats"] = current_payload
            ctx.kv.set(_PLAN_KEY, active_plan)
        ctx.kv.set(_STATUS_KEY, {"running": True, "completed": base_completed, "target": target, "balance": balance, "cost": cost, "current_stats": current_payload})
        if remaining_target <= 0:
            if base_completed:
                _save_stats_payload(ctx, current_payload)
            ctx.kv.set(_PLAN_KEY, {})
            result_text = f"💸 憨豆不足\n\n余额 {balance:,}，单次需要 {cost:,}。"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": base_completed, "target": target, "detail": "憨豆不足", "current_stats": current_payload})
            await _push_result(result_text, success=False)
            _active_task = None
            return

        cookie, error = await _cookie_header(ctx)
        cookie_attempt = 0
        while error and resumed and not (_stop_event and _stop_event.is_set()):
            if deadline and datetime.now() >= deadline:
                ctx.kv.set(_PLAN_KEY, {})
                break
            cookie_attempt += 1
            delay = min(60, max(5, cookie_attempt * 5))
            ctx.kv.set(_STATUS_KEY, {
                "running": True, "completed": base_completed, "target": target,
                "detail": f"续跑等待 Cookie 服务就绪：{error}；{delay} 秒后重试",
                "current_stats": current_payload,
            })
            if cookie_attempt == 1 or cookie_attempt % 10 == 0:
                ctx.log.warning(
                    "[憨憨转盘] 续跑 Cookie 检查失败（第 %s 次）：%s；%s 秒后重试",
                    cookie_attempt, error, delay,
                )
                await _notify_cookie(error)
            await asyncio.sleep(delay)
            cookie, error = await _cookie_header(ctx)
        if error:
            if not resumed:
                ctx.kv.set(_PLAN_KEY, {})
            result_text = f"⚠️ {error}"
            ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {"running": False, "completed": base_completed, "target": target, "detail": error, "current_stats": current_payload})
            await _push_result(result_text, success=False)
            _active_task = None
            return
        interval = _int(ctx.config.get("interval_seconds"), 7, 3)
        dynamic_interval = interval
        consecutive_retry = 0
        stop_detail = ""
        segment_started = asyncio.get_running_loop().time()
        segment_draws = 0
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
                while base_completed + len(prizes) < target:
                    if _stop_event and _stop_event.is_set():
                        stop_detail = "用户已手动停止任务"
                        break
                    if deadline and datetime.now() >= deadline:
                        stop_detail = f"已到定时停止时间 {deadline:%Y-%m-%d %H:%M}"
                        break
                    if estimated_balance - cost < reserve:
                        stop_detail = f"已到保留余额 {reserve:,} 憨豆，自动停止"
                        break
                    if segment_draws >= _SEGMENT_MAX_DRAWS or asyncio.get_running_loop().time() - segment_started >= _SEGMENT_MAX_SECONDS:
                        stop_detail = "后台任务分段续跑"
                        break
                    success, result, retryable = await _draw(client, cookie)
                    if success:
                        segment_draws += 1
                        before_balance = estimated_balance
                        estimated_balance = max(0, before_balance - cost + _bean_value(result))
                        if re.search(r"\bVIP\b", result, re.IGNORECASE) and _bean_value(result) == 0:
                            live_ok, _, live_balance, _ = await _page_info(ctx)
                            if live_ok:
                                converted = live_balance - (before_balance - cost)
                                estimated_balance = live_balance
                                if 900_000 <= converted <= 1_100_000:
                                    result = f"{result}（已转换为憨豆 {converted:,}）"
                        prizes.append(result)
                        current_counts[result] += 1
                        current_cost += cost
                        current_beans += _bean_value(result)
                        completed = base_completed + len(prizes)
                        current_payload = {
                            "count": completed,
                            "cost": current_cost,
                            "beans": current_beans,
                            "prizes": dict(current_counts),
                        }
                        plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
                        if plan.get("active"):
                            if count is not None:
                                plan["count"] = max(0, _int(plan.get("count"), count) - 1)
                            plan["start_balance"] = start_balance
                            plan["current_stats"] = current_payload
                            ctx.kv.set(_PLAN_KEY, plan)
                        consecutive_retry = 0
                        dynamic_interval = interval
                        ctx.kv.set(_STATUS_KEY, {
                            "running": True, "completed": completed, "target": target,
                            "last_prize": result, "balance": estimated_balance, "cost": cost,
                            "current_stats": current_payload,
                        })
                        ctx.log.info("[憨憨转盘] %s/%s prize=%s", completed, target, result)
                        hit = _stop_target(result, cfg)
                        if hit:
                            stop_detail = f"命中止损目标“{hit}”：{result}"
                            break
                        if completed % sync_every == 0:
                            live_ok, _, live_balance, live_cost = await _page_info(ctx)
                            if live_ok:
                                estimated_balance, cost = live_balance, live_cost
                            if cfg.get("auto_clean_lottery_mail", False):
                                try:
                                    mail_cleaned += await _clean_lottery_mail(ctx)
                                except Exception as exc:  # noqa: BLE001
                                    ctx.log.warning("[憨憨转盘] 自动清理通知失败：%s", exc)
                    elif retryable:
                        consecutive_retry += 1
                        ctx.log.warning("[憨憨转盘] 可重试错误：%s", result)
                        if consecutive_retry >= 3:
                            dynamic_interval = min(30, max(interval, int(dynamic_interval * 1.5)))
                        if consecutive_retry >= 12:
                            stop_detail = f"连续重试 {consecutive_retry} 次仍失败：{result}"
                            break
                        await asyncio.sleep(dynamic_interval)
                        continue
                    else:
                        stop_detail = result
                        await _notify_cookie(result)
                        break
                    if base_completed + len(prizes) < target:
                        await asyncio.sleep(dynamic_interval)
        except asyncio.CancelledError:
            stop_detail = "平台或插件正在重启，任务将在恢复后继续"
            raise
        finally:
            completed = base_completed + len(prizes)
            current_payload = {
                "count": completed, "cost": current_cost,
                "beans": current_beans, "prizes": dict(current_counts),
            }
            continuing = stop_detail.startswith("平台或插件正在重启") or stop_detail == "后台任务分段续跑"
            if completed and not continuing:
                _save_stats_payload(ctx, current_payload)
            title = "🎉 憨憨转盘完成" if completed == target else "🛑 憨憨转盘已停止"
            if count is not None and remaining_target < count and not stop_detail:
                stop_detail = f"余额最多支持新增 {remaining_target} 次，已自动缩减"
            if mail_cleaned:
                stop_detail = f"{stop_detail + '；' if stop_detail else ''}已清理 {mail_cleaned} 封转盘通知"
            result_text = _summary_payload(title, current_payload, start_balance, stop_detail)
            if not continuing:
                ctx.kv.set(_LAST_RESULT_KEY, result_text)
            ctx.kv.set(_STATUS_KEY, {
                "running": False, "completed": completed, "target": target,
                "detail": "正在切换下一段后台任务" if stop_detail == "后台任务分段续跑" else stop_detail,
                "last_prize": prizes[-1] if prizes else "",
                "current_stats": current_payload,
            })
            if not continuing:
                await _push_result(result_text, success=completed == target)
            _active_task = None
            if not continuing:
                ctx.kv.set(_PLAN_KEY, {})
            elif continuing:
                _schedule_resume(delay=_RESUME_DELAY_SECONDS)
            if _stop_event:
                _stop_event.clear()

    @ctx.action("test_cookie")
    async def test_cookie():
        ok, message, balance, cost = await _page_info(ctx)
        if ok:
            message += f"；余额 {balance:,}，单次消耗 {cost:,}"
        return {"ok": ok, "message": message}

    @ctx.action("clean_lottery_mail")
    async def clean_lottery_mail():
        try:
            removed = await _clean_lottery_mail(ctx)
            return {"ok": True, "message": f"已删除 {removed} 封“幸运大转盘”通知，其他站内信已保留"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"清理转盘通知失败：{exc}"}

    @ctx.action("start_lottery")
    async def start_lottery():
        global _active_task
        if not ctx.config.get("enabled", True):
            return {"ok": False, "message": "请先启用憨憨转盘插件"}
        if _active_task and not _active_task.done():
            status = ctx.kv.get(_STATUS_KEY, {}) or {}
            return {
                "ok": False,
                "message": f"已有任务运行中：{_int(status.get('completed'), 0)}/{_int(status.get('target'), 0)}",
            }
        mode = str(ctx.config.get("lottery_mode", "fixed"))
        balance_mode = mode in {"balance", "reserve"}
        count = None if balance_mode else _int(ctx.config.get("lottery_count"), 10, 1)
        if count is not None and count < 1:
            return {"ok": False, "message": "抽奖次数必须是大于 0 的整数"}
        if _stop_event:
            _stop_event.clear()
        deadline = _stop_at(ctx.config.get("scheduled_stop_at")) if ctx.config.get("scheduled_stop_enabled", False) else None
        if ctx.config.get("scheduled_stop_enabled", False) and not deadline:
            return {"ok": False, "message": "请设置有效的定时停止日期和时间"}
        if deadline and deadline <= datetime.now():
            return {"ok": False, "message": "定时停止时间必须晚于当前时间"}
        ctx.kv.set(_PLAN_KEY, {
            "active": True,
            "count": count,
            "stop_at": deadline.isoformat(timespec="minutes") if deadline else "",
        })
        _active_task = ctx.create_task(
            _run(count), name="憨憨转盘后台任务", operation="lottery"
        )
        if mode == "reserve":
            plan = f"将保留 {_int(ctx.config.get('reserve_beans'), 0):,} 憨豆，其余余额自动抽取"
        else:
            plan = "将按当前余额计算全部可抽次数" if balance_mode else f"计划抽奖 {count} 次"
        return {"ok": True, "message": f"憨憨转盘已开始，{plan}；可在面板查看进度。"}

    @ctx.action("stop_lottery")
    async def stop_lottery():
        if not (_active_task and not _active_task.done()):
            return {"ok": False, "message": "当前没有正在运行的抽奖任务"}
        if _stop_event:
            _stop_event.set()
        ctx.kv.set(_PLAN_KEY, {})
        return {"ok": True, "message": "已请求停止，当前请求完成后退出"}

    @ctx.action("view_result")
    async def view_result():
        status = ctx.kv.get(_STATUS_KEY, {}) or {}
        if status.get("running"):
            message = (
                f"抽奖进行中：{_int(status.get('completed'), 0)}/"
                f"{_int(status.get('target'), 0)}"
            )
            if status.get("last_prize"):
                message += f"；最近奖品：{status['last_prize']}"
            return {"ok": True, "message": message}
        result = str(ctx.kv.get(_LAST_RESULT_KEY, "") or "")
        return {"ok": bool(result), "message": result or "暂无抽奖结果"}

    @ctx.action("view_stats")
    async def view_stats():
        return {"ok": True, "message": _stats_text(_load_stats(ctx))}

    @ctx.on_api("/lottery/status", methods=["GET", "POST"])
    async def lottery_status(_request=None):
        status = dict(ctx.kv.get(_STATUS_KEY, {}) or {})
        status["running"] = bool(_active_task and not _active_task.done())
        status.setdefault("completed", 0)
        status.setdefault("target", 0)
        status["last_result"] = str(ctx.kv.get(_LAST_RESULT_KEY, "") or "")
        current = _stats_payload(status.get("current_stats", {}) or {})
        cumulative = _stats_payload(_load_stats(ctx))
        if status["running"]:
            cumulative = _merge_stats(cumulative, current)
        status["current_stats"] = current
        status["cumulative_stats"] = cumulative
        status["setup_error"] = str(ctx.kv.get("lottery_setup_error", "") or "")
        status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return status

    @ctx.on_api("/lottery/run", methods=["POST"])
    async def lottery_run(_request=None):
        return await start_lottery()

    @ctx.on_api("/lottery/stop", methods=["POST"])
    async def lottery_stop(_request=None):
        return await stop_lottery()

    @ctx.on_api("/lottery/cookie/check", methods=["GET"])
    async def lottery_cookie_check(_request=None):
        return await test_cookie()

    @ctx.on_api("/lottery/mail/clean", methods=["POST"])
    async def lottery_mail_clean(_request=None):
        return await clean_lottery_mail()

    @ctx.on_api("/lottery/stats", methods=["GET", "POST"])
    async def lottery_stats(_request=None):
        stats = _load_stats(ctx)
        return {"ok": True, "text": _stats_text(stats), "stats": stats}

    async def _resume_supervisor():
        """用单个托管任务直接执行续跑，避免守护器与工作任务同时占满并发。"""
        global _active_task
        await asyncio.sleep(_RESUME_BOOT_DELAY_SECONDS)
        while True:
            plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
            if not plan.get("active"):
                break
            resume_deadline = _stop_at(plan.get("stop_at"))
            resume_count = plan.get("count")
            if resume_deadline and resume_deadline <= datetime.now():
                ctx.kv.set(_PLAN_KEY, {})
                ctx.kv.set(_STATUS_KEY, {
                    "running": False, "completed": 0, "target": _int(resume_count, 0),
                    "detail": f"平台恢复时已超过定时停止时间 {resume_deadline:%Y-%m-%d %H:%M}",
                })
                break
            if resume_count is not None and _int(resume_count, 0) <= 0:
                ctx.kv.set(_PLAN_KEY, {})
                break
            if _stop_event:
                _stop_event.clear()
            _active_task = asyncio.current_task()
            ctx.log.info("[憨憨转盘] 检测到未完成计划，单任务模式开始续跑")
            try:
                await _run(None if resume_count is None else _int(resume_count, 0, 1), resumed=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                ctx.log.exception("[憨憨转盘] 续跑任务异常退出：%r", exc)
                ctx.kv.set(_STATUS_KEY, {
                    "running": False, "completed": 0, "target": _int(resume_count, 0),
                    "detail": f"续跑任务异常：{exc}；10 秒后重试",
                })
            finally:
                if _active_task is asyncio.current_task():
                    _active_task = None
            if _resume_task is not asyncio.current_task():
                break
            if not (ctx.kv.get(_PLAN_KEY, {}) or {}).get("active"):
                break
            await asyncio.sleep(10)

    def _schedule_resume(*, delay: float = 0):
        """释放当前任务后再创建下一段；创建失败会持续退避重试。"""
        global _resume_task, _resume_handle

        if _resume_handle and not _resume_handle.cancelled():
            return

        def launch():
            global _resume_task, _resume_handle
            _resume_handle = None
            plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
            if not plan.get("active"):
                return
            if _resume_task and not _resume_task.done():
                _schedule_resume(delay=1)
                return
            supervisor_coro = _resume_supervisor()
            try:
                _resume_task = ctx.create_task(
                    supervisor_coro, name="憨憨转盘重启续跑任务", operation="lottery"
                )
                ctx.kv.set("lottery_setup_error", "")
                ctx.log.info("[憨憨转盘] 已创建下一段续跑任务")
            except Exception as exc:  # noqa: BLE001
                supervisor_coro.close()
                _resume_task = None
                ctx.kv.set("lottery_setup_error", f"续跑任务启动失败：{exc}")
                ctx.log.exception("[憨憨转盘] 续跑任务启动失败，10 秒后重试：%r", exc)
                _resume_handle = asyncio.get_running_loop().call_later(10, launch)

        if delay > 0:
            _resume_handle = asyncio.get_running_loop().call_later(delay, launch)
        else:
            launch()

    pending_plan = dict(ctx.kv.get(_PLAN_KEY, {}) or {})
    if pending_plan.get("active"):
        _schedule_resume()
    else:
        ctx.kv.set("lottery_setup_error", "")


async def teardown(ctx):
    global _active_task, _resume_task, _resume_handle
    if _resume_handle and not _resume_handle.cancelled():
        _resume_handle.cancel()
    _resume_handle = None
    tasks = list({id(task): task for task in (_resume_task, _active_task) if task and not task.done()}.values())
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    if _resume_handle and not _resume_handle.cancelled():
        _resume_handle.cancel()
    _resume_handle = None
    _active_task = None
    _resume_task = None


async def self_check(ctx):
    cookie, error = await _cookie_header(ctx, request_sync=False)
    return {
        "id": "cookie_sync",
        "name": "平台 Cookie 同步",
        "ok": bool(cookie),
        "detail": "已读取 hhanclub.net Cookie" if cookie else error,
    }
