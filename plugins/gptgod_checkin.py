"""GPT-GOD 自动签到：使用平台托管浏览器完成登录和网页签到。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import re
import time


__plugin__ = {
    "name": "GPT-GOD 自动签到",
    "id": "gptgod_checkin",
    "version": "1.0.6",
    "author": "AWdress",
    "description": "使用平台托管浏览器登录 GPT-GOD，每日自动领取签到积分，支持立即签到和结果通知。",
    "changelog": "v1.0.5 修复网站受控登录表单\n- 邮箱和密码改为模拟真人逐键输入，触发网站内部表单状态更新\n- 按可见按钮实际文字精确匹配“登录”，避免点击同一区域内的其他按钮\n- 已使用平台 CloakBrowser 实测登录成功并取得会话 Cookie，未执行签到\n\nv1.0.4 修复已登录状态误判\n- 运行时优先访问免费积分页，已有有效登录态时直接签到，不再重复打开登录页\n- 登录提交后改用受保护积分页确认会话，不再仅凭 URL 仍含 /login 判定失败\n- 只有积分页确实退回登录表单时才提示检查账号或安全验证\n\nv1.0.3 增加积分记录\n- 每次签到完成后读取当前可用积分，并在通知中显示剩余积分\n- 配置页显示当前积分和最近 10 次签到记录\n- 持久保存最近 30 次签到结果，插件重载后记录不会消失\n\nv1.0.2 修复登录按钮识别\n- 兼容页面组件生成的登录按钮和同一页面存在多个隐藏按钮\n- 登录按钮无法点击时会尝试通过密码框提交，不再误报按钮不存在\n- 签到按钮同样会选择第一个可见按钮\n\nv1.0.1 修复登录页识别\n- 等待 GPT-GOD 单页应用完成登录表单渲染，避免页面刚打开就误报表单不存在\n- 兼容浏览器已有登录状态时直接跳转，跳过重复登录\n- 等待积分页签到控件加载，并细分 Cloudflare、登录和页面加载错误\n\nv1.0.0 初始版本\n- 支持邮箱、密码登录 GPT-GOD\n- 使用网站原生页面流程完成动态校验和每日签到\n- 支持定时签到、立即签到、重复签到识别和结果通知",
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

__plugin__["changelog"] = (
    "v1.0.6 修复切换账号后串号\n"
    "- 每次签到清理浏览器 Cookie 与本地会话并强制使用当前配置重新登录\n"
    "- 登录完成后核验网站显示邮箱与配置邮箱一致，不一致时停止签到并明确报错\n"
    "- 避免 Docker 浏览器残留旧会话，将旧账号的已签到状态误报给新账号\n\n"
    + __plugin__["changelog"]
)


LOGIN_URL = "https://gptgod.online/login"
WELFARE_URL = "https://gptgod.online/token/welfare"
POINTS_URL = "https://gptgod.online/token/rule"
HISTORY_KEY = "checkin_history"
HISTORY_LIMIT = 30
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


def _loading_error(page, area: str) -> RuntimeError:
    text = _page_text(page)
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
    page.goto(POINTS_URL, wait_until="domcontentloaded")
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


def _browser_checkin(page, email: str, password: str) -> dict:
    """同步浏览器动作；由 ctx.browser.run 在线程中执行。"""
    welfare_selectors = (
        'button:has-text("今天已签到")',
        'button:has-text("今日已签到")',
        'button:has-text("Already Checked In Today")',
        'button:has-text("签到领取")',
        'button:has-text("签到")',
        'button:has-text("Check-in")',
    )
    email_selectors = (
            "#email",
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="邮箱"]',
            'input[placeholder*="Email"]',
    )

    # Docker 浏览器内核可能残留旧站点会话。每次清理状态并使用当前配置
    # 重新登录，避免换号后沿用旧账号的“今天已签到”状态。
    try:
        page.context.clear_cookies()
    except Exception:  # noqa: BLE001 - 部分浏览器内核可能不暴露该方法
        pass
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    try:
        page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
        page.reload(wait_until="domcontentloaded")
    except Exception:  # noqa: BLE001 - 页面未使用本地存储时不影响登录
        pass

    email_input = _wait_for_any_visible(page, email_selectors, timeout_ms=33_000)
    if email_input is None:
        raise _loading_error(page, "登录页")
    password_input = _wait_for_any_visible(page, (
        "#password",
        'input[name="password"]',
        'input[type="password"]',
    ), timeout_ms=10_000)
    if password_input is None:
        raise _loading_error(page, "登录页密码框")
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

    try:
        page.wait_for_url("**/session/**", timeout=15_000)
    except Exception:  # noqa: BLE001 - 以受保护页面的实际访问结果为最终依据
        pass
    login_text = _page_text(page)
    for marker in ("邮箱或密码错误", "密码错误", "登录失败", "账号不存在", "网络异常"):
        if marker in login_text:
            raise RuntimeError(marker)

    page.goto(WELFARE_URL, wait_until="domcontentloaded")
    welfare_button = _wait_for_any_visible(page, welfare_selectors, timeout_ms=45_000)
    if welfare_button is None:
        login_input = _wait_for_any_visible(page, email_selectors, timeout_ms=2_000)
        if login_input is not None or "/login" in _current_url(page):
            raise RuntimeError("登录状态未生效，请检查邮箱、密码或网站安全验证")
        raise _loading_error(page, "免费积分页")

    welfare_text = _page_text(page)
    displayed_emails = {
        value.casefold()
        for value in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", welfare_text)
    }
    if displayed_emails and email.casefold() not in displayed_emails:
        raise RuntimeError("网站实际登录账号与插件当前配置邮箱不一致，已停止签到以防串号")
    if any(marker in welfare_text for marker in ("今天已签到", "今日已签到", "Already Checked In Today")):
        return _checkin_result(page, "already", "今天已经签到，无需重复领取")

    if not _click_first_visible(page, (
        'button:has-text("签到领取")',
        'button:has-text("签到")',
        'button:has-text("Check-in")',
    )):
        raise RuntimeError("未找到签到按钮，网站页面可能已更新")

    # 网站会先执行动态校验再调用签到接口；等待按钮状态或成功提示落地。
    try:
        page.locator(
            'button:has-text("今天已签到"), button:has-text("今日已签到"), '
            'button:has-text("Already Checked In Today")'
        ).wait_for(state="visible", timeout=30_000)
    except Exception:  # noqa: BLE001 - 重新载入积分页进行最终核验
        pass

    page.goto(WELFARE_URL, wait_until="domcontentloaded")
    result_text = _page_text(page)
    if any(marker in result_text for marker in ("今天已签到", "今日已签到", "Already Checked In Today")):
        return _checkin_result(page, "success", "签到成功，已领取每日积分")
    for marker in ("签到失败", "操作频繁", "请稍后", "验证失败", "网络异常"):
        if marker in result_text:
            raise RuntimeError(marker)
    raise RuntimeError("签到后未能确认成功状态，请稍后重试")


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
                browser_result = await ctx.browser.run(
                    LOGIN_URL,
                    lambda page: _browser_checkin(page, email, password),
                    headless=True,
                    timeout=180,
                )
                status = str((browser_result or {}).get("status") or "")
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
