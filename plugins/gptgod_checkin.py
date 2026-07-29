"""GPT-GOD 自动签到：使用平台托管浏览器完成登录和网页签到。"""

from __future__ import annotations

import asyncio
from datetime import datetime


__plugin__ = {
    "name": "GPT-GOD 自动签到",
    "id": "gptgod_checkin",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "使用平台托管浏览器登录 GPT-GOD，每日自动领取签到积分，支持立即签到和结果通知。",
    "changelog": "v1.0.0 初始版本\n- 支持邮箱、密码登录 GPT-GOD\n- 使用网站原生页面流程完成动态校验和每日签到\n- 支持定时签到、立即签到、重复签到识别和结果通知",
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
    },
}


LOGIN_URL = "https://gptgod.online/login"
WELFARE_URL = "https://gptgod.online/token/welfare"
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


def _click_first_visible(page, selectors: tuple[str, ...]):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() == 1 and locator.is_visible(timeout=2_000):
                locator.click()
                return True
        except Exception:  # noqa: BLE001 - 尝试下一稳定选择器
            continue
    return False


def _browser_checkin(page, email: str, password: str) -> dict:
    """同步浏览器动作；由 ctx.browser.run 在线程中执行。"""
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    email_input = page.locator("#email")
    password_input = page.locator("#password")
    if email_input.count() != 1 or password_input.count() != 1:
        raise RuntimeError("未找到 GPT-GOD 登录表单，网站页面可能已更新")

    email_input.fill(email)
    password_input.fill(password)
    if not _click_first_visible(page, (
        'button:has-text("登 录")',
        'button:has-text("登录")',
        'button[type="submit"]',
    )):
        raise RuntimeError("未找到登录按钮，网站页面可能已更新")

    try:
        page.wait_for_url("**/session/**", timeout=30_000)
    except Exception:  # noqa: BLE001 - 下方读取页面给出具体失败原因
        pass

    login_text = _page_text(page)
    if "/login" in str(page.url):
        for marker in ("邮箱或密码错误", "密码错误", "登录失败", "账号不存在", "网络异常"):
            if marker in login_text:
                raise RuntimeError(marker)
        raise RuntimeError("登录后仍停留在登录页，请检查邮箱、密码或网站验证")

    page.goto(WELFARE_URL, wait_until="domcontentloaded")
    welfare_text = _page_text(page)
    if any(marker in welfare_text for marker in ("今天已签到", "今日已签到", "Already Checked In Today")):
        return {"status": "already", "message": "今天已经签到，无需重复领取"}

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
        return {"status": "success", "message": "签到成功，已领取每日积分"}
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
                    timeout=90,
                )
                status = str((browser_result or {}).get("status") or "")
                result = {
                    "ok": status in ("success", "already"),
                    "already": status == "already",
                    "message": str((browser_result or {}).get("message") or "签到完成"),
                }
            except Exception as exc:  # noqa: BLE001 - 转换成可读运行结果
                ctx.log.error("签到失败：%r", exc)
                result = {"ok": False, "message": f"签到失败：{exc}"}

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display = f"{stamp} · {result['message']}"
        ctx.update_config({"last_result": display})
        ctx.kv.set("last_result", {"time": stamp, **result})
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
