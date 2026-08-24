"""GPT-GOD 自动签到：使用平台托管浏览器完成登录和网页签到。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import re
import time


__plugin__ = {
    "name": "GPT-GOD 自动签到",
    "id": "gptgod_checkin",
    "version": "1.1.8",
    "author": "AWdress",
    "description": "使用平台托管浏览器为多个 GPT-GOD 账号每日自动签到，支持独立会话复用、立即签到和汇总通知。",
    "changelog": "v1.1.8 修复新版福利页误点快捷入口\n- 严格匹配‘签到 领取 N 积分’按钮，不再误点‘签到 / 兑换码’快捷入口\n- 本地使用真实账号完成首次签到并取得服务端 success 回执\n- 二次运行正确识别今天已签到，不会重复提交\n\nv1.1.7 适配 GPT-GOD 新版签到回执\n- 兼容空 2xx、纯文本与 JSON 三类响应\n- 修复 JSON 解析失败时丢弃成功 HTTP 状态导致的误报失败",
    "icon": "https://gptgod.online/favicon.ico",
    "scope": "standalone",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "default_enabled": False,
    "resources": {
        "timeout_seconds": 1800,
        "max_concurrency": 1,
        "max_background_tasks": 2,
        "failure_threshold": 3,
        "recovery_seconds": 120,
    },
    "config_schema": {
        "auto_checkin": {
            "type": "boolean", "default": True, "label": "启用自动签到",
            "section": "功能开关", "cols": 4, "order": 1,
        },
        "notify": {
            "type": "boolean", "default": True, "label": "推送签到结果",
            "section": "功能开关", "cols": 4, "order": 2,
        },
        "auto_retry": {
            "type": "boolean", "default": True, "label": "失败后自动重试",
            "help": "仅重试浏览器启动、网络、页面加载和网站临时异常；明确的账号密码错误不会重试。",
            "section": "功能开关", "cols": 4, "order": 3,
        },
        "accounts": {
            "type": "list", "default": [], "label": "签到账号", "item_label": "账号",
            "help": "逐个添加 GPT-GOD 账号。旧版单账号配置会自动继续使用。",
            "section": "账号", "cols": 12, "order": 10,
            "fields": {
                "email": {
                    "type": "string", "label": "登录邮箱",
                    "help": "GPT-GOD 注册邮箱。",
                },
                "password": {
                    "type": "password", "label": "账户密码",
                    "help": "GPT-GOD 账户密码，不是邮箱密码。",
                },
            },
        },
        "checkin_hour": {
            "type": "slider", "default": 8, "label": "签到小时",
            "min": 0, "max": 23, "step": 1, "section": "定时", "cols": 6, "order": 20,
        },
        "checkin_minute": {
            "type": "slider", "default": 5, "label": "签到分钟",
            "min": 0, "max": 59, "step": 1, "section": "定时", "cols": 6, "order": 21,
        },
        "retry_count": {
            "type": "slider", "default": 2, "label": "失败重试次数",
            "min": 0, "max": 5, "step": 1,
            "help": "单个账号首次失败后最多再次尝试的次数。",
            "section": "重试", "cols": 6, "order": 24,
        },
        "retry_interval": {
            "type": "slider", "default": 20, "label": "重试间隔（秒）",
            "min": 5, "max": 300, "step": 5,
            "help": "两次尝试之间的等待时间，建议至少 20 秒，避免网站限流。",
            "section": "重试", "cols": 6, "order": 25,
        },
        "run_now": {
            "type": "action", "label": "立即签到", "action": "run_now",
            "section": "操作", "cols": 6, "order": 30,
        },
        "last_result": {
            "type": "info", "default": "尚未运行", "label": "最近结果",
            "section": "运行状态", "cols": 12, "order": 40,
        },
        "checkin_history": {
            "type": "info", "default": "暂无记录", "label": "最近签到记录",
            "section": "运行状态", "cols": 12, "order": 41,
        },
    },
}


LOGIN_URL = "https://gptgod.online/login"
WELFARE_URL = "https://gptgod.online/token/welfare"
HISTORY_KEY = "checkin_history"
HISTORY_LIMIT = 30
SESSION_KEY = "account_sessions"
LEGACY_SESSION_KEY = "account_session"
_run_lock: asyncio.Lock | None = None
_background_tasks: set[asyncio.Task] = set()


def _bounded_int(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except Exception:  # noqa: BLE001 - 兼容不同浏览器引擎
        return page.content()


def _matching_locators(page, selector: str):
    try:
        locator = page.locator(selector)
        count = min(locator.count(), 20)
    except Exception:  # noqa: BLE001 - 页面切换时 locator 可能短暂失效
        return

    for index in range(count):
        try:
            yield locator.nth(index)
        except Exception:  # noqa: BLE001 - 尝试同一选择器的下一个元素
            continue


def _click_first_visible(
    page,
    selectors: tuple[str, ...],
    *,
    require_enabled: bool = False,
):
    for selector in selectors:
        for candidate in _matching_locators(page, selector):
            try:
                if not candidate.is_visible(timeout=1_000):
                    continue
                if require_enabled and not candidate.is_enabled():
                    continue
                candidate.click()
                return True
            except Exception:  # noqa: BLE001 - 尝试下一个可见元素或选择器
                continue
    return False


def _click_visible_button_text(page, labels: tuple[str, ...]) -> bool:
    """按可见按钮实际文字精确点击，忽略网站在“登 录”中插入的空格。"""
    normalized_labels = {"".join(str(label).split()).lower() for label in labels}
    try:
        buttons = page.locator("button")
        count = min(buttons.count(), 30)
    except Exception:  # noqa: BLE001 - 页面切换时按未匹配处理
        return False
    matches = []
    for index in range(count):
        try:
            candidate = buttons.nth(index)
            text = "".join(candidate.inner_text().split()).lower()
            if candidate.is_visible(timeout=1_000) and text in normalized_labels:
                matches.append(candidate)
        except Exception:  # noqa: BLE001 - 尝试下一个按钮
            continue
    if len(matches) != 1:
        return False
    try:
        matches[0].click()
        return True
    except Exception:  # noqa: BLE001 - 交给 Enter 兜底
        return False


def _type_like_user(locator, value: str) -> None:
    """触发真实键盘事件；GPT-GOD 受控表单不会可靠接收 Playwright.fill。"""
    locator.click()
    locator.press("Control+A")
    locator.type(str(value), delay=20)


def _wait_for_any_visible(page, selectors: tuple[str, ...], timeout_ms: int = 45_000):
    """等待 SPA 渲染出任一目标控件，返回第一个可见 locator。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        for selector in selectors:
            for candidate in _matching_locators(page, selector):
                try:
                    if candidate.is_visible(timeout=500):
                        return candidate
                except Exception:  # noqa: BLE001 - SPA 导航过程中 locator 可能短暂失效
                    continue
        page.wait_for_timeout(500)
    return None


def _current_url(page) -> str:
    value = getattr(page, "url", "")
    return str(value() if callable(value) else value)


def _clear_site_frontend_cache(page) -> None:
    """清除持久 Docker 浏览器中的旧前端构建缓存，不触碰登录 Cookie。"""
    try:
        page.evaluate("""async () => {
            if ('caches' in window) {
                for (const key of await caches.keys()) await caches.delete(key);
            }
            if ('serviceWorker' in navigator) {
                for (const reg of await navigator.serviceWorker.getRegistrations()) {
                    await reg.unregister();
                }
            }
        }""")
    except Exception:  # noqa: BLE001 - 站点未启用相关能力时无需处理
        pass


def _fresh_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_aw_checkin={int(time.time() * 1000)}"


def _goto_fresh(page, url: str) -> None:
    page.goto(_fresh_url(url), wait_until="domcontentloaded")


def _loading_error(page, area: str) -> RuntimeError:
    text = _page_text(page)
    if any(marker in text for marker in (
        "Loading CSS chunk", "Loading chunk", "ChunkLoadError",
        "Failed to fetch dynamically imported module", "Something went wrong",
    )):
        return RuntimeError(f"{area}前端资源加载失败，已清理缓存但 GPT-GOD 当前发布资源仍不可用")
    if any(marker in text for marker in (
        "Just a moment", "Checking your browser", "验证您是否是真人",
        "请完成安全验证", "Cloudflare",
    )):
        return RuntimeError(f"{area}被 Cloudflare 验证拦截，平台浏览器暂时无法自动通过")
    if any(marker in text for marker in ("502 Bad Gateway", "503 Service", "网络异常", "连接超时")):
        return RuntimeError(f"{area}加载失败，GPT-GOD 当前网络或服务异常")
    return RuntimeError(f"{area}加载超时，未找到预期控件")


def _checkin_result(page, status: str, message: str, trace=None) -> dict:
    return {"status": status, "message": message}


def _displayed_account_matches(page, email: str) -> bool:
    displayed_emails = {
        value.casefold()
        for value in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", _page_text(page))
    }
    return not displayed_emails or email.casefold() in displayed_emails


def _masked_email(email: str) -> str:
    local, separator, domain = str(email or "").partition("@")
    if not separator:
        return (local[:2] + "***") if local else "未知账号"
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


def _visible_checkin_state(page) -> str | None:
    """只读取可见按钮，避免隐藏的桌面/移动端组件污染整页文字判断。"""
    try:
        buttons = page.locator("button")
        count = min(buttons.count(), 80)
    except Exception:  # noqa: BLE001 - 页面切换期间按未知状态处理
        return None
    for index in range(count):
        try:
            candidate = buttons.nth(index)
            if not candidate.is_visible(timeout=500):
                continue
            text = "".join(candidate.inner_text().split()).lower()
            if text in {"今天已签到", "今日已签到", "alreadycheckedintoday"}:
                return "already"
            if (
                text in {"签到", "check-in", "checkin"}
                or text.startswith("签到领取")
                or text.startswith("check-infor")
            ):
                return "claim"
        except Exception:  # noqa: BLE001 - 尝试下一个按钮
            continue
    # 新版页面顶部还会显示独立状态徽标；某些窄屏布局中操作按钮延迟挂载，
    # 但徽标已经可见。只接受精确文字且实际可见的元素，避免再次误读隐藏模板。
    for label in ("今天已签到", "今日已签到", "Already Checked In Today"):
        try:
            matches = page.get_by_text(label, exact=True)
            for index in range(min(matches.count(), 20)):
                if matches.nth(index).is_visible(timeout=300):
                    return "already"
        except Exception:  # noqa: BLE001 - 引擎不支持 get_by_text 时继续
            continue
    # 新版 Ant Design 页面可能把操作区渲染为带 role 的容器而非 button。
    # body.inner_text 只返回实际渲染文字，可避开 display:none 的响应式模板。
    try:
        visible_text = "".join(_page_text(page).split()).lower()
        if "今天已签到" in visible_text or "今日已签到" in visible_text:
            return "already"
        if (
            "签到领取" in visible_text
            or "每日签到" in visible_text and "签到" in visible_text
            or "check-in" in visible_text and "already" not in visible_text
        ):
            return "claim"
    except Exception:  # noqa: BLE001
        pass
    return None


def _click_checkin(page) -> bool:
    """严格点击领取按钮，避免误点同页“签到 / 兑换码”快捷入口。"""
    try:
        candidates = page.locator('button, [role="button"], .ant-btn')
        for index in range(min(candidates.count(), 100)):
            candidate = candidates.nth(index)
            if not candidate.is_visible(timeout=500) or not candidate.is_enabled():
                continue
            text = "".join(candidate.inner_text().split()).lower()
            if not (
                text in {"签到", "check-in", "checkin"}
                or re.fullmatch(r"签到领取[\d,.]+积分", text)
                or re.fullmatch(r"check-infor[\d,.]+points", text)
            ):
                continue
            candidate.click()
            return True
    except Exception:  # noqa: BLE001 - 交给 DOM 事件兜底
        pass
    # 末级兼容同样使用严格全文规则，不使用 :has-text() 的包含匹配。
    try:
        return bool(page.evaluate("""() => {
            const nodes = [...document.querySelectorAll('button,[role="button"],a,.ant-btn')];
            const target = nodes.find((node) => {
                const text = (node.innerText || '').replace(/\\s+/g, '').toLowerCase();
                const style = getComputedStyle(node);
                const visible = style.display !== 'none' && style.visibility !== 'hidden'
                    && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0;
                const enabled = !node.disabled && node.getAttribute('aria-disabled') !== 'true';
                return visible && enabled && (
                    text === '签到' || /^签到领取[\d,.]+积分$/.test(text)
                    || text === 'check-in' || text === 'checkin'
                    || /^check-infor[\d,.]+points$/.test(text)
                );
            });
            if (!target) return false;
            target.click();
            return true;
        }"""))
    except Exception:  # noqa: BLE001
        return False


def _classify_checkin_response(response) -> tuple[str, str] | None:
    """读取官方 /user/checkin 响应；服务端结果优先于可能滞后的 SPA 按钮。"""
    try:
        url = str(getattr(response, "url", "") or "")
        if "/user/checkin" not in url:
            return None
        status = int(getattr(response, "status", 0) or 0)
    except Exception:  # noqa: BLE001 - 无法读取响应元数据时交给页面状态兜底
        return None

    payload = None
    raw_text = ""
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - 新版接口可能返回空响应或纯文本
        try:
            raw_text = str(response.text() or "")
        except Exception:  # noqa: BLE001 - 仍可使用 HTTP 状态判断
            raw_text = ""

    text = str(payload) if payload is not None else raw_text
    message = ""
    if isinstance(payload, dict):
        message = str(payload.get("message") or payload.get("msg") or "").strip()
        code = payload.get("code")
        success = payload.get("success")
        data = payload.get("data")
        if isinstance(data, dict):
            message = str(data.get("message") or data.get("msg") or message).strip()
        lowered = f"{message} {text}".lower()
        if any(marker in lowered for marker in ("already", "已签到", "重复签到")):
            return "already", message or "今天已经签到"
        if success is False or code not in (None, 0, 200, "0", "200"):
            return "failure", message or f"签到接口返回失败（code={code}）"
        if success is True or code in (0, 200, "0", "200"):
            return "success", message or "签到接口已确认成功"
    lowered = text.casefold()
    if any(marker in lowered for marker in ("already", "已签到", "重复签到")):
        return "already", text.strip() or "今天已经签到"
    if any(marker in lowered for marker in ("签到成功", "check-in successful", "checkin success")):
        return "success", text.strip() or "签到接口已确认成功"
    if 200 <= status < 300:
        return "success", message or "签到接口已确认成功"
    return "failure", message or f"签到接口返回 HTTP {status}"


def _start_checkin_response_watch(page):
    watch = {"results": []}

    def _on_response(response):
        result = _classify_checkin_response(response)
        if result is not None:
            watch["results"].append(result)

    try:
        page.on("response", _on_response)
        watch["callback"] = _on_response
    except Exception:  # noqa: BLE001 - 不支持事件监听时继续使用页面核验
        watch["callback"] = None
    return watch


def _stop_checkin_response_watch(page, watch) -> None:
    callback = watch.get("callback") if watch else None
    if callback:
        try:
            page.remove_listener("response", callback)
        except Exception:  # noqa: BLE001
            pass


def _wait_for_checkin_state(
    page, timeout_ms: int = 45_000, *, stop_on_login: bool = False,
) -> str | None:
    """等待 SPA 签到卡片稳定。Docker 首屏渲染慢时会自动滚动并重载一次。"""
    deadline = time.monotonic() + timeout_ms / 1000
    reloaded = False
    while time.monotonic() < deadline:
        if stop_on_login and "/login" in _current_url(page):
            return None
        state = _visible_checkin_state(page)
        if state:
            return state
        try:
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        except Exception:  # noqa: BLE001
            pass
        remaining = deadline - time.monotonic()
        if not reloaded and remaining < timeout_ms / 2000:
            try:
                _clear_site_frontend_cache(page)
                _goto_fresh(page, WELFARE_URL)
                reloaded = True
            except Exception:  # noqa: BLE001 - 继续在当前页面等待
                pass
        page.wait_for_timeout(750)
    return None


def _session_cookie(page) -> str:
    try:
        return "; ".join(
            f"{item['name']}={item['value']}"
            for item in page.context.cookies()
            if item.get("name") and item.get("value")
        )
    except Exception:  # noqa: BLE001 - Cookie 缓存失败不影响本次签到
        return ""


def _finish_checkin(page, email: str, trace=None) -> dict:
    trace = trace or (lambda _message: None)
    trace("核验当前登录账号")
    if not _displayed_account_matches(page, email):
        raise RuntimeError("网站实际登录账号与插件当前配置邮箱不一致，已停止签到以防串号")
    account = _masked_email(email)
    trace("等待免费积分页签到控件")
    state = _wait_for_checkin_state(page)
    trace(f"签到状态识别结果：{state or '未识别'}")
    if state == "already":
        trace("网站显示今天已签到，当前账号完成")
        return _checkin_result(page, "already", f"账号 {account} 今天已经签到，无需重复领取", trace)
    if state != "claim":
        raise RuntimeError("未找到可见的签到状态按钮，网站页面可能已更新")

    trace("点击签到控件并监听服务端结果")
    watch = _start_checkin_response_watch(page)
    try:
        if not _click_checkin(page):
            raise RuntimeError("未找到签到按钮，网站页面可能已更新")

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not watch["results"]:
            page.wait_for_timeout(250)
        if watch["results"]:
            api_state, api_message = watch["results"][-1]
            trace(f"签到接口结果：{api_state}（{api_message}）")
            if api_state == "success":
                return _checkin_result(page, "success", f"账号 {account} 签到成功，服务端已确认", trace)
            if api_state == "already":
                return _checkin_result(page, "already", f"账号 {account} 今天已经签到，无需重复领取", trace)
            raise RuntimeError(api_message or "签到接口返回失败")

        # 新版 SPA 的接口事件在极慢容器中可能早于监听器挂载完成；成功提示
        # 与按钮状态均来自服务端响应，可作为提交后的即时确认。
        immediate_text = "".join(_page_text(page).split()).casefold()
        if any(marker in immediate_text for marker in (
            "签到成功", "获得积分", "check-insuccessful", "receivedpoints",
        )) or _visible_checkin_state(page) == "already":
            trace("页面即时状态已确认签到成功")
            return _checkin_result(page, "success", f"账号 {account} 签到成功，页面状态已确认", trace)
    finally:
        _stop_checkin_response_watch(page, watch)

    try:
        page.locator(
            'button:has-text("今天已签到"), button:has-text("今日已签到"), '
            'button:has-text("Already Checked In Today")'
        ).wait_for(state="visible", timeout=30_000)
    except Exception:  # noqa: BLE001 - 重新载入积分页进行最终核验
        pass

    trace("签到请求已提交，重新加载免费积分页确认结果")
    _goto_fresh(page, WELFARE_URL)
    result_state = _wait_for_checkin_state(page, timeout_ms=45_000)
    trace(f"签到后状态确认：{result_state or '未识别'}")
    result_text = _page_text(page)
    if result_state == "already":
        trace("签到成功，当前账号完成")
        return _checkin_result(page, "success", f"账号 {account} 签到成功，已领取每日积分", trace)
    for marker in ("签到失败", "操作频繁", "请稍后", "验证失败", "网络异常"):
        if marker in result_text:
            raise RuntimeError(marker)
    raise RuntimeError("签到后未能确认成功状态，请稍后重试")


def _browser_checkin(
    page, email: str, password: str, reuse_session: bool = False, trace=None,
) -> dict:
    """同步浏览器动作；由 ctx.browser.run 在线程中执行。"""
    trace = trace or (lambda _message: None)
    email_selectors = (
            "#email",
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="邮箱"]',
            'input[placeholder*="Email"]',
    )

    if reuse_session:
        trace("检测到同账号缓存会话，清理旧前端缓存")
        _clear_site_frontend_cache(page)
        trace("使用缓存会话打开免费积分页")
        _goto_fresh(page, WELFARE_URL)
        cached_state = _wait_for_checkin_state(
            page, timeout_ms=75_000, stop_on_login=True,
        )
        trace(f"缓存会话状态：{cached_state or '无效或页面未加载'}")
        if cached_state is not None and _displayed_account_matches(page, email):
            trace("缓存会话有效，无需重新登录")
            result = _finish_checkin(page, email, trace)
            result["session_cookie"] = _session_cookie(page)
            return result
        cached_login_input = _wait_for_any_visible(page, email_selectors, timeout_ms=2_000)
        if cached_login_input is not None or "/login" in _current_url(page):
            trace("缓存 Cookie 被网站拒绝并返回登录页，切换为干净登录流程")
        else:
            trace("缓存 Cookie 未被退回登录页，但页面长期未渲染签到控件，重新登录恢复")

    # Docker 浏览器内核可能残留旧站点会话。每次清理状态并使用当前配置
    # 重新登录，避免换号后沿用旧账号的“今天已签到”状态。
    try:
        trace("清理旧账号 Cookie")
        page.context.clear_cookies()
    except Exception:  # noqa: BLE001 - 部分浏览器内核可能不暴露该方法
        pass
    trace("打开 GPT-GOD 登录页")
    _goto_fresh(page, LOGIN_URL)
    try:
        trace("清理站点本地存储和旧前端缓存")
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        _clear_site_frontend_cache(page)
        _goto_fresh(page, LOGIN_URL)
    except Exception:  # noqa: BLE001 - 页面未使用本地存储时不影响登录
        pass

    email_input = _wait_for_any_visible(page, email_selectors, timeout_ms=33_000)
    if email_input is None:
        raise _loading_error(page, "登录页")
    trace("登录页邮箱输入框已加载")
    password_input = _wait_for_any_visible(page, (
        "#password",
        'input[name="password"]',
        'input[type="password"]',
    ), timeout_ms=10_000)
    if password_input is None:
        raise _loading_error(page, "登录页密码框")
    trace("填写登录表单（敏感内容不写入日志）")
    _type_like_user(email_input, email)
    _type_like_user(password_input, password)
    submitted = _click_visible_button_text(page, ("登 录", "登录", "Login", "Sign in"))
    if not submitted:
        try:
            password_input.press("Enter")
            submitted = True
        except Exception:  # noqa: BLE001 - 下方统一返回表单提交错误
            pass
    if not submitted:
        raise RuntimeError("登录表单无法提交，网站页面可能已更新")
    trace("登录表单已提交，等待网站建立会话")

    try:
        page.wait_for_url("**/session/**", timeout=15_000)
    except Exception:  # noqa: BLE001 - 以受保护页面的实际访问结果为最终依据
        pass
    login_text = _page_text(page)
    for marker in ("邮箱或密码错误", "密码错误", "登录失败", "账号不存在", "网络异常"):
        if marker in login_text:
            raise RuntimeError(marker)

    trace("登录响应未发现账号错误，清理前端缓存")
    _clear_site_frontend_cache(page)
    trace("打开免费积分页")
    _goto_fresh(page, WELFARE_URL)
    welfare_state = _wait_for_checkin_state(page, timeout_ms=60_000)
    trace(f"免费积分页状态：{welfare_state or '未找到签到控件'}")
    if welfare_state is None:
        login_input = _wait_for_any_visible(page, email_selectors, timeout_ms=2_000)
        if login_input is not None or "/login" in _current_url(page):
            raise RuntimeError("登录状态未生效，请检查邮箱、密码或网站安全验证")
        raise _loading_error(page, "免费积分页")

    result = _finish_checkin(page, email, trace)
    result["session_cookie"] = _session_cookie(page)
    return result


def _configured_accounts(config: dict) -> list[dict]:
    accounts = []
    seen = set()
    raw_accounts = config.get("accounts") or []
    if isinstance(raw_accounts, list):
        for item in raw_accounts:
            if not isinstance(item, dict):
                continue
            email = str(item.get("email") or "").strip()
            password = str(item.get("password") or "")
            key = email.casefold()
            if email and password and key not in seen:
                seen.add(key)
                accounts.append({"email": email, "password": password})
    # 兼容升级前已经保存的单账号字段；列表中存在同邮箱时不重复添加。
    legacy_email = str(config.get("email") or "").strip()
    legacy_password = str(config.get("password") or "")
    if legacy_email and legacy_password and legacy_email.casefold() not in seen:
        accounts.append({"email": legacy_email, "password": legacy_password})
    return accounts


def _retryable_error(exc: Exception) -> bool:
    message = str(exc or "")
    permanent_markers = (
        "邮箱或密码错误", "密码错误", "账号不存在",
        "账户不存在", "账号已禁用", "账户已禁用",
    )
    return not any(marker in message for marker in permanent_markers)


def _friendly_error(exc: Exception) -> str:
    message = str(exc or "未知错误")
    lowered = message.casefold()
    if "executable doesn't exist" in lowered or "headless_shell" in lowered:
        return "平台托管浏览器运行文件不存在，请更新或重建容器的浏览器运行时"
    return message


async def _run(ctx, source: str) -> dict:
    global _run_lock
    if _run_lock is None:
        _run_lock = asyncio.Lock()
    if _run_lock.locked():
        return {"ok": False, "message": "已有签到任务正在运行，请稍后再试"}

    async with _run_lock:
        accounts = _configured_accounts(dict(ctx.config or {}))
        if not accounts:
            result = {"ok": False, "message": "请先添加至少一个 GPT-GOD 签到账号"}
        else:
            ctx.log.info("开始%s签到，共 %s 个账号", source, len(accounts))
            sessions = ctx.kv.get(SESSION_KEY, {}) or {}
            if not isinstance(sessions, dict):
                sessions = {}
            legacy_session = ctx.kv.get(LEGACY_SESSION_KEY, {}) or {}
            if isinstance(legacy_session, dict):
                legacy_email = str(legacy_session.get("email") or "").casefold()
                legacy_cookie = str(legacy_session.get("cookie") or "")
                if legacy_email and legacy_cookie and legacy_email not in sessions:
                    sessions[legacy_email] = legacy_cookie

            account_results = []
            for index, account in enumerate(accounts, 1):
                email, password = account["email"], account["password"]
                account_key = email.casefold()
                masked = _masked_email(email)
                cached_cookie = str(sessions.get(account_key) or "")
                ctx.log.info(
                    "[签到流程][%s/%s][%s] 启动托管浏览器；会话缓存=%s",
                    index, len(accounts), masked, "有" if cached_cookie else "无",
                )

                def trace(message: str, label=masked) -> None:
                    ctx.log.info("[签到流程][%s] %s", label, message)

                def browser_action(page):
                    try:
                        return _browser_checkin(
                            page, email, password, bool(cached_cookie), trace,
                        )
                    except Exception as exc:
                        ctx.log.error("[签到流程][%s] 浏览器步骤失败：%s", masked, exc)
                        raise

                auto_retry = bool(ctx.config.get("auto_retry", True))
                retry_count = _bounded_int(ctx.config.get("retry_count"), 2, 0, 5) if auto_retry else 0
                retry_interval = _bounded_int(ctx.config.get("retry_interval"), 20, 5, 300)
                max_attempts = retry_count + 1
                item = None

                for attempt in range(1, max_attempts + 1):
                    ctx.log.info(
                        "[签到流程][%s] 开始第 %s/%s 次尝试",
                        masked, attempt, max_attempts,
                    )
                    try:
                        browser_result = await ctx.browser.run(
                            LOGIN_URL, browser_action,
                            cookies=cached_cookie or None,
                            headless=True, timeout=240,
                        )
                        session_cookie = str((browser_result or {}).get("session_cookie") or "")
                        if session_cookie:
                            sessions[account_key] = session_cookie
                            ctx.log.info("[签到流程][%s] 已更新独立会话缓存", masked)
                        status = str((browser_result or {}).get("status") or "")
                        if status not in ("success", "already"):
                            raise RuntimeError(
                                str((browser_result or {}).get("message") or "签到结果未确认")
                            )
                        message = str((browser_result or {}).get("message") or "签到完成")
                        if attempt > 1:
                            message = f"{message}（第 {attempt} 次尝试成功）"
                        item = {
                            "account": masked,
                            "ok": True,
                            "already": status == "already",
                            "message": message,
                            "attempts": attempt,
                        }
                        ctx.log.info(
                            "[签到流程][%s] 完成，结果=%s，尝试=%s",
                            masked, status, attempt,
                        )
                        break
                    except Exception as exc:  # noqa: BLE001 - 按配置重试或继续下一个账号
                        can_retry = attempt < max_attempts and _retryable_error(exc)
                        if can_retry:
                            ctx.log.warning(
                                "[签到流程][%s] 第 %s/%s 次尝试失败：%s；%s 秒后重试",
                                masked, attempt, max_attempts, _friendly_error(exc), retry_interval,
                            )
                            await asyncio.sleep(retry_interval)
                            continue
                        item = {
                            "account": masked,
                            "ok": False,
                            "message": f"账号 {masked} 签到失败：{_friendly_error(exc)}",
                            "attempts": attempt,
                        }
                        ctx.log.error(
                            "[签到流程][%s] 签到失败，已尝试 %s 次：%r",
                            masked, attempt, exc,
                        )
                        break
                account_results.append(item)

            ctx.kv.set(SESSION_KEY, sessions)
            ctx.kv.delete(LEGACY_SESSION_KEY)
            success_count = sum(1 for item in account_results if item["ok"])
            failed_count = len(account_results) - success_count
            summary = f"多账号签到完成：成功 {success_count}，失败 {failed_count}"
            details = "\n".join(item["message"] for item in account_results)
            result = {
                "ok": failed_count == 0,
                "partial": success_count > 0 and failed_count > 0,
                "message": f"{summary}\n{details}",
                "accounts": account_results,
            }

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display = f"{stamp} · {result['message']}"
        record = {"time": stamp, **result}
        history = ctx.kv.get(HISTORY_KEY, [])
        if not isinstance(history, list):
            history = []
        history = [*history, record][-HISTORY_LIMIT:]
        history_display = "\n\n".join(
            f"{item.get('time', '')} · {item.get('message', '')}"
            for item in reversed(history[-10:])
        )
        ctx.update_config({
            "last_result": display,
            "checkin_history": history_display or "暂无记录",
        })
        ctx.kv.set("last_result", record)
        ctx.kv.set(HISTORY_KEY, history)
        if ctx.config.get("notify", True):
            try:
                level = "success" if result["ok"] else ("warning" if result.get("partial") else "error")
                rows = [
                    {
                        "账号": item.get("account", ""),
                        "结果": "已签到" if item.get("already") else ("成功" if item.get("ok") else "失败"),
                        "尝试次数": item.get("attempts", 1),
                        "详情": item.get("message", ""),
                    }
                    for item in result.get("accounts", [])
                ]
                await ctx.notify(rows or result["message"], level=level, category="GPT-GOD 签到")
            except Exception as exc:  # noqa: BLE001 - 通知失败不改变签到结果
                ctx.log.warning("签到结果通知失败：%r", exc)
        ctx.log.info("%s", result["message"])
        return result


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()

    @ctx.action("run_now")
    async def _run_now():
        if not _configured_accounts(dict(ctx.config or {})):
            return {"ok": False, "message": "请先添加至少一个 GPT-GOD 签到账号"}
        if _run_lock and _run_lock.locked():
            return {"ok": True, "message": "签到任务已在后台运行，请查看运行日志"}
        task = ctx.create_task(
            _run(ctx, "手动"), name="GPT-GOD 手动签到", operation="manual_checkin"
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"ok": True, "message": "多账号签到已在后台开始，请查看运行日志"}

    if ctx.config.get("auto_checkin", True):
        hour = _bounded_int(ctx.config.get("checkin_hour"), 8, 0, 23)
        minute = _bounded_int(ctx.config.get("checkin_minute"), 5, 0, 59)

        async def _scheduled_checkin():
            ctx.log.info("定时任务已触发")
            await _run(ctx, "定时")

        ctx.schedule(
            _scheduled_checkin,
            "cron",
            hour=hour,
            minute=minute,
            id="GPT-GOD 每日签到",
        )
        ctx.log.info("已注册每日签到任务：%02d:%02d", hour, minute)
    else:
        ctx.log.info("自动签到未启用，仅保留手动签到")


async def teardown(ctx):
    for task in list(_background_tasks):
        if not task.done():
            task.cancel()
    _background_tasks.clear()
    ctx.log.info("GPT-GOD 自动签到插件已停用")
