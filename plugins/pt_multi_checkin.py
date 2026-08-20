"""多站点 PT 自动签到：平台 CloakBrowser + 平台/手动 Cookie。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import urlparse


SITES = {
    "audiences": {"name": "观众 Audiences", "domain": "audiences.me", "url": "https://audiences.me/attendance.php"},
    "ourbits": {"name": "OurBits", "domain": "ourbits.club", "url": "https://ourbits.club/attendance.php"},
    "piggo": {"name": "PigGo", "domain": "piggo.me", "url": "https://piggo.me/attendance.php"},
    "tjupt": {"name": "北洋园 TJUPT", "domain": "tjupt.org", "url": "https://tjupt.org/attendance.php"},
}


def _site_schema():
    schema = {}
    order = 10
    for key, site in SITES.items():
        section = site["name"]
        schema[f"{key}_enabled"] = {
            "type": "boolean", "default": True, "label": "启用签到",
            "section": section, "cols": 4, "order": order,
        }
        schema[f"{key}_cookie_source"] = {
            "type": "select", "default": "platform", "label": "Cookie 来源",
            "options": [
                {"label": "从平台读取", "value": "platform"},
                {"label": "手动填写", "value": "manual"},
            ],
            "section": section, "cols": 4, "order": order + 1,
        }
        schema[f"{key}_cookie"] = {
            "type": "password", "default": "", "label": "手动 Cookie",
            "help": "仅在 Cookie 来源选择“手动填写”时使用；可省略 Cookie: 前缀。",
            "section": section, "cols": 4, "order": order + 2,
        }
        order += 10
    return schema


__plugin__ = {
    "name": "PT站自动签到",
    "id": "pt_multi_checkin",
    "version": "1.0.3",
    "author": "AWdress",
    "description": "可持续扩展的多 PT 站自动签到助手，使用平台 CloakBrowser，支持平台或手动 Cookie。",
    "icon": "https://audiences.me/favicon.ico",
    "changelog": "v1.0.3 按真实站点结果适配\n- 兼容 Audiences 实际使用的“已签到”状态\n- 识别 TJUPT 影视图片签到验证码并明确提示人工处理\n- Cookie、验证码和权限类错误不再无意义自动重试\n\nv1.0.2 修复签到误判与任务清理\n- 点击或访问签到页后必须确认成功或已签到状态\n- 结果未知时仅刷新确认，绝不重复点击签到\n- 插件停用时等待后台任务完成清理",
    "scope": "standalone",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": [
        "audiences.me", "*.audiences.me", "ourbits.club", "*.ourbits.club",
        "piggo.me", "*.piggo.me", "tjupt.org", "*.tjupt.org",
    ],
    "default_enabled": False,
    "resources": {
        "timeout_seconds": 1800, "max_concurrency": 1, "max_background_tasks": 3,
        "failure_threshold": 3, "recovery_seconds": 120,
    },
    "config_schema": {
        "auto_checkin": {
            "type": "boolean", "default": True, "label": "启用每日自动签到",
            "section": "任务设置", "cols": 4, "order": 1,
        },
        "notify_result": {
            "type": "boolean", "default": True, "label": "推送签到结果",
            "section": "任务设置", "cols": 4, "order": 2,
        },
        "headless": {
            "type": "boolean", "default": True, "label": "无头浏览器",
            "help": "服务器建议保持开启；底层优先使用与色花堂助手相同的 CloakBrowser。",
            "section": "任务设置", "cols": 4, "order": 3,
        },
        "checkin_hour": {
            "type": "slider", "default": 8, "label": "签到小时",
            "min": 0, "max": 23, "step": 1, "section": "定时与重试", "cols": 3, "order": 4,
        },
        "checkin_minute": {
            "type": "slider", "default": 10, "label": "签到分钟",
            "min": 0, "max": 59, "step": 1, "section": "定时与重试", "cols": 3, "order": 5,
        },
        "retry_count": {
            "type": "slider", "default": 2, "label": "失败重试次数",
            "min": 0, "max": 5, "step": 1, "section": "定时与重试", "cols": 3, "order": 6,
        },
        "retry_interval": {
            "type": "slider", "default": 20, "label": "重试间隔（秒）",
            "min": 5, "max": 300, "step": 5, "section": "定时与重试", "cols": 3, "order": 7,
        },
        **_site_schema(),
        "run_now": {
            "type": "action", "label": "立即签到全部启用站点", "action": "run_now",
            "section": "操作", "cols": 6, "order": 100,
        },
        "view_result": {
            "type": "action", "label": "查看最近结果", "action": "view_result",
            "section": "操作", "cols": 6, "order": 101,
        },
        "usage": {
            "type": "info", "label": "说明", "section": "说明", "cols": 12, "order": 110,
            "default": "每个站点可独立选择 Cookie 来源。遇到 Cloudflare 时浏览器会等待验证；若出现需要人工操作的交互式验证码，本轮会报告失败，不会绕过验证码。",
        },
    },
}


_run_lock: asyncio.Lock | None = None
_tasks: set[asyncio.Task] = set()
_HISTORY_KEY = "history"
_LAST_KEY = "last_result"


def _bounded(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clean_cookie(value) -> tuple[str, str]:
    cookie = str(value or "").strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    if not cookie:
        return "", "尚未填写手动 Cookie"
    if "\r" in cookie or "\n" in cookie or "=" not in cookie:
        return "", "手动 Cookie 格式不正确"
    return cookie, ""


async def _site_cookie(ctx, key: str, site: dict) -> tuple[str, str]:
    source = str(ctx.config.get(f"{key}_cookie_source", "platform") or "platform")
    if source == "manual":
        return _clean_cookie(ctx.config.get(f"{key}_cookie"))
    if not ctx.cookies.available:
        return "", "平台 Cookie 同步未启用"
    try:
        cookie = await ctx.cookies.header(site["domain"], path="/attendance.php")
    except Exception as exc:  # noqa: BLE001
        return "", f"读取平台 Cookie 失败：{exc}"
    if cookie:
        return cookie, ""
    try:
        await ctx.cookies.request_sync(site["domain"])
    except Exception:
        pass
    try:
        cookie = await ctx.cookies.header(site["domain"], path="/attendance.php")
    except Exception:
        cookie = ""
    if cookie:
        return cookie, ""
    return "", "平台中没有该站 Cookie，请登录网站并同步"


def _page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return page.content()


def _result_state(text: str) -> tuple[str, str] | None:
    """只根据明确的站点反馈判断结果，避免把普通 200 页面误报为成功。"""
    low = (text or "").lower()
    already_markers = (
        "今日已签到", "今天已签到", "已经签到", "签到已完成", "今日已经签到", "已签到", "签到已得",
        "already attended", "already signed", "attended today", "already checked in",
    )
    success_markers = (
        "签到成功", "成功签到", "签到获得", "签到奖励",
        "attend got", "attend get bonus", "attend get bouns",
        "attendance success", "check-in successful", "checked in successfully",
    )
    failure_markers = (
        "签到失败", "操作频繁", "验证失败", "请求失败", "稍后再试",
        "attendance failed", "check-in failed", "too many requests", "rate limit",
    )
    if any(marker in low for marker in already_markers):
        return "already", "今天已经签到"
    if any(marker in low for marker in success_markers):
        return "success", "签到成功"
    if any(marker in low for marker in failure_markers):
        return "failed", "网站返回签到失败、验证失败或操作频繁"
    return None


def _captcha_error(text: str) -> str:
    low = (text or "").lower()
    if any(marker in low for marker in (
        "签到验证码", "请选择与左侧图片对应", "回答正确将获得", "回答错误将反向扣除",
    )):
        return "网站要求完成签到图片验证码，需要人工签到，本插件不会自动提交答案"
    if any(marker in low for marker in (
        "turnstile", "hcaptcha", "recaptcha", "交互式验证码",
    )):
        return "网站要求完成交互式验证码，需要人工处理"
    return ""


def _retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    permanent = (
        "cookie", "登录页", "人工签到", "人工处理", "验证码", "没有访问权限",
        "非预期域名", "格式不正确",
    )
    return not any(marker in text for marker in permanent)


def _confirm_result(page, *, attempts: int = 3) -> dict:
    """刷新确认服务端状态；绝不为确认结果而再次点击签到按钮。"""
    for attempt in range(attempts):
        text = _page_text(page)
        captcha = _captcha_error(text)
        if captcha:
            raise RuntimeError(captcha)
        state = _result_state(text)
        if state:
            status, message = state
            if status == "failed":
                raise RuntimeError(message)
            return {"status": status, "message": message}
        if attempt + 1 < attempts:
            page.wait_for_timeout(2_000 * (attempt + 1))
            page.reload(wait_until="domcontentloaded", timeout=60_000)
    raise RuntimeError("签到请求后无法确认成功状态，未计为签到成功")


def _browser_checkin(page, expected_domain: str) -> dict:
    """在平台托管的同步 Playwright 页面内完成单站签到。"""
    page.set_default_timeout(20_000)
    for _ in range(30):
        title = (page.title() or "").lower()
        text = _page_text(page).lower()
        challenged = any(marker in f"{title}\n{text}" for marker in (
            "just a moment", "checking your browser", "cloudflare ray id", "cf-chl-",
            "请完成安全验证", "验证您是否是真人",
        ))
        if not challenged:
            break
        page.wait_for_timeout(3_000)
    else:
        raise RuntimeError("Cloudflare 验证等待超时；若为交互式验证码需要人工处理")

    current_domain = (urlparse(page.url).hostname or "").lower()
    if current_domain not in {expected_domain, f"www.{expected_domain}"}:
        raise RuntimeError(f"站点跳转到了非预期域名：{current_domain or '未知'}")
    text = _page_text(page)
    low = text.lower()
    html = page.content().lower()
    if any(marker in low for marker in (
        "用户名或密码", "please login", "not logged in", "请先登录",
    )) or 'name="username"' in html or "name='username'" in html or urlparse(page.url).path.lower().endswith(("/login.php", "/takelogin.php")):
        raise RuntimeError("Cookie 已失效，网站返回登录页")
    if any(marker in low for marker in ("没有权限", "无权访问", "permission denied", "access denied", "page not found", "404 not found")):
        raise RuntimeError("签到页面不可用或当前账号没有访问权限")
    captcha = _captcha_error(text)
    if captcha:
        raise RuntimeError(captcha)
    initial_state = _result_state(text)
    if initial_state:
        status, message = initial_state
        if status == "failed":
            raise RuntimeError(message)
        return {"status": status, "message": message}

    candidates = page.locator('a, button, input[type="submit"], input[type="button"]')
    for index in range(min(candidates.count(), 80)):
        item = candidates.nth(index)
        try:
            if not item.is_visible() or not item.is_enabled():
                continue
            label = (item.inner_text() or item.get_attribute("value") or "").strip()
            normalized = "".join(label.split()).lower()
            if normalized not in {"签到", "立即签到", "点击签到", "今日未签到", "attend", "checkin", "check-in"}:
                continue
            item.click()
            page.wait_for_timeout(3_000)
            return _confirm_result(page)
        except RuntimeError:
            raise
        except Exception:
            continue

    # 标准 NexusPHP attendance.php 通常由 GET 完成签到；刷新后必须出现明确结果。
    if urlparse(page.url).path.lower().endswith("/attendance.php"):
        return _confirm_result(page)
    raise RuntimeError("没有识别到签到页面或签到按钮，网站结构可能已更新")


async def _run(ctx, source: str) -> dict:
    global _run_lock
    if _run_lock is None:
        _run_lock = asyncio.Lock()
    if _run_lock.locked():
        return {"ok": False, "message": "签到任务正在运行"}
    async with _run_lock:
        enabled = [(key, site) for key, site in SITES.items() if ctx.config.get(f"{key}_enabled", True)]
        if not enabled:
            return {"ok": False, "message": "没有启用任何签到站点"}
        results = []
        retries = _bounded(ctx.config.get("retry_count"), 2, 0, 5)
        interval = _bounded(ctx.config.get("retry_interval"), 20, 5, 300)
        for key, site in enabled:
            cookie, error = await _site_cookie(ctx, key, site)
            if error:
                results.append({"site": site["name"], "ok": False, "status": "failed", "message": error})
                continue
            item = None
            for attempt in range(retries + 1):
                try:
                    def action(page, domain=site["domain"]):
                        return _browser_checkin(page, domain)

                    outcome = await ctx.browser.run(
                        site["url"], action, cookies=cookie,
                        headless=bool(ctx.config.get("headless", True)), timeout=150,
                    )
                    status = str((outcome or {}).get("status") or "success")
                    item = {
                        "site": site["name"], "ok": True, "status": status,
                        "message": str((outcome or {}).get("message") or "签到完成"),
                    }
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt < retries and _retryable_error(exc):
                        await asyncio.sleep(interval)
                    else:
                        item = {"site": site["name"], "ok": False, "status": "failed", "message": str(exc)}
                        break
            results.append(item)

        success = sum(1 for item in results if item["ok"])
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = f"{source}签到完成：成功 {success}/{len(results)}"
        text = summary + "\n" + "\n".join(
            f"{'成功' if item['ok'] else '失败'} · {item['site']}：{item['message']}" for item in results
        )
        record = {"time": stamp, "ok": success == len(results), "summary": summary, "sites": results}
        history = ctx.kv.get(_HISTORY_KEY, []) or []
        if not isinstance(history, list):
            history = []
        ctx.kv.set(_HISTORY_KEY, [record, *history][:30])
        ctx.kv.set(_LAST_KEY, text)
        if ctx.config.get("notify_result", True):
            rows = [{"站点": item["site"], "结果": "已签到" if item["status"] == "already" else ("成功" if item["ok"] else "失败"), "详情": item["message"]} for item in results]
            try:
                await ctx.notify(rows, level="success" if success == len(results) else "warning", category="PT站签到")
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("签到结果推送失败：%r", exc)
        return {"ok": success == len(results), "message": text, "results": results}


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()

    @ctx.action("run_now")
    async def run_now():
        if _run_lock and _run_lock.locked():
            return {"ok": True, "message": "签到任务已经在后台运行"}
        task = ctx.create_task(_run(ctx, "手动"), name="PT站手动签到", operation="manual_checkin")
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        return {"ok": True, "message": "签到任务已开始，完成后会推送汇总结果"}

    @ctx.action("view_result")
    async def view_result():
        text = str(ctx.kv.get(_LAST_KEY, "") or "")
        return {"ok": bool(text), "message": text or "暂无签到记录"}

    if ctx.config.get("auto_checkin", True):
        hour = _bounded(ctx.config.get("checkin_hour"), 8, 0, 23)
        minute = _bounded(ctx.config.get("checkin_minute"), 10, 0, 59)

        async def scheduled():
            await _run(ctx, "定时")

        ctx.schedule(scheduled, "cron", hour=hour, minute=minute, id="PT站每日签到")


async def teardown(ctx):
    tasks = list(_tasks)
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()
