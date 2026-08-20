"""多站点 PT 自动签到：平台 CloakBrowser + 平台同步 Cookie。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


__plugin__ = {
    "name": "PT站自动签到",
    "id": "pt_multi_checkin",
    "version": "2.5.0",
    "author": "AWdress",
    "description": "多 PT 站自动签到中心，统一使用平台 Cookie 与 CloakBrowser，提供 Vue 管理界面。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/pt_checkin_v2.svg",
    "changelog": "v2.5.0 修复 PigGo 会话 Cookie 轮换\n- PigGo 跳过 HTTP 预请求，直接使用 CloakBrowser，避免两个客户端争用旧会话\n- 签到成功后仅在内存中保留浏览器刷新的 PigGo Cookie，后续任务复用\n- Cookie 不写入配置、KV、磁盘或日志，平台重启后仍从 CookieCloud 读取\n\nv2.4.2 标记 PigGo 待适配",
    "scope": "standalone",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12"],
    "cookie_domains": [
        "audiences.me", "*.audiences.me", "ourbits.club", "*.ourbits.club",
        "hhanclub.net", "*.hhanclub.net",
        "piggo.me", "*.piggo.me", "tjupt.org", "*.tjupt.org", "52pt.site", "*.52pt.site",
        "pt.btschool.club", "*.pt.btschool.club", "ptchdbits.co", "*.ptchdbits.co",
        "haidan.video", "*.haidan.video", "club.hares.top", "*.club.hares.top",
        "hdarea.club", "*.hdarea.club", "hdchina.org", "*.hdchina.org",
        "hdcity.city", "*.hdcity.city", "hdsky.me", "*.hdsky.me",
        "pt.hdupt.com", "*.pt.hdupt.com", "m-team.cc", "*.m-team.cc",
        "v6.nexushd.org", "*.v6.nexushd.org", "open.cd", "*.open.cd",
        "pterclub.net", "*.pterclub.net", "pttime.org", "*.pttime.org",
        "totheglory.im", "*.totheglory.im", "u2.dmhy.org", "*.u2.dmhy.org",
        "yemapt.org", "*.yemapt.org", "zhuque.in", "*.zhuque.in",
    ],
    "default_enabled": False,
    "render_mode": "vue",
    "resources": {
        "timeout_seconds": 1800, "max_concurrency": 1, "max_background_tasks": 3,
        "failure_threshold": 3, "recovery_seconds": 120,
    },
}


SITES = {
    "audiences": {"name": "Audiences", "domain": "audiences.me", "url": "https://audiences.me/attendance.php", "group": "NexusPHP"},
    "ourbits": {"name": "OurBits", "domain": "ourbits.club", "url": "https://ourbits.club/attendance.php", "group": "NexusPHP"},
    "piggo": {"name": "PigGo", "domain": "piggo.me", "url": "https://piggo.me/attendance.php", "group": "NexusPHP", "status": "pending"},
    "hhan": {"name": "HHanClub", "domain": "hhanclub.net", "url": "https://hhanclub.net/attendance.php", "group": "NexusPHP"},
    "tjupt": {"name": "TJUPT", "domain": "tjupt.org", "url": "https://www.tjupt.org/attendance.php", "group": "交互验证"},
    "pt52": {"name": "52PT", "domain": "52pt.site", "url": "https://52pt.site/bakatest.php", "mode": "interactive", "group": "交互验证"},
    "btschool": {"name": "BT School", "domain": "pt.btschool.club", "url": "https://pt.btschool.club", "mode": "btschool", "group": "专用适配"},
    "chdbits": {"name": "CHDBits", "domain": "ptchdbits.co", "url": "https://ptchdbits.co/bakatest.php", "mode": "interactive", "group": "交互验证"},
    "haidan": {"name": "海胆", "domain": "haidan.video", "url": "https://www.haidan.video/signin.php", "mode": "haidan", "group": "专用适配"},
    "hares": {"name": "白兔", "domain": "club.hares.top", "url": "https://club.hares.top", "mode": "hares", "group": "专用适配"},
    "hdarea": {"name": "好大", "domain": "hdarea.club", "url": "https://www.hdarea.club", "mode": "hdarea", "group": "专用适配"},
    "hdchina": {"name": "HDChina", "domain": "hdchina.org", "url": "https://hdchina.org/index.php", "mode": "hdchina", "group": "专用适配"},
    "hdcity": {"name": "HDCity", "domain": "hdcity.city", "url": "https://hdcity.city/sign", "mode": "direct", "group": "专用适配"},
    "hdsky": {"name": "天空", "domain": "hdsky.me", "url": "https://hdsky.me", "mode": "interactive", "group": "交互验证"},
    "hdupt": {"name": "HDU PT", "domain": "pt.hdupt.com", "url": "https://pt.hdupt.com", "mode": "hdupt", "group": "专用适配"},
    "mteam": {"name": "M-Team", "domain": "kp.m-team.cc", "url": "https://kp.m-team.cc", "mode": "visit", "group": "专用适配"},
    "nexushd": {"name": "NexusHD", "domain": "v6.nexushd.org", "url": "https://v6.nexushd.org", "mode": "nexushd", "group": "专用适配"},
    "opencd": {"name": "OpenCD", "domain": "open.cd", "url": "https://www.open.cd", "mode": "interactive", "group": "交互验证"},
    "pterclub": {"name": "PTerClub", "domain": "pterclub.net", "url": "https://pterclub.net/attendance-ajax.php", "mode": "pterclub", "group": "专用适配"},
    "pttime": {"name": "PTTime", "domain": "pttime.org", "url": "https://www.pttime.org/attendance.php", "mode": "pttime", "group": "专用适配"},
    "ttg": {"name": "TTG", "domain": "totheglory.im", "url": "https://totheglory.im", "mode": "ttg", "group": "专用适配"},
    "u2": {"name": "U2", "domain": "u2.dmhy.org", "url": "https://u2.dmhy.org/showup.php", "mode": "interactive", "group": "交互验证"},
    "yema": {"name": "YemaPT", "domain": "yemapt.org", "url": "https://yemapt.org/api/consumer/checkIn", "mode": "yema", "group": "专用适配"},
    "zhuque": {"name": "朱雀", "domain": "zhuque.in", "url": "https://zhuque.in", "mode": "zhuque", "group": "专用适配"},
}


DEFAULTS = {
    "auto_checkin": True, "notify_result": True, "headless": True,
    "checkin_hour": 8, "checkin_minute": 10, "retry_count": 2, "retry_interval": 20,
    "tjupt_ai_assist": True, "tjupt_confirm_timeout": 300,
    "selected_sites": list(SITES.keys()),
}


_run_lock: asyncio.Lock | None = None
_tasks: set[asyncio.Task] = set()
_HISTORY_KEY = "history"
_LAST_KEY = "last_result"
_tjupt_pending: dict[str, dict] = {}
_browser_cookie_cache: dict[str, str] = {}
_state = {"running": False, "started_at": "", "finished_at": "", "current": "", "phase": "", "message": "", "completed": 0, "total": 0}


def _cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _task_done(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if task.cancelled():
        _state.update({"running": False, "phase": "已取消", "message": "签到任务已取消", "current": ""})
        return
    try:
        error = task.exception()
    except Exception as exc:  # noqa: BLE001
        error = exc
    if error:
        _state.update({"running": False, "phase": "异常", "message": f"后台任务异常：{error}", "current": ""})


def _bounded(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


async def _site_cookie(ctx, key: str, site: dict) -> tuple[str, str]:
    if not ctx.cookies.available:
        return "", "平台 Cookie 同步未启用"
    parsed = urlparse(site["url"])
    path = parsed.path or "/"
    domain = site["domain"].lower()
    url_host = (parsed.hostname or domain).lower()
    hosts = list(dict.fromkeys((url_host, domain, domain[4:] if domain.startswith("www.") else f"www.{domain}")))
    last_error = ""
    for host in hosts:
        try:
            cookie = await ctx.cookies.header(host, path=path)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        if cookie:
            return cookie, ""
    for host in hosts:
        try:
            await ctx.cookies.request_sync(host)
        except Exception:
            continue
    for host in hosts:
        try:
            cookie = await ctx.cookies.header(host, path=path)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        if cookie:
            return cookie, ""
    if last_error:
        return "", f"读取平台 Cookie 失败：{last_error}"
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


def _nexus_result_state(text: str) -> tuple[str, str] | None:
    """NexusPHP 签到回执不一定包含“签到成功”。"""
    state = _result_state(text)
    if state:
        return state
    compact = re.sub(r"\s+", "", text or "").lower()
    if any(marker in compact for marker in (
        "今日已经签到过", "今天已经签到过", "今日不能重复签到", "请勿重复签到",
    )):
        return "already", "今天已经签到"
    if any(marker in compact for marker in (
        "本次签到获得", "此次签到获得", "签到所得", "已连续签到",
    )) or re.search(r"(?:这是您的(?:首次|第\d+次)签到|连续签到\d+天|获得(?:了)?[\d,.]+个?魔力)", compact):
        return "success", "签到成功"
    return None


def _site_result_state(text: str, expected_domain: str = "") -> tuple[str, str] | None:
    if expected_domain.lower() in {"piggo.me", "hhanclub.net"}:
        return _nexus_result_state(text)
    return _result_state(text)


def _same_site_domain(current: str, expected: str) -> bool:
    """www 与根域视为同一站点，不放宽到其他子域。"""
    return current.lower().removeprefix("www.") == expected.lower().removeprefix("www.")


def _refreshed_cookie_header(page, expected_domain: str) -> str:
    """读取浏览器刷新后的同站 Cookie；调用方只允许保存在进程内。"""
    expected = expected_domain.lower().lstrip(".").removeprefix("www.")
    try:
        cookies = page.context.cookies()
    except Exception:
        return ""
    pairs = []
    for item in cookies or []:
        domain = str(item.get("domain") or "").lower().lstrip(".").removeprefix("www.")
        name = str(item.get("name") or "")
        if domain == expected and name:
            pairs.append(f"{name}={item.get('value', '')}")
    return "; ".join(pairs)


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


def _confirm_result(page, *, attempts: int = 3, expected_domain: str = "") -> dict:
    """刷新确认服务端状态；绝不为确认结果而再次点击签到按钮。"""
    for attempt in range(attempts):
        text = _page_text(page)
        captcha = _captcha_error(text)
        if captcha:
            raise RuntimeError(captcha)
        state = _site_result_state(text, expected_domain)
        if state:
            status, message = state
            if status == "failed":
                raise RuntimeError(message)
            return {"status": status, "message": message}
        if attempt + 1 < attempts:
            page.wait_for_timeout(2_000 * (attempt + 1))
            page.reload(wait_until="domcontentloaded", timeout=60_000)
    # PigGo 的 attendance.php 在 Cloudflare 之后可能只剩页脚；真实签到状态在首顶导航。
    if expected_domain.lower() == "piggo.me":
        page.goto("https://piggo.me/", wait_until="domcontentloaded", timeout=60_000)
        for _ in range(15):
            home_text = _page_text(page)
            state = _nexus_result_state(home_text)
            if state:
                status, message = state
                if status == "failed":
                    raise RuntimeError(message)
                signed_badge = bool(re.search(r"签到\s*已得\s*[\d,.]+", home_text))
                return {"status": "already" if signed_badge else status, "message": "今天已经签到" if signed_badge else message}
            page.wait_for_timeout(1_000)
    path = urlparse(page.url).path or "/"
    controls = page.locator('a, button, input[type="submit"], input[type="button"]')
    labels: list[str] = []
    for index in range(min(controls.count(), 30)):
        try:
            item = controls.nth(index)
            label = (item.inner_text() or item.get_attribute("value") or item.get_attribute("aria-label") or "").strip()
            label = re.sub(r"\s+", " ", label)[:24]
            if label and label not in labels:
                labels.append(label)
        except Exception:
            continue
    summary = "、".join(labels[:5]) or "无可见操作控件"
    raise RuntimeError(f"签到后未识别到结果（页面 {path}；控件：{summary}）")


def _fetch_same_origin(page, url: str, *, method: str = "GET", data: dict | None = None,
                       json_data: dict | None = None, headers: dict | None = None) -> dict:
    return page.evaluate("""async payload => {
        const options = {method: payload.method, credentials: 'include', headers: payload.headers || {}};
        if (payload.jsonData !== null) {
            options.headers['Content-Type'] = 'application/json; charset=utf-8';
            options.body = JSON.stringify(payload.jsonData);
        } else if (payload.data !== null) {
            options.headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
            options.body = new URLSearchParams(payload.data).toString();
        }
        const response = await fetch(payload.url, options);
        return {status: response.status, text: await response.text(), url: response.url};
    }""", {"url": url, "method": method, "data": data, "jsonData": json_data, "headers": headers or {}})


def _response_result(text: str, *, success: tuple[str, ...], already: tuple[str, ...] = ()) -> dict:
    low = (text or "").lower()
    if any(marker.lower() in low for marker in already):
        return {"status": "already", "message": "今天已经签到"}
    if any(marker.lower() in low for marker in success):
        return {"status": "success", "message": "签到成功"}
    raise RuntimeError("签到接口返回未识别结果，未计为成功")


def _ai_call(ctx, loop, capability: str, *, prompt: str, image: bytes | None = None) -> str:
    if not _ai_available(ctx, capability):
        raise RuntimeError(f"平台未配置可用的 AI {capability} 能力，无法自动识别签到验证")
    if capability == "vision":
        coro = ctx.ai.vision(image=image, prompt=prompt, system="你是谨慎的验证码识别器，只输出请求的答案，不要解释。")
    else:
        coro = ctx.ai.chat(prompt=prompt, system="你是谨慎的 PT 签到答题助手，只输出答案编号，不要解释。", temperature=0)
    try:
        return str(asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=90) or "").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"AI 识别失败：{exc}") from exc


def _ai_choice(ctx, loop, question: str, options: list[str]) -> int:
    answer = _ai_call(ctx, loop, "text", prompt=(
        "请回答下面的单选题。只输出正确选项编号（从 1 开始）；不确定就输出 0。\n"
        f"问题：{question}\n" + "\n".join(f"{i + 1}. {text}" for i, text in enumerate(options))
    ))
    match = re.search(r"(?<!\d)(\d+)(?!\d)", answer)
    index = int(match.group(1)) - 1 if match else -1
    if index < 0 or index >= len(options):
        raise RuntimeError("AI 未给出可靠的有效选项，未提交签到答案")
    return index


def _ai_ocr(ctx, loop, image: bytes, length: int = 6) -> str:
    answer = _ai_call(ctx, loop, "vision", image=image, prompt=(
        f"读取图片中的 {length} 位验证码。只输出验证码本身；无法确认时输出 UNKNOWN。"
    ))
    if "UNKNOWN" in answer.upper():
        raise RuntimeError("AI 未能可靠识别验证码，未提交签到")
    candidates = re.findall(rf"(?<![A-Za-z0-9])[A-Za-z0-9]{{{length}}}(?![A-Za-z0-9])", answer)
    if not candidates:
        raise RuntimeError("AI 未能可靠识别验证码，未提交签到")
    return candidates[0]


def _quiz_checkin(page, site: dict, ctx, loop) -> dict:
    text = _page_text(page)
    if "今天已经签过到了" in text:
        return {"status": "already", "message": "今天已经签到"}
    question_id = page.locator('input[name="questionid"]').get_attribute("value")
    choices = page.locator('input[name="choice[]"]')
    if not question_id or choices.count() < 2:
        raise RuntimeError("未解析到签到问题或候选答案")
    question = text.split("请问：", 1)[1].splitlines()[0].strip() if "请问：" in text else text[:500]
    options = [_radio_label(choices.nth(i)) or str(choices.nth(i).get_attribute("value") or "") for i in range(choices.count())]
    selected = choices.nth(_ai_choice(ctx, loop, question, options)).get_attribute("value")
    result = _fetch_same_origin(page, site["url"], method="POST", data={
        "questionid": question_id, "choice[]": selected, "usercomment": "自动签到", "wantskip": "不会",
    })
    return _response_result(result.get("text", ""), success=("点魔力值",), already=("今天已经签过到了",))


def _special_checkin(page, key: str, site: dict, ctx, loop) -> dict:
    current_domain = (urlparse(page.url).hostname or "").lower()
    expected = site["domain"].lower()
    if not _same_site_domain(current_domain, expected):
        raise RuntimeError(f"站点跳转到了非预期域名：{current_domain or '未知'}")
    text = _page_text(page)
    low = text.lower()
    html = page.content()
    if "login.php" in low or "takelogin.php" in low or 'name="username"' in html.lower():
        raise RuntimeError("Cookie 已失效，网站返回登录页")
    mode = site.get("mode")
    if mode == "interactive":
        state = _result_state(text)
        if state and state[0] != "failed":
            return {"status": state[0], "message": state[1]}
        if key in {"pt52", "chdbits"}:
            return _quiz_checkin(page, site, ctx, loop)
        if key == "hdsky":
            code_response = _fetch_same_origin(page, "https://hdsky.me/image_code_ajax.php", method="POST", data={"action": "new"})
            try:
                image_hash = json.loads(code_response.get("text", "")).get("code")
            except (TypeError, ValueError):
                image_hash = None
            if not image_hash:
                raise RuntimeError("天空未返回有效验证码参数")
            page.goto(f"https://hdsky.me/image.php?action=regimage&imagehash={image_hash}", wait_until="load", timeout=60_000)
            captcha = _ai_ocr(ctx, loop, page.screenshot(), 6)
            result = _fetch_same_origin(page, "https://hdsky.me/showup.php", method="POST", data={"action": "showup", "imagehash": image_hash, "imagestring": captcha})
            body = result.get("text", "")
            return _response_result(body, success=('"success":true', '"success": true'), already=("date_unmatch",))
        if key == "opencd":
            if "/plugin_sign-in.php?cmd=show-log" in html:
                return {"status": "already", "message": "今天已经签到"}
            page.goto("https://www.open.cd/plugin_sign-in.php", wait_until="domcontentloaded", timeout=60_000)
            form = page.locator("#frmSignin")
            image = form.locator("img").first
            image_hash = form.locator('input[name="imagehash"]').get_attribute("value")
            if not image_hash or image.count() < 1:
                raise RuntimeError("OpenCD 未解析到验证码参数")
            captcha = _ai_ocr(ctx, loop, image.screenshot(), 6)
            result = _fetch_same_origin(page, "https://www.open.cd/plugin_sign-in.php?cmd=signin", method="POST", data={"imagehash": image_hash, "imagestring": captcha})
            return _response_result(result.get("text", ""), success=('"state":"success"', '"state":true'), already=("已签到",))
        if key == "u2":
            if datetime.now().hour < 9:
                raise RuntimeError("U2 站点规则要求 09:00 后签到")
            form = page.locator("form").filter(has=page.locator('input[name="req"]')).first
            req = form.locator('input[name="req"]').get_attribute("value")
            hash_value = form.locator('input[name="hash"]').get_attribute("value")
            form_value = form.locator('input[name="form"]').get_attribute("value")
            submits = form.locator('input[type="submit"]')
            if not req or not hash_value or not form_value or submits.count() < 1:
                raise RuntimeError("U2 未解析到签到表单")
            submit = submits.nth(secrets.randbelow(submits.count()))
            result = _fetch_same_origin(page, "https://u2.dmhy.org/showup.php?action=show", method="POST", data={
                "req": req, "hash": hash_value, "form": form_value, "message": "自动签到",
                str(submit.get_attribute("name")): str(submit.get_attribute("value")),
            })
            body = result.get("text", "")
            if re.search(r"window\.location\.href\s*=\s*['\"]showup\.php['\"]", body, re.IGNORECASE):
                return {"status": "success", "message": "签到成功"}
            page.goto("https://u2.dmhy.org/showup.php", wait_until="domcontentloaded", timeout=60_000)
            confirmed = page.content()
            if re.search(r'<a[^>]+href=["\']showup\.php["\'][^>]*>\s*(?:已签到|Show Up|Показать|已簽到)\s*</a>', confirmed, re.IGNORECASE):
                return {"status": "success", "message": "签到成功"}
            raise RuntimeError("U2 签到提交后仍未确认已签到")
        raise RuntimeError("暂不支持该站点的自动验证")
    if mode == "visit":
        return {"status": "success", "message": "模拟访问成功，已刷新最后访问时间"}
    if mode == "direct":
        return _response_result(text, success=("签到成功", "本次签到获得魅力"), already=("已签到", "已经签到"))
    if mode == "pttime":
        return _response_result(text, success=("签到成功",), already=("今日已签到", "今天已签到"))
    if mode == "btschool":
        if "每日签到" not in text:
            return {"status": "already", "message": "今天已经签到"}
        page.goto("https://pt.btschool.club/index.php?action=addbonus", wait_until="domcontentloaded", timeout=60_000)
        if "每日签到" not in _page_text(page):
            return {"status": "success", "message": "签到成功"}
        raise RuntimeError("签到入口仍然存在")
    if mode == "haidan":
        page.goto("https://www.haidan.video/index.php", wait_until="domcontentloaded", timeout=60_000)
        return _response_result(page.content(), success=("已经打卡",), already=())
    if mode == "hares":
        result = _fetch_same_origin(page, "https://club.hares.top/attendance.php?action=sign")
        return _response_result(result.get("text", ""), success=('"code":0', "签到成功"), already=('"code":1', "已经签到过"))
    if mode == "hdarea":
        result = _fetch_same_origin(page, "https://www.hdarea.club/sign_in.php", method="POST", data={"action": "sign_in"})
        return _response_result(result.get("text", ""), success=("此次签到您获得",), already=("请不要重复签到",))
    if mode == "hdchina":
        csrf = page.locator('meta[name="x-csrf"]').get_attribute("content")
        if not csrf:
            if "已签到" in text:
                return {"status": "already", "message": "今天已经签到"}
            raise RuntimeError("未获取到 HDChina CSRF 参数")
        result = _fetch_same_origin(page, "https://hdchina.org/plugin_sign-in.php?cmd=signin", method="POST", data={"csrf": csrf})
        return _response_result(result.get("text", ""), success=('"state":"success"', '"state":true'), already=("已签到",))
    if mode == "hdupt":
        if "yiqiandao" in html:
            return {"status": "already", "message": "今天已经签到"}
        page.goto("https://pt.hdupt.com/added.php?action=qiandao", wait_until="domcontentloaded", timeout=60_000)
        if any(ch.isdigit() for ch in _page_text(page)):
            return {"status": "success", "message": "签到成功"}
        raise RuntimeError("HDU PT 签到接口返回异常")
    if mode == "nexushd":
        result = _fetch_same_origin(page, "https://v6.nexushd.org/signin.php", method="POST", data={"action": "post", "content": ""})
        return _response_result(result.get("text", ""), success=("本次签到获得",), already=("你今天已经签到过了",))
    if mode == "pterclub":
        return _response_result(text, success=('"status":"1"', "签到已成功"), already=('"status":"0"', "已经签到过"))
    if mode == "ttg":
        if "已签到" in text:
            return {"status": "already", "message": "今天已经签到"}
        timestamp = re.search(r'signed_timestamp:\s*["\'](\d{10})', html)
        token = re.search(r'signed_token:\s*["\']([^"\']+)', html)
        if not timestamp or not token:
            raise RuntimeError("未获取到 TTG 签到参数")
        result = _fetch_same_origin(page, "https://totheglory.im/signed.php", method="POST", data={"signed_timestamp": timestamp.group(1), "signed_token": token.group(1)})
        return _response_result(result.get("text", ""), success=("您已连续签到",), already=("今天已签到过",))
    if mode == "yema":
        return _response_result(text, success=('"success":true', '"success": true'), already=("already", "已签到"))
    if mode == "zhuque":
        csrf = page.locator('meta[name="x-csrf-token"]').get_attribute("content")
        if not csrf:
            raise RuntimeError("未获取到朱雀 CSRF 参数")
        result = _fetch_same_origin(page, "https://zhuque.in/api/gaming/fireGenshinCharacterMagic", method="POST", json_data={"all": 1, "resetModal": "true"}, headers={"x-csrf-token": csrf})
        return _response_result(result.get("text", ""), success=("FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS", '"status":200'), already=("already",))
    return _browser_checkin(page, site["domain"], ctx, loop)


def _browser_checkin(page, expected_domain: str, ctx=None, loop=None) -> dict:
    """在平台托管的同步 Playwright 页面内完成单站签到。"""
    page.set_default_timeout(20_000)
    challenge_reload_done = False
    for challenge_round in range(100):
        title = (page.title() or "").lower()
        text = _page_text(page).lower()
        challenged = any(marker in f"{title}\n{text}" for marker in (
            "just a moment", "checking your browser", "cloudflare ray id", "cf-chl-",
            "请完成安全验证", "验证您是否是真人", "验证完成，即将进入网站",
            "雷池 waf", "安全检测能力由 雷池", "verification completed",
        ))
        if not challenged:
            break
        # 雷池偶尔已下发通行 Cookie 但前端未完成跳转，受控重载可恢复。
        if not challenge_reload_done and challenge_round >= 10 and any(marker in f"{title}\n{text}" for marker in (
            "验证完成，即将进入网站", "verification completed",
        )):
            page.reload(wait_until="domcontentloaded", timeout=60_000)
            challenge_reload_done = True
            continue
        page.wait_for_timeout(3_000)
    else:
        raise RuntimeError("Cloudflare/雷池验证等待超时；若为交互式验证码需要人工处理")

    current_domain = (urlparse(page.url).hostname or "").lower()
    if not _same_site_domain(current_domain, expected_domain):
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
    initial_state = _site_result_state(text, expected_domain)
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
            return _confirm_result(page, expected_domain=expected_domain)
        except RuntimeError:
            raise
        except Exception:
            continue

    # 标准 NexusPHP attendance.php 通常由 GET 完成签到；刷新后必须出现明确结果。
    if urlparse(page.url).path.lower().endswith("/attendance.php"):
        return _confirm_result(page, expected_domain=expected_domain)
    raise RuntimeError("没有识别到签到页面或签到按钮，网站结构可能已更新")


class _NeedsBrowser(RuntimeError):
    """HTTP 页面需要浏览器执行挑战或动态脚本。"""


def _http_guard(response: httpx.Response) -> str:
    text = response.text or ""
    low = text.lower()
    if response.status_code in {403, 429, 468, 503, 521, 522, 525} or any(marker in low for marker in (
        "cf-chl-", "cloudflare ray id", "just a moment", "checking your browser",
        "turnstile", "雷池 waf", "安全检测能力由 雷池", "验证您是否是真人",
        "verification completed", "challenge-platform",
    )):
        raise _NeedsBrowser(f"HTTP 命中安全验证（{response.status_code}），切换 CloakBrowser")
    if any(marker in low for marker in ('name="username"', "name='username'", "takelogin.php")) or response.url.path.lower().endswith(("/login.php", "/takelogin.php")):
        raise RuntimeError("Cookie 已失效，网站返回登录页")
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP 请求失败：{response.status_code}")
    return text


async def _http_ai_choice(ctx, question: str, options: list[str]) -> int:
    if not _ai_available(ctx, "text"):
        raise RuntimeError("平台未配置可用的 AI 文字模型，无法回答签到题")
    answer = str(await ctx.ai.chat(
        prompt="请回答下面的单选题。只输出正确选项编号（从 1 开始）；不确定就输出 0。\n"
               f"问题：{question}\n" + "\n".join(f"{i + 1}. {item}" for i, item in enumerate(options)),
        system="你是谨慎的 PT 签到答题助手，只输出答案编号，不要解释。", temperature=0,
    ) or "").strip()
    match = re.search(r"(?<!\d)(\d+)(?!\d)", answer)
    index = int(match.group(1)) - 1 if match else -1
    if index < 0 or index >= len(options):
        raise RuntimeError("AI 未给出可靠的有效选项，未提交签到答案")
    return index


async def _http_ai_ocr(ctx, image: bytes, length: int = 6) -> str:
    if not _ai_available(ctx, "vision"):
        raise RuntimeError("平台未配置视觉模型，无法识别签到验证码")
    answer = str(await ctx.ai.vision(
        image=image, prompt=f"读取图片中的 {length} 位验证码。只输出验证码本身；无法确认时输出 UNKNOWN。",
        system="你是谨慎的验证码识别器，只输出请求的答案，不要解释。",
    ) or "").strip()
    if "UNKNOWN" in answer.upper():
        raise RuntimeError("AI 未能可靠识别验证码，未提交签到")
    matches = re.findall(rf"(?<![A-Za-z0-9])[A-Za-z0-9]{{{length}}}(?![A-Za-z0-9])", answer)
    if not matches:
        raise RuntimeError("AI 未能可靠识别验证码，未提交签到")
    return matches[0]


def _soup_value(soup: BeautifulSoup, name: str) -> str:
    node = soup.select_one(f'input[name="{name}"]')
    return str(node.get("value") or "") if node else ""


async def _http_checkin(ctx, key: str, site: dict, cookie: str) -> dict:
    """轻量签到；只有安全挑战或必须执行动态脚本时才请求浏览器降级。"""
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    timeout = httpx.Timeout(35.0, connect=12.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        async def get(url: str) -> tuple[httpx.Response, str]:
            response = await client.get(url)
            return response, _http_guard(response)

        async def post(url: str, *, data=None, json_data=None, extra_headers=None) -> tuple[httpx.Response, str]:
            response = await client.post(url, data=data, json=json_data, headers=extra_headers)
            return response, _http_guard(response)

        mode = site.get("mode")
        response, text = await get(site["url"])
        state = _result_state(text)
        if state and state[0] != "failed":
            return {"status": state[0], "message": state[1], "engine": "http"}

        if key in {"audiences", "ourbits", "piggo", "hhan"}:
            # 标准 attendance.php 通常 GET 即完成；未知页面交给浏览器识别动态按钮。
            if state and state[0] == "failed":
                raise RuntimeError(state[1])
            raise _NeedsBrowser("HTTP 页面没有明确签到结果，切换 CloakBrowser 确认")

        if mode == "visit":
            return {"status": "success", "message": "轻量访问成功，已刷新最后访问时间", "engine": "http"}
        if mode == "direct":
            result = _response_result(text, success=("签到成功", "本次签到获得魅力"), already=("已签到", "已经签到"))
            return {**result, "engine": "http"}
        if mode == "pttime":
            try:
                result = _response_result(text, success=("签到成功",), already=("今日已签到", "今天已签到"))
            except RuntimeError as exc:
                raise _NeedsBrowser("PTTime HTTP 回执未识别，切换 CloakBrowser 确认") from exc
            return {**result, "engine": "http"}
        if mode == "btschool":
            if "每日签到" not in text:
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            _, body = await get("https://pt.btschool.club/index.php?action=addbonus")
            if "每日签到" not in body:
                return {"status": "success", "message": "签到成功", "engine": "http"}
            raise RuntimeError("签到入口仍然存在")
        if mode == "haidan":
            _, body = await get("https://www.haidan.video/index.php")
            return {**_response_result(body, success=("已经打卡",)), "engine": "http"}
        if mode == "hares":
            _, body = await get("https://club.hares.top/attendance.php?action=sign")
            return {**_response_result(body, success=('"code":0', "签到成功"), already=('"code":1', "已经签到过")), "engine": "http"}
        if mode == "hdarea":
            _, body = await post("https://www.hdarea.club/sign_in.php", data={"action": "sign_in"})
            return {**_response_result(body, success=("此次签到您获得",), already=("请不要重复签到",)), "engine": "http"}
        if mode == "hdchina":
            soup = BeautifulSoup(text, "html.parser")
            csrf_node = soup.select_one('meta[name="x-csrf"]')
            csrf = str(csrf_node.get("content") or "") if csrf_node else ""
            if not csrf:
                raise _NeedsBrowser("HTTP 未取得 HDChina CSRF，切换 CloakBrowser")
            _, body = await post("https://hdchina.org/plugin_sign-in.php?cmd=signin", data={"csrf": csrf})
            return {**_response_result(body, success=('"state":"success"', '"state":true'), already=("已签到",)), "engine": "http"}
        if mode == "hdupt":
            if "yiqiandao" in text:
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            _, body = await get("https://pt.hdupt.com/added.php?action=qiandao")
            if any(char.isdigit() for char in BeautifulSoup(body, "html.parser").get_text(" ")):
                return {"status": "success", "message": "签到成功", "engine": "http"}
            raise RuntimeError("HDU PT 签到接口返回异常")
        if mode == "nexushd":
            _, body = await post("https://v6.nexushd.org/signin.php", data={"action": "post", "content": ""})
            return {**_response_result(body, success=("本次签到获得",), already=("你今天已经签到过了",)), "engine": "http"}
        if mode == "pterclub":
            return {**_response_result(text, success=('"status":"1"', "签到已成功"), already=('"status":"0"', "已经签到过")), "engine": "http"}
        if mode == "ttg":
            if "已签到" in text:
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            timestamp = re.search(r'signed_timestamp:\s*["\'](\d{10})', text)
            token = re.search(r'signed_token:\s*["\']([^"\']+)', text)
            if not timestamp or not token:
                raise _NeedsBrowser("HTTP 未取得 TTG 动态参数，切换 CloakBrowser")
            _, body = await post("https://totheglory.im/signed.php", data={"signed_timestamp": timestamp.group(1), "signed_token": token.group(1)})
            return {**_response_result(body, success=("您已连续签到",), already=("今天已签到过",)), "engine": "http"}
        if mode == "yema":
            return {**_response_result(text, success=('"success":true', '"success": true'), already=("already", "已签到")), "engine": "http"}
        if mode == "zhuque":
            soup = BeautifulSoup(text, "html.parser")
            csrf_node = soup.select_one('meta[name="x-csrf-token"]')
            csrf = str(csrf_node.get("content") or "") if csrf_node else ""
            if not csrf:
                raise _NeedsBrowser("HTTP 未取得朱雀 CSRF，切换 CloakBrowser")
            _, body = await post("https://zhuque.in/api/gaming/fireGenshinCharacterMagic", json_data={"all": 1, "resetModal": "true"}, extra_headers={"x-csrf-token": csrf})
            return {**_response_result(body, success=("FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS", '"status":200'), already=("already",)), "engine": "http"}
        if key in {"pt52", "chdbits"}:
            if "今天已经签过到了" in text:
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            soup = BeautifulSoup(text, "html.parser")
            question_id = _soup_value(soup, "questionid")
            nodes = soup.select('input[name="choice[]"]')
            if not question_id or len(nodes) < 2:
                raise _NeedsBrowser("HTTP 未解析到签到题，切换 CloakBrowser")
            question = soup.get_text(" ", strip=True).split("请问：", 1)[-1][:500]
            options = []
            for node in nodes:
                label = soup.select_one(f'label[for="{node.get("id", "")}"]') if node.get("id") else None
                options.append(label.get_text(" ", strip=True) if label else str(node.parent.get_text(" ", strip=True) or node.get("value") or ""))
            selected = str(nodes[await _http_ai_choice(ctx, question, options)].get("value") or "")
            _, body = await post(site["url"], data={"questionid": question_id, "choice[]": selected, "usercomment": "自动签到", "wantskip": "不会"})
            return {**_response_result(body, success=("点魔力值",), already=("今天已经签过到了",)), "engine": "http"}
        if key == "hdsky":
            _, code_body = await post("https://hdsky.me/image_code_ajax.php", data={"action": "new"})
            try:
                image_hash = json.loads(code_body).get("code")
            except (TypeError, ValueError):
                image_hash = None
            if not image_hash:
                raise _NeedsBrowser("HTTP 未取得天空验证码，切换 CloakBrowser")
            image_response = await client.get(f"https://hdsky.me/image.php?action=regimage&imagehash={image_hash}")
            if image_response.status_code >= 400:
                raise RuntimeError(f"下载天空验证码失败：{image_response.status_code}")
            captcha = await _http_ai_ocr(ctx, image_response.content)
            _, body = await post("https://hdsky.me/showup.php", data={"action": "showup", "imagehash": image_hash, "imagestring": captcha})
            return {**_response_result(body, success=('"success":true', '"success": true'), already=("date_unmatch",)), "engine": "http"}
        if key == "opencd":
            if "/plugin_sign-in.php?cmd=show-log" in text:
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            _, form_body = await get("https://www.open.cd/plugin_sign-in.php")
            soup = BeautifulSoup(form_body, "html.parser")
            form = soup.select_one("#frmSignin")
            image_node = form.select_one("img") if form else None
            hash_node = form.select_one('input[name="imagehash"]') if form else None
            if not image_node or not hash_node:
                raise _NeedsBrowser("HTTP 未解析到 OpenCD 验证码，切换 CloakBrowser")
            image_url = str(response.url.join(str(image_node.get("src") or "")))
            image_response = await client.get(image_url)
            captcha = await _http_ai_ocr(ctx, image_response.content)
            _, body = await post("https://www.open.cd/plugin_sign-in.php?cmd=signin", data={"imagehash": hash_node.get("value"), "imagestring": captcha})
            return {**_response_result(body, success=('"state":"success"', '"state":true'), already=("已签到",)), "engine": "http"}
        if key == "u2":
            if datetime.now().hour < 9:
                raise RuntimeError("U2 站点规则要求 09:00 后签到")
            soup = BeautifulSoup(text, "html.parser")
            req, hash_value, form_value = (_soup_value(soup, name) for name in ("req", "hash", "form"))
            submits = soup.select('input[type="submit"][name]')
            if not req or not hash_value or not form_value or not submits:
                raise _NeedsBrowser("HTTP 未解析到 U2 签到表单，切换 CloakBrowser")
            if re.search(r'<a[^>]+href=["\']showup\.php["\'][^>]*>\s*(?:已签到|Show Up|Показать|已簽到)\s*</a>', text, re.IGNORECASE):
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            submit = submits[secrets.randbelow(len(submits))]
            _, body = await post("https://u2.dmhy.org/showup.php?action=show", data={"req": req, "hash": hash_value, "form": form_value, "message": "自动签到", submit.get("name"): submit.get("value")})
            if re.search(r"window\.location\.href\s*=\s*['\"]showup\.php['\"]", body, re.IGNORECASE):
                return {"status": "success", "message": "签到成功", "engine": "http"}
            _, confirmed = await get("https://u2.dmhy.org/showup.php")
            if re.search(r'<a[^>]+href=["\']showup\.php["\'][^>]*>\s*(?:已签到|Show Up|Показать|已簽到)\s*</a>', confirmed, re.IGNORECASE):
                return {"status": "success", "message": "签到成功", "engine": "http"}
            raise RuntimeError("U2 签到提交后仍未确认已签到")
        raise _NeedsBrowser("该站点暂无稳定 HTTP 适配，切换 CloakBrowser")


async def _run(ctx, source: str) -> dict:
    global _run_lock
    if _run_lock is None:
        _run_lock = asyncio.Lock()
    if _run_lock.locked():
        return {"ok": False, "message": "签到任务正在运行"}
    async with _run_lock:
        cfg = _cfg(ctx)
        selected = cfg.get("selected_sites", list(SITES))
        if not isinstance(selected, list):
            selected = list(SITES)
        enabled = [(key, SITES[key]) for key in selected if key in SITES]
        if not enabled:
            return {"ok": False, "message": "没有启用任何签到站点"}
        _state.update({
            "running": True, "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": "", "current": "", "phase": "准备", "message": "正在准备签到任务",
            "completed": 0, "total": len(enabled),
        })
        results = []
        retries = _bounded(cfg.get("retry_count"), 2, 0, 5)
        interval = _bounded(cfg.get("retry_interval"), 20, 5, 300)
        loop = asyncio.get_running_loop()
        for key, site in enabled:
            _state.update({"current": site["name"], "phase": "读取 Cookie", "message": f"正在读取 {site['name']} 平台 Cookie"})
            cookie, error = await _site_cookie(ctx, key, site)
            if error:
                results.append({"key": key, "site": site["name"], "ok": False, "status": "failed", "message": error})
                _state["completed"] += 1
                continue
            cookie = _browser_cookie_cache.get(key) or cookie
            item = None
            for attempt in range(retries + 1):
                try:
                    outcome = None
                    browser_reason = ""
                    if key not in {"piggo", "tjupt"}:
                        _state.update({"phase": "HTTP 请求", "message": f"{site['name']} 正在使用轻量 HTTP 签到"})
                        try:
                            outcome = await _http_checkin(ctx, key, site, cookie)
                        except _NeedsBrowser as fallback:
                            browser_reason = str(fallback)
                    elif key == "piggo":
                        browser_reason = "PigGo 会话会轮换，直接使用 CloakBrowser"
                    else:
                        browser_reason = "TJUPT 需要页面交互验证"

                    if outcome is None:
                        _state.update({"phase": "浏览器降级", "message": f"{site['name']}：{browser_reason}"})

                        def action(page, site_key=key, current_site=site):
                            if site_key in {"audiences", "ourbits", "piggo", "hhan", "tjupt"}:
                                result = _browser_checkin(page, current_site["domain"], ctx, loop)
                                if site_key == "piggo":
                                    refreshed = _refreshed_cookie_header(page, current_site["domain"])
                                    if refreshed:
                                        _browser_cookie_cache[site_key] = refreshed
                                return result
                            return _special_checkin(page, site_key, current_site, ctx, loop)

                        outcome = await ctx.browser.run(
                            site["url"], action, cookies=cookie,
                            headless=bool(cfg.get("headless", True)),
                            timeout=720 if key == "tjupt" else (300 if key == "piggo" else 150),
                        )
                    status = str((outcome or {}).get("status") or "success")
                    engine = str((outcome or {}).get("engine") or "browser")
                    item = {
                        "key": key, "site": site["name"], "ok": True, "status": status,
                        "engine": engine, "message": str((outcome or {}).get("message") or "签到完成"),
                    }
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt < retries and _retryable_error(exc):
                        await asyncio.sleep(interval)
                    else:
                        item = {"key": key, "site": site["name"], "ok": False, "status": "failed", "engine": "http/browser", "message": str(exc)}
                        break
            results.append(item)
            _state["completed"] += 1

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
        if cfg.get("notify_result", True):
            rows = [{"站点": item["site"], "结果": "已签到" if item["status"] == "already" else ("成功" if item["ok"] else "失败"), "详情": item["message"]} for item in results]
            try:
                await ctx.notify(rows, level="success" if success == len(results) else "warning", category="PT站签到")
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("签到结果推送失败：%r", exc)
        _state.update({"running": False, "finished_at": stamp, "current": "", "phase": "完成", "message": summary})
        return {"ok": success == len(results), "message": text, "results": results}


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()
    _state.update({"running": False, "started_at": "", "finished_at": "", "current": "", "phase": "", "message": "", "completed": 0, "total": 0})

    @ctx.on_api("/meta", methods=["GET"])
    async def api_meta(req):
        return {
            "ok": True,
            "sites": [{"key": key, **{field: site[field] for field in ("name", "domain", "group")}, "status": site.get("status", "ready")} for key, site in SITES.items()],
            "defaults": DEFAULTS,
        }

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        return {"ok": True, **_state}

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(req):
        if _run_lock and _run_lock.locked():
            return {"ok": False, "message": "签到任务已经在运行"}
        task = ctx.create_task(_run(ctx, "手动"), name="PT站手动签到", operation="manual_checkin")
        _tasks.add(task)
        task.add_done_callback(_task_done)
        return {"ok": True, "message": "签到任务已开始"}

    @ctx.on_api("/history", methods=["GET"])
    async def api_history(req):
        items = ctx.kv.get(_HISTORY_KEY, []) or []
        return {"ok": True, "items": items if isinstance(items, list) else []}

    @ctx.on_api("/history/clear", methods=["POST"])
    async def api_history_clear(req):
        ctx.kv.set(_HISTORY_KEY, [])
        return {"ok": True, "message": "签到记录已清空"}

    @ctx.on_api("/cookies/check", methods=["POST"])
    async def api_cookies_check(req):
        data = req.json if isinstance(req.json, dict) else {}
        requested = data.get("selected_sites")
        selected = requested if isinstance(requested, list) else _cfg(ctx).get("selected_sites", list(SITES))
        selected = list(dict.fromkeys(str(key) for key in selected if str(key) in SITES))
        if not selected:
            return {"ok": False, "message": "请至少勾选一个站点", "items": []}
        rows = []
        for key in selected:
            cookie, error = await _site_cookie(ctx, key, SITES[key])
            rows.append({"key": key, "ok": bool(cookie), "message": "平台 Cookie 可用" if cookie else error})
        return {"ok": all(row["ok"] for row in rows), "items": rows}

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
        task.add_done_callback(_task_done)
        return {"ok": True, "message": "签到任务已开始，完成后会推送汇总结果"}

    @ctx.action("view_result")
    async def view_result():
        text = str(ctx.kv.get(_LAST_KEY, "") or "")
        return {"ok": bool(text), "message": text or "暂无签到记录"}

    cfg = _cfg(ctx)
    if cfg.get("auto_checkin", True):
        hour = _bounded(cfg.get("checkin_hour"), 8, 0, 23)
        minute = _bounded(cfg.get("checkin_minute"), 10, 0, 59)

        async def scheduled():
            await _run(ctx, "定时")

        ctx.schedule(scheduled, "cron", hour=hour, minute=minute, id="PT站每日签到")


async def teardown(ctx):
    _state.update({"running": False, "current": "", "phase": "", "message": ""})
    for pending in list(_tjupt_pending.values()):
        pending["choice"] = None
        pending["event"].set()
    _tjupt_pending.clear()
    _browser_cookie_cache.clear()
    tasks = list(_tasks)
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()
