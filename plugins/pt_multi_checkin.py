"""多站点 PT 自动签到：平台 CloakBrowser + 平台/手动 Cookie。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import secrets
import threading
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
    "version": "1.1.0",
    "author": "AWdress",
    "description": "可持续扩展的多 PT 站自动签到助手，使用平台 CloakBrowser，支持平台或手动 Cookie。",
    "icon": "https://audiences.me/favicon.ico",
    "changelog": "v1.1.0 增加雷池兼容与 TJUPT 人工确认\n- PigGo 识别雷池 WAF 验证完成页并等待站内跳转\n- TJUPT 验证题调用平台 AI 识图并向 Telegram 推送候选按钮\n- 用户点击候选答案后在原浏览器会话提交，超时或页面变化时安全取消\n\nv1.0.3 按真实站点结果适配\n- 兼容 Audiences 与 OurBits 实际签到状态\n- Cookie、验证码和权限类错误不再无意义自动重试",
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
        "tjupt_ai_assist": {
            "type": "boolean", "default": True, "label": "TJUPT AI 识图辅助",
            "help": "把验证题截图、AI 建议和候选按钮推送给平台主人；由你点击答案后提交。",
            "section": "任务设置", "cols": 4, "order": 8,
        },
        "tjupt_confirm_timeout": {
            "type": "slider", "default": 300, "label": "TJUPT 等待确认（秒）",
            "min": 60, "max": 600, "step": 30, "section": "任务设置", "cols": 4, "order": 9,
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
            "default": "每个站点可独立选择 Cookie 来源。Cloudflare/雷池会等待正常验证。TJUPT 验证题可由平台 AI 给出建议，并推送 Telegram 候选按钮供主人确认。",
        },
    },
}


_run_lock: asyncio.Lock | None = None
_tasks: set[asyncio.Task] = set()
_HISTORY_KEY = "history"
_LAST_KEY = "last_result"
_tjupt_pending: dict[str, dict] = {}


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
        "非预期域名", "格式不正确", "bot 未连接", "主人 id",
        "等待 telegram", "签到选项", "验证题已变化",
    )
    return not any(marker in text for marker in permanent)


def _ai_available(ctx, capability: str) -> bool:
    checker = getattr(ctx.ai, "is_available", None)
    if callable(checker):
        return bool(checker(capability))
    return bool(getattr(ctx.ai, "available", False))


def _radio_label(item) -> str:
    """读取单选项可见文案，兼容 label[for]、包裹式 label 和表格布局。"""
    try:
        return str(item.evaluate("""el => {
            const direct = el.labels && el.labels.length ? el.labels[0].innerText : '';
            if (direct.trim()) return direct.trim();
            const wrapped = el.closest('label');
            if (wrapped && wrapped.innerText.trim()) return wrapped.innerText.trim();
            const cell = el.closest('td,li,div');
            return cell ? cell.innerText.trim() : (el.value || '');
        }""") or "").strip()
    except Exception:
        return str(item.get_attribute("value") or "").strip()


async def _send_tjupt_question(ctx, token: str, image_path: Path, options: list[str]) -> None:
    suggestion = "平台未配置视觉模型，请根据海报手动选择。"
    if ctx.config.get("tjupt_ai_assist", True) and _ai_available(ctx, "vision"):
        try:
            suggestion = str(await ctx.ai.vision(
                image=image_path.read_bytes(),
                prompt=(
                    "这是 TJUPT 的影视海报选择题。请观察图片，在下列候选项中给出最可能的一个，"
                    "同时简短说明依据和置信度。不要编造候选项。\n候选项：\n"
                    + "\n".join(f"{index + 1}. {label}" for index, label in enumerate(options))
                ),
                system="你是谨慎的影视海报识别助手。答案不确定时必须明确说明。",
            ) or "AI 未返回建议")
        except Exception as exc:  # noqa: BLE001
            ctx.log.warning("TJUPT AI 识图失败：%r", exc)
            suggestion = f"AI 识图失败：{exc.__class__.__name__}，请手动选择。"

    rows = []
    for index, label in enumerate(options):
        rows.append([{"text": f"{index + 1}. {label}"[:60], "callback_data": f"pttj:{token}:{index}"}])
    caption = (
        "🎬 TJUPT 签到验证\n\n"
        f"AI 建议：{suggestion[:700]}\n\n"
        "请核对海报后点击一个候选答案；插件只会提交你点击的选项。"
    )
    if not ctx.bot.connected or not ctx.owner_id:
        raise RuntimeError("平台 Bot 未连接或未配置主人 ID，无法发送 TJUPT 确认按钮")
    await ctx.bot.send_photo(ctx.owner_id, str(image_path), caption=caption, reply_markup={"inline_keyboard": rows})


def _tjupt_challenge(ctx, page, loop) -> dict:
    radios = page.locator('input[type="radio"]')
    count = min(radios.count(), 12)
    if count < 2:
        raise RuntimeError("识别到 TJUPT 签到验证，但没有解析到候选答案")
    options = [_radio_label(radios.nth(index)) or f"选项 {index + 1}" for index in range(count)]
    token = secrets.token_urlsafe(6)
    image_path = Path(ctx.data_dir) / f"tjupt_{token}.png"
    form = radios.first.locator("xpath=ancestor::form[1]")
    try:
        form.screenshot(path=str(image_path))
    except Exception:
        page.screenshot(path=str(image_path), full_page=True)

    event = threading.Event()
    pending = {"event": event, "choice": None, "created": datetime.now().timestamp()}
    _tjupt_pending[token] = pending
    timeout = _bounded(ctx.config.get("tjupt_confirm_timeout"), 300, 60, 600)
    try:
        future = asyncio.run_coroutine_threadsafe(_send_tjupt_question(ctx, token, image_path, options), loop)
        future.result(timeout=90)
        if not event.wait(timeout):
            raise RuntimeError(f"等待 Telegram 选择超时（{timeout} 秒），未提交签到答案")
        choice = pending.get("choice")
        if not isinstance(choice, int) or choice < 0 or choice >= count:
            raise RuntimeError("Telegram 返回的签到选项无效，未提交")
        current = page.locator('input[type="radio"]')
        if current.count() != count or [_radio_label(current.nth(i)) or f"选项 {i + 1}" for i in range(count)] != options:
            raise RuntimeError("TJUPT 验证题已变化，未提交旧答案")
        selected = current.nth(choice)
        selected.check()
        submit = form.locator('button[type="submit"], input[type="submit"], button').first
        if submit.count() < 1:
            raise RuntimeError("没有找到 TJUPT 验证题提交按钮")
        submit.click()
        page.wait_for_timeout(3_000)
        return _confirm_result(page)
    finally:
        _tjupt_pending.pop(token, None)
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass


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


def _browser_checkin(page, expected_domain: str, ctx=None, loop=None) -> dict:
    """在平台托管的同步 Playwright 页面内完成单站签到。"""
    page.set_default_timeout(20_000)
    for _ in range(60):
        title = (page.title() or "").lower()
        text = _page_text(page).lower()
        challenged = any(marker in f"{title}\n{text}" for marker in (
            "just a moment", "checking your browser", "cloudflare ray id", "cf-chl-",
            "请完成安全验证", "验证您是否是真人", "验证完成，即将进入网站",
            "雷池 waf", "安全检测能力由 雷池", "verification completed",
        ))
        if not challenged:
            break
        page.wait_for_timeout(3_000)
    else:
        raise RuntimeError("Cloudflare/雷池验证等待超时；若为交互式验证码需要人工处理")

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
        if expected_domain == "tjupt.org" and ctx is not None and loop is not None and "签到图片验证码" in captcha:
            return _tjupt_challenge(ctx, page, loop)
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
        loop = asyncio.get_running_loop()
        for key, site in enabled:
            cookie, error = await _site_cookie(ctx, key, site)
            if error:
                results.append({"site": site["name"], "ok": False, "status": "failed", "message": error})
                continue
            item = None
            for attempt in range(retries + 1):
                try:
                    def action(page, domain=site["domain"]):
                        return _browser_checkin(page, domain, ctx, loop)

                    outcome = await ctx.browser.run(
                        site["url"], action, cookies=cookie,
                        headless=bool(ctx.config.get("headless", True)),
                        timeout=720 if key == "tjupt" else (300 if key == "piggo" else 150),
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

    @ctx.on_callback(ctx.filters.regex(r"^pttj:"), target="bot", group=10)
    async def tjupt_choice(client, query):
        data = getattr(query, "data", "") or ""
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data).decode("utf-8", "replace")
        try:
            _, token, raw_choice = str(data).split(":", 2)
            choice = int(raw_choice)
        except (TypeError, ValueError):
            await query.answer("选项数据无效", show_alert=True)
            return
        if not getattr(query, "from_user", None) or int(query.from_user.id) != int(ctx.owner_id or 0):
            await query.answer("只有平台主人可以确认签到答案", show_alert=True)
            return
        pending = _tjupt_pending.get(token)
        if not pending or pending["event"].is_set():
            await query.answer("这道验证题已失效", show_alert=True)
            return
        pending["choice"] = choice
        pending["event"].set()
        await query.answer("已选择，正在原页面提交")

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
    for pending in list(_tjupt_pending.values()):
        pending["choice"] = None
        pending["event"].set()
    _tjupt_pending.clear()
    tasks = list(_tasks)
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()
