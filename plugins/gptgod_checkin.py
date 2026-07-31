"""GPT-GOD 自动签到：使用平台托管浏览器完成登录和网页签到。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import re
import time


__plugin__ = {
    "name": "GPT-GOD 自动签到",
    "id": "gptgod_checkin",
    "version": "1.0.12",
    "author": "AWdress",
    "description": "使用平台托管浏览器登录 GPT-GOD，每日自动领取签到积分，支持立即签到和结果通知。",
    "changelog": "v1.0.12 增加分步骤运行日志\n- 记录浏览器启动、缓存会话、前端缓存清理、登录提交、积分页加载、状态识别、签到点击和积分读取步骤\n- 失败日志附带当前步骤，且不会输出密码、Cookie 等敏感内容\n\nv1.0.11 修复 Docker 前端缓存失效\n- 清理 Cache Storage 与旧 Service Worker，并使用防缓存地址加载页面\n- 兼容非按钮签到控件并识别 ChunkLoadError\n\nv1.0.10 修复 Docker 签到页加载识别\n- 等待 SPA 完整渲染签到卡片并兼容顶部已签到状态\n\nv1.0.9 修复 Docker 环境积分未显示\n- 从免费积分页读取当前可用积分，读取失败时刷新重试\n\nv1.0.0 初始版本\n- 支持网站原生登录、定时签到、立即签到和结果通知",
    "icon": "https://gptgod.online/favicon.ico",
    "scope": "user",
    "default_enabled": False,
    "config_schema": {
        "auto_checkin": {
            "type": "boolean", "default": True, "label": "启用自动签到",
            "section": "功能开关", "cols": 4, "order": 1,
        },
        "notify": {
            "type": "boolean", "default": True, "label": "推送签到结果",
            "section": "功能开关", "cols": 4, "order": 2,
        },
        "email": {
            "type": "string", "default": "", "label": "登录邮箱",
            "help": "GPT-GOD 注册邮箱。", "section": "账号", "cols": 6, "order": 10,
        },
        "password": {
            "type": "password", "default": "", "label": "账户密码",
            "help": "GPT-GOD 账户密码，不是邮箱密码。", "section": "账号", "cols": 6, "order": 11,
        },
        "checkin_hour": {
            "type": "slider", "default": 8, "label": "签到小时",
            "min": 0, "max": 23, "step": 1, "section": "定时", "cols": 6, "order": 20,
        },
        "checkin_minute": {
            "type": "slider", "default": 5, "label": "签到分钟",
            "min": 0, "max": 59, "step": 1, "section": "定时", "cols": 6, "order": 21,
        },
        "run_now": {
            "type": "action", "label": "立即签到", "action": "run_now",
            "section": "操作", "cols": 6, "order": 30,
        },
        "last_result": {
            "type": "info", "default": "尚未运行", "label": "最近结果",
            "section": "运行状态", "cols": 12, "order": 40,
        },
        "current_points": {
            "type": "info", "default": "尚未读取", "label": "当前积分",
            "section": "运行状态", "cols": 12, "order": 41,
        },
        "checkin_history": {
            "type": "info", "default": "暂无记录", "label": "最近签到记录",
            "section": "运行状态", "cols": 12, "order": 42,
        },
    },
}

LOGIN_URL = "https://gptgod.online/login"
WELFARE_URL = "https://gptgod.online/token/welfare"
POINTS_URL = "https://gptgod.online/token/rule"
HISTORY_KEY = "checkin_history"
HISTORY_LIMIT = 30
SESSION_KEY = "account_session"
_run_lock: asyncio.Lock | None = None


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


def _extract_points(text: str) -> str | None:
    patterns = (
        r"当前可用积分\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(万)?",
        r"(?:^|\s)积分\s*[:：]?\s*([\d,]+(?:\.\d+)?)\s*(万)?(?:\s|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, str(text or ""), re.MULTILINE)
        if not match:
            continue
        raw_value = match.group(1).replace(",", "")
        try:
            if match.group(2):
                value = int(float(raw_value) * 10_000)
            else:
                value = int(float(raw_value))
        except (TypeError, ValueError):
            continue
        return f"{value:,}"
    return None


def _read_current_points(page, timeout_ms: int = 30_000) -> str | None:
    # 当前签到页已经包含精确的“当前可用积分”，先直接读取，避免 Docker
    # 环境跳转到积分规则页后 SPA 尚未渲染或页面结构不同而丢失积分。
    points = _extract_points(_page_text(page))
    if points:
        return points
    _goto_fresh(page, WELFARE_URL)
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        points = _extract_points(_page_text(page))
        if points:
            return points
        if "/login" in _current_url(page):
            return None
        page.wait_for_timeout(500)
    return None


def _checkin_result(page, status: str, message: str) -> dict:
    points = None
    try:
        points = _read_current_points(page)
    except Exception:  # noqa: BLE001 - 积分读取失败不能改变签到结果
        pass
    if points:
        message = f"{message}，剩余积分：{points}"
    return {"status": status, "message": message, "points": points}


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
    if _click_first_visible(page, (
        'button:has-text("签到领取")',
        'button:has-text("签到")',
        '[role="button"]:has-text("签到领取")',
        '[role="button"]:has-text("签到")',
        'button:has-text("Check-in")',
        '[role="button"]:has-text("Check-in")',
    ), require_enabled=True):
        return True
    # 末级兼容：只点击可见、可交互且文字明确为签到的元素。
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
                    text === '签到' || text.startsWith('签到领取')
                    || text === 'check-in' || text === 'checkin'
                );
            });
            if (!target) return false;
            target.click();
            return true;
        }"""))
    except Exception:  # noqa: BLE001
        return False


def _wait_for_checkin_state(page, timeout_ms: int = 45_000) -> str | None:
    """等待 SPA 签到卡片稳定。Docker 首屏渲染慢时会自动滚动并重载一次。"""
    deadline = time.monotonic() + timeout_ms / 1000
    reloaded = False
    while time.monotonic() < deadline:
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
        trace("网站显示今天已签到，开始读取当前积分")
        return _checkin_result(page, "already", f"账号 {account} 今天已经签到，无需重复领取")
    if state != "claim":
        raise RuntimeError("未找到可见的签到状态按钮，网站页面可能已更新")

    trace("点击签到控件")
    if not _click_checkin(page):
        raise RuntimeError("未找到签到按钮，网站页面可能已更新")

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
        trace("签到成功，开始读取当前积分")
        return _checkin_result(page, "success", f"账号 {account} 签到成功，已领取每日积分")
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
        cached_state = _wait_for_checkin_state(page, timeout_ms=20_000)
        trace(f"缓存会话状态：{cached_state or '无效或页面未加载'}")
        if cached_state is not None and _displayed_account_matches(page, email):
            trace("缓存会话有效，无需重新登录")
            result = _finish_checkin(page, email, trace)
            result["session_cookie"] = _session_cookie(page)
            return result
        trace("缓存会话不可用，切换为干净登录流程")

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


async def _run(ctx, source: str) -> dict:
    global _run_lock
    if _run_lock is None:
        _run_lock = asyncio.Lock()
    if _run_lock.locked():
        return {"ok": False, "message": "已有签到任务正在运行，请稍后再试"}

    async with _run_lock:
        email = str(ctx.config.get("email") or "").strip()
        password = str(ctx.config.get("password") or "")
        if not email or not password:
            result = {"ok": False, "message": "请先配置 GPT-GOD 登录邮箱和账户密码"}
        else:
            ctx.log.info("开始%s签到", source)
            try:
                cached_session = ctx.kv.get(SESSION_KEY, {}) or {}
                same_account = (
                    isinstance(cached_session, dict)
                    and str(cached_session.get("email") or "").casefold() == email.casefold()
                )
                cached_cookie = str(cached_session.get("cookie") or "") if same_account else ""
                if not same_account:
                    ctx.kv.delete(SESSION_KEY)
                ctx.log.info(
                    "[签到流程] 启动平台托管浏览器；账号=%s，会话缓存=%s",
                    _masked_email(email), "有" if cached_cookie else "无",
                )

                def trace(message: str) -> None:
                    ctx.log.info("[签到流程] %s", message)

                def browser_action(page):
                    try:
                        return _browser_checkin(
                            page, email, password, bool(cached_cookie), trace,
                        )
                    except Exception as exc:
                        ctx.log.error("[签到流程] 浏览器步骤失败：%s", exc)
                        raise

                browser_result = await ctx.browser.run(
                    LOGIN_URL,
                    browser_action,
                    cookies=cached_cookie or None,
                    headless=True,
                    timeout=240,
                )
                session_cookie = str((browser_result or {}).get("session_cookie") or "")
                if session_cookie:
                    ctx.kv.set(SESSION_KEY, {"email": email, "cookie": session_cookie})
                    ctx.log.info("[签到流程] 已更新当前账号会话缓存")
                status = str((browser_result or {}).get("status") or "")
                ctx.log.info("[签到流程] 流程完成，结果=%s", status or "未知")
                result = {
                    "ok": status in ("success", "already"),
                    "already": status == "already",
                    "message": str((browser_result or {}).get("message") or "签到完成"),
                    "points": (browser_result or {}).get("points"),
                }
            except Exception as exc:  # noqa: BLE001 - 转换成可读运行结果
                ctx.log.error("签到失败：%r", exc)
                result = {"ok": False, "message": f"签到失败：{exc}"}

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display = f"{stamp} · {result['message']}"
        record = {"time": stamp, **result}
        history = ctx.kv.get(HISTORY_KEY, [])
        if not isinstance(history, list):
            history = []
        history = [*history, record][-HISTORY_LIMIT:]
        history_display = "\n".join(
            f"{item.get('time', '')} · {item.get('message', '')}"
            for item in reversed(history[-10:])
        )
        config_updates = {
            "last_result": display,
            "checkin_history": history_display or "暂无记录",
        }
        if result.get("points"):
            config_updates["current_points"] = f"{result['points']} 积分"
        ctx.update_config(config_updates)
        ctx.kv.set("last_result", record)
        ctx.kv.set(HISTORY_KEY, history)
        if ctx.config.get("notify", True):
            try:
                level = "success" if result["ok"] and not result.get("already") else (
                    "info" if result["ok"] else "error"
                )
                await ctx.notify(result["message"], level=level, category="GPT-GOD 签到")
            except Exception as exc:  # noqa: BLE001 - 通知失败不改变签到结果
                ctx.log.warning("签到结果通知失败：%r", exc)
        ctx.log.info("%s", result["message"])
        return result


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()

    @ctx.action("run_now")
    async def _run_now():
        return await _run(ctx, "手动")

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
    ctx.log.info("GPT-GOD 自动签到插件已停用")
