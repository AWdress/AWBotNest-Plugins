"""憨憨工具箱：HHanClub 转盘与一键全部已读。"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from . import _bonus, _lottery
from ._auth import cookie_header


__plugin__ = {
    "name": "憨憨小助手",
    "id": "hhan_lottery",
    "version": "2.4.0",
    "author": "AWdress",
    "description": "HHanClub 综合助手：赠豆命令、幸运转盘、全部已读和收件箱消息删除。",
    "icon": "https://hhanclub.net/favicon.ico",
    "changelog": "v2.4.0 新增定时停止与重启续跑\n- 可设置具体日期和时间，到点后安全停止转盘任务\n- 抽奖计划与剩余次数持久化，平台或插件重启后自动继续\n- 手动停止、正常完成和到点停止会清除续跑计划\n\nv2.3.2 修复抽奖临时错误中止\n- Something wrong 等服务端临时异常改为自动退避重试\n- 仅余额不足、次数用完等明确条件立即停止，连续异常达到上限才结束\n\nv2.3.1 修复转盘配置保存按钮\n- 保存按钮不再被其他后台操作的忙碌状态连带禁用\n- 增加独立保存状态与失败提示，避免按钮长期不可点击\n\nv2.3.0 同步庆典版转盘更新\n- 新增保留余额模式、大奖止损和自定义奖品关键词\n- 每 N 抽自动校准服务端余额，可选清理“幸运大转盘”通知\n- 新增手动清理转盘通知，保留其他站内信\n- 增强 VIP 折算憨豆识别、奖品统计与限流退避\n\nv2.2.0 优化转盘次数",
    "scope": "user",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "cookie_domains": ["hhanclub.net", "*.hhanclub.net"],
    "default_enabled": False,
    "render_mode": "vue",
    "resources": {
        "timeout_seconds": 3600,
        "max_concurrency": 2,
        "max_background_tasks": 24,
        "failure_threshold": 5,
        "recovery_seconds": 60,
    },
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12", "lxml>=5.0"],
}


DEFAULTS = {
    "cookie_source": "platform",
    "manual_cookie": "",
    "enabled": True,
    "notify_result": True,
    "notify_cookie_error": True,
    "lottery_count": 10,
    "lottery_mode": "fixed",
    "interval_seconds": 7,
    "reserve_beans": 0,
    "sync_every_draws": 20,
    "auto_clean_lottery_mail": False,
    "stop_on_prize": False,
    "stop_on_vip": True,
    "stop_on_invite": True,
    "stop_on_big_beans": True,
    "big_bean_threshold": 500000,
    "stop_prize_keywords": "",
    "scheduled_stop_enabled": False,
    "scheduled_stop_at": "",
    "page_delay": 1.0,
    "max_pages": 200,
    "bonus_enabled": True,
    "single_command": ".hh",
    "batch_command": ".hhs",
    "cooldown_seconds": 10,
    "result_delete": 90,
}

_DOMAIN = "hhanclub.net"
_PAGE_URL = "https://hhanclub.net/messages.php"
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_task = None
_stop_event = None
_state = {
    "running": False, "operation": "read",
    "phase": "idle",
    "message": "尚未运行",
    "current_page": 0,
    "total_pages": 0,
    "processed": 0,
    "started_at": "",
    "finished_at": "",
    "stop_requested": False,
}


def _cfg(ctx) -> dict:
    return {**DEFAULTS, **dict(ctx.config or {})}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _looks_like_login(resp: httpx.Response) -> bool:
    path = urlparse(str(resp.url)).path.lower()
    text = (resp.text or "").lower()
    return path.endswith(("/login.php", "/takelogin.php")) or (
        "takelogin.php" in text
        or ('name="username"' in text and 'name="password"' in text)
        or ("name='username'" in text and "name='password'" in text)
    )


def _has_challenge(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in (
        "cf-chl-", "challenge-platform", "cloudflare ray id", "checking your browser"
    ))


def _headers(cookie: str, referer: str = _PAGE_URL) -> dict[str, str]:
    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": cookie,
        "Referer": referer,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
    }


async def _cookie_header(ctx, *, request_sync: bool = True) -> tuple[str, str]:
    return await cookie_header(ctx, path="/messages.php", request_sync=request_sync)


async def _request(client: httpx.AsyncClient, method: str, url: str,
                   headers: dict[str, str], *, content: bytes | None = None) -> tuple[httpx.Response, str]:
    """只允许跟随 HHanClub 站内跳转，防止显式 Cookie 泄露。"""
    current_method = method.upper()
    resp = await client.request(
        current_method, url, headers=headers, content=content, follow_redirects=False
    )
    for _ in range(5):
        if resp.status_code not in _REDIRECT_CODES:
            return resp, ""
        location = str(resp.headers.get("location", "") or "").strip()
        if not location:
            return resp, f"HTTP {resp.status_code}（缺少 Location）"
        target = urljoin(str(resp.url), location)
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != _DOMAIN:
            return resp, f"站点返回了不安全的跳转：{target}"
        current_method = "GET" if resp.status_code in {301, 302, 303} else current_method
        next_headers = dict(headers)
        next_headers["Referer"] = str(resp.url)
        if current_method == "GET":
            next_headers.pop("Origin", None)
            content = None
        resp = await client.request(
            current_method, target, headers=next_headers, content=content, follow_redirects=False
        )
    return resp, "站点跳转次数过多"


def _validate_page(resp: httpx.Response) -> str:
    if resp.status_code != 200:
        return f"网站返回 HTTP {resp.status_code}"
    if _looks_like_login(resp):
        return "Cookie 已失效，网站返回登录页"
    if _has_challenge(resp.text):
        return "站点触发了 Cloudflare 安全验证，请重新同步 Cookie"
    return ""


def _replace_page(url: str, value: str | int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _pagination_urls(soup: BeautifulSoup, current_url: str) -> list[str]:
    select = soup.select_one('select[onchange*="switchPage"]')
    if not select:
        return [current_url]
    urls = []
    for index, option in enumerate(select.find_all("option")):
        raw = str(option.get("value") or "").strip()
        if raw and ("messages.php" in raw or raw.startswith(("/", "http://", "https://"))):
            target = urljoin(current_url, raw)
        elif raw and re.fullmatch(r"\d+", raw):
            target = _replace_page(current_url, raw)
        else:
            # NexusPHP 分页通常是从 0 开始；没有 value 时按 option 顺序回退。
            target = _replace_page(current_url, index)
        parsed = urlparse(target)
        if parsed.hostname in {None, _DOMAIN} and target not in urls:
            urls.append(target)
    return urls or [current_url]


def _page_form(soup: BeautifulSoup, current_url: str) -> tuple[list[str], str, list[tuple[str, str]]]:
    unread_ids = []
    box = soup.select_one("#mail-table-display")
    rows = list(box.children) if box else []
    for row in rows:
        if not getattr(row, "select_one", None):
            continue
        image = row.select_one("img")
        checkbox = row.select_one('input[name="messages[]"]')
        src = str(image.get("src") or "") if image else ""
        value = str(checkbox.get("value") or "").strip() if checkbox else ""
        if "icon-unread.svg" in src and value:
            unread_ids.append(value)

    button = soup.select_one('input[type="submit"][name="markread"], button[name="markread"]')
    if not button:
        return unread_ids, current_url, []
    form = button.find_parent("form")
    action = urljoin(current_url, str(form.get("action") or current_url)) if form else current_url
    fields: list[tuple[str, str]] = []
    if form:
        for element in form.select('input[type="hidden"][name]'):
            fields.append((str(element.get("name")), str(element.get("value") or "")))
    fields.extend(("messages[]", value) for value in unread_ids)
    fields.append(("markread", str(button.get("value") or "设为已读")))
    return unread_ids, action, fields


def _delete_form(soup: BeautifulSoup, current_url: str) -> tuple[list[str], str, list[tuple[str, str]]]:
    """构造删除当前页全部消息的原生表单。"""
    message_ids = [
        str(item.get("value") or "").strip()
        for item in soup.select('#mail-table-display input[name="messages[]"]')
    ]
    message_ids = [value for value in message_ids if value]
    button = soup.select_one(
        'input[type="submit"][name="delete"], button[name="delete"], '
        'input[type="submit"][name="del"], button[name="del"], '
        'input[type="submit"][name="deletemessages"], button[name="deletemessages"]'
    )
    if not button:
        button = next((
            item for item in soup.select('input[type="submit"][name], button[name]')
            if "删除" in str(item.get("value") or item.get_text() or "")
        ), None)
    if not button:
        return message_ids, current_url, []
    form = button.find_parent("form")
    action = urljoin(current_url, str(form.get("action") or current_url)) if form else current_url
    fields: list[tuple[str, str]] = []
    if form:
        for element in form.select('input[type="hidden"][name]'):
            fields.append((str(element.get("name")), str(element.get("value") or "")))
    fields.extend(("messages[]", value) for value in message_ids)
    fields.append((str(button.get("name") or "delete"), str(button.get("value") or "删除")))
    return message_ids, action, fields


def _history(ctx) -> list[dict]:
    value = ctx.kv.get("history", []) or []
    return value if isinstance(value, list) else []


def _record(ctx, *, status: str, processed: int, pages: int, detail: str, operation: str = "read"):
    rows = _history(ctx)
    rows.insert(0, {
        "time": _now(), "status": status, "processed": processed,
        "pages": pages, "detail": detail, "operation": operation,
    })
    ctx.kv.set("history", rows[:20])


async def _check_cookie(ctx) -> dict:
    cookie, error = await _cookie_header(ctx)
    if error:
        return {"ok": False, "message": error}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0)) as client:
            resp, redirect_error = await _request(client, "GET", _PAGE_URL, _headers(cookie))
        error = redirect_error or _validate_page(resp)
        if error:
            return {"ok": False, "message": error}
        soup = BeautifulSoup(resp.text or "", "lxml")
        if not soup.select_one("#mail-table-display"):
            return {"ok": False, "message": "登录成功，但未识别到消息列表，页面结构可能已更新"}
        unread, _, _ = _page_form(soup, str(resp.url))
        return {"ok": True, "message": f"Cookie 有效，当前页识别到 {len(unread)} 条未读消息"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"访问 HHanClub 失败：{exc}"}


async def _run(ctx):
    global _task
    cfg = _cfg(ctx)
    processed = pages_checked = 0
    status = "completed"
    detail = "全部未读消息已处理"
    _state.update({
        "running": True, "operation": "read", "phase": "checking", "message": "正在检查 Cookie…",
        "current_page": 0, "total_pages": 0, "processed": 0,
        "started_at": _now(), "finished_at": "", "stop_requested": False,
    })
    try:
        cookie, error = await _cookie_header(ctx)
        if error:
            raise RuntimeError(error)
        delay = max(0.2, min(float(cfg.get("page_delay", 1.0) or 1.0), 10.0))
        max_pages = max(1, min(int(cfg.get("max_pages", 200) or 200), 1000))
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
            first, redirect_error = await _request(client, "GET", _PAGE_URL, _headers(cookie))
            error = redirect_error or _validate_page(first)
            if error:
                raise RuntimeError(error)
            first_soup = BeautifulSoup(first.text or "", "lxml")
            if not first_soup.select_one("#mail-table-display"):
                raise RuntimeError("未识别到消息列表，网站页面可能已更新")
            urls = _pagination_urls(first_soup, str(first.url))[:max_pages]
            _state["total_pages"] = len(urls)
            found_unread = False

            for index, page_url in enumerate(urls, start=1):
                if _stop_event and _stop_event.is_set():
                    status, detail = "stopped", "用户已停止任务"
                    break
                _state.update({
                    "phase": "searching" if not found_unread else "processing",
                    "message": f"正在检查第 {index}/{len(urls)} 页",
                    "current_page": index,
                })
                if index == 1 and page_url == str(first.url):
                    resp, soup = first, first_soup
                else:
                    resp, redirect_error = await _request(
                        client, "GET", page_url, _headers(cookie, str(first.url))
                    )
                    error = redirect_error or _validate_page(resp)
                    if error:
                        raise RuntimeError(f"第 {index} 页读取失败：{error}")
                    soup = BeautifulSoup(resp.text or "", "lxml")
                pages_checked += 1
                unread_ids, action, fields = _page_form(soup, str(resp.url))
                if not unread_ids:
                    if found_unread:
                        detail = "已进入历史已读区域，任务结束"
                        break
                    if index < len(urls):
                        await asyncio.sleep(delay)
                    continue
                found_unread = True
                if not fields:
                    raise RuntimeError(f"第 {index} 页找不到“设为已读”表单")
                _state.update({
                    "phase": "processing", "message": f"第 {index} 页正在处理 {len(unread_ids)} 条",
                })
                post_headers = _headers(cookie, str(resp.url))
                post_headers["Origin"] = "https://hhanclub.net"
                post_headers["Content-Type"] = "application/x-www-form-urlencoded"
                result, redirect_error = await _request(
                    client, "POST", action, post_headers,
                    content=urlencode(fields).encode("utf-8"),
                )
                error = redirect_error or _validate_page(result)
                if error:
                    raise RuntimeError(f"第 {index} 页提交失败：{error}")
                processed += len(unread_ids)
                _state["processed"] = processed
                ctx.log.info("[憨憨一键已读] page=%s marked=%s total=%s", index, len(unread_ids), processed)
                if index < len(urls):
                    await asyncio.sleep(delay)
    except asyncio.CancelledError:
        status, detail = "stopped", "插件已停用，任务取消"
        raise
    except Exception as exc:  # noqa: BLE001
        status, detail = "failed", str(exc)
        ctx.log.error("[憨憨一键已读] 任务失败：%r", exc)
    finally:
        _state.update({
            "running": False, "phase": status, "message": detail,
            "processed": processed, "finished_at": _now(), "stop_requested": False,
        })
        _record(ctx, status=status, processed=processed, pages=pages_checked, detail=detail)
        if cfg.get("notify_result", True):
            level = "success" if status == "completed" else ("error" if status == "failed" else "warning")
            try:
                await ctx.notify(
                    f"📖 憨憨一键已读\n\n处理消息：{processed} 条\n检查页面：{pages_checked} 页\n结果：{detail}",
                    level=level, category="憨憨一键已读",
                )
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("[憨憨一键已读] 结果通知失败：%r", exc)
        if _stop_event:
            _stop_event.clear()
        _task = None


async def _run_delete(ctx):
    """逐批删除收件箱当前第一页，避免删除后分页收缩而跳过消息。"""
    global _task
    cfg = _cfg(ctx)
    processed = batches = 0
    status, detail = "completed", "收件箱消息已全部删除"
    previous_ids: tuple[str, ...] = ()
    _state.update({
        "running": True, "operation": "delete", "phase": "checking",
        "message": "正在检查 Cookie…", "current_page": 0, "total_pages": 0,
        "processed": 0, "started_at": _now(), "finished_at": "", "stop_requested": False,
    })
    try:
        cookie, error = await _cookie_header(ctx)
        if error:
            raise RuntimeError(error)
        delay = max(0.2, min(float(cfg.get("page_delay", 1.0) or 1.0), 10.0))
        max_batches = max(1, min(int(cfg.get("max_pages", 200) or 200), 1000))
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0)) as client:
            while batches < max_batches:
                if _stop_event and _stop_event.is_set():
                    status, detail = "stopped", "用户已停止删除任务"
                    break
                resp, redirect_error = await _request(client, "GET", _PAGE_URL, _headers(cookie))
                error = redirect_error or _validate_page(resp)
                if error:
                    raise RuntimeError(error)
                soup = BeautifulSoup(resp.text or "", "lxml")
                if not soup.select_one("#mail-table-display"):
                    raise RuntimeError("未识别到消息列表，网站页面可能已更新")
                message_ids, action, fields = _delete_form(soup, str(resp.url))
                if not message_ids:
                    break
                fingerprint = tuple(message_ids)
                if fingerprint == previous_ids:
                    raise RuntimeError("删除后消息列表没有变化，站点可能拒绝了请求")
                if not fields:
                    raise RuntimeError("找不到网站的“删除”表单")
                previous_ids = fingerprint
                batches += 1
                _state.update({
                    "phase": "processing", "message": f"正在删除第 {batches} 批，共 {len(message_ids)} 条",
                    "current_page": batches, "total_pages": max_batches,
                })
                post_headers = _headers(cookie, str(resp.url))
                post_headers.update({"Origin": "https://hhanclub.net", "Content-Type": "application/x-www-form-urlencoded"})
                result, redirect_error = await _request(
                    client, "POST", action, post_headers,
                    content=urlencode(fields).encode("utf-8"),
                )
                error = redirect_error or _validate_page(result)
                if error:
                    raise RuntimeError(f"第 {batches} 批删除失败：{error}")
                processed += len(message_ids)
                _state["processed"] = processed
                await asyncio.sleep(delay)
            else:
                detail = f"已达到最多处理 {max_batches} 批的限制"
    except asyncio.CancelledError:
        status, detail = "stopped", "插件已停用，删除任务取消"
        raise
    except Exception as exc:  # noqa: BLE001
        status, detail = "failed", str(exc)
        ctx.log.error("[憨憨消息删除] 任务失败：%r", exc)
    finally:
        _state.update({
            "running": False, "phase": status, "message": detail,
            "processed": processed, "finished_at": _now(), "stop_requested": False,
        })
        _record(ctx, status=status, processed=processed, pages=batches, detail=detail, operation="delete")
        if cfg.get("notify_result", True):
            level = "success" if status == "completed" else ("error" if status == "failed" else "warning")
            try:
                await ctx.notify(
                    f"憨憨消息删除\n\n删除消息：{processed} 条\n处理批次：{batches} 批\n结果：{detail}",
                    level=level, category="憨憨消息管理",
                )
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("[憨憨消息删除] 结果通知失败：%r", exc)
        if _stop_event:
            _stop_event.clear()
        _task = None


async def setup(ctx):
    global _task, _stop_event
    _task = None
    _stop_event = asyncio.Event()
    _state.update({
        "running": False, "operation": "read", "phase": "idle", "message": "尚未运行",
        "current_page": 0, "total_pages": 0, "processed": 0,
        "started_at": "", "finished_at": "", "stop_requested": False,
    })

    await _lottery.setup(ctx)
    await _bonus.setup(ctx)

    @ctx.on_api("/read/status", methods=["GET"])
    async def api_status(req):
        return {**_state}

    @ctx.on_api("/auth/check", methods=["GET"])
    async def api_auth_check(req):
        result = await _check_cookie(ctx)
        result["source"] = str(_cfg(ctx).get("cookie_source", "platform"))
        return result

    @ctx.on_api("/read/cookie/check", methods=["GET"])
    async def api_cookie_check(req):
        return await _check_cookie(ctx)

    @ctx.on_api("/read/run", methods=["POST"])
    async def api_run(req):
        global _task
        if not _cfg(ctx).get("enabled", True):
            return {"ok": False, "message": "请先启用插件并保存配置"}
        if _task and not _task.done():
            return {"ok": False, "message": "已有一键已读任务正在运行"}
        if _stop_event:
            _stop_event.clear()
        _task = ctx.create_task(_run(ctx), name="憨憨一键全部已读", operation="mark_read")
        return {"ok": True, "message": "任务已开始，可在面板查看实时进度"}

    @ctx.on_api("/read/delete", methods=["POST"])
    async def api_delete(req):
        global _task
        if not _cfg(ctx).get("enabled", True):
            return {"ok": False, "message": "请先启用插件并保存配置"}
        if _task and not _task.done():
            return {"ok": False, "message": "已有消息处理任务正在运行"}
        if _stop_event:
            _stop_event.clear()
        _task = ctx.create_task(_run_delete(ctx), name="憨憨删除全部消息", operation="delete_messages")
        return {"ok": True, "message": "删除任务已开始，可在面板查看实时进度"}

    @ctx.on_api("/read/stop", methods=["POST"])
    async def api_stop(req):
        if not (_task and not _task.done()):
            return {"ok": False, "message": "当前没有运行中的任务"}
        if _stop_event:
            _stop_event.set()
        _state.update({"stop_requested": True, "message": "已请求停止，当前请求结束后退出"})
        return {"ok": True, "message": "已请求停止"}

    @ctx.on_api("/read/history", methods=["GET"])
    async def api_history(req):
        return {"ok": True, "items": _history(ctx)}

    @ctx.on_api("/read/history/clear", methods=["POST"])
    async def api_history_clear(req):
        ctx.kv.set("history", [])
        return {"ok": True, "message": "运行记录已清空"}


async def teardown(ctx):
    if _stop_event:
        _stop_event.set()
    await _lottery.teardown(ctx)
    await _bonus.teardown(ctx)


async def self_check(ctx):
    cookie, error = await _cookie_header(ctx, request_sync=False)
    return {
        "id": "cookie_sync", "name": "平台 Cookie 同步", "ok": bool(cookie),
        "detail": "已读取 hhanclub.net Cookie" if cookie else error,
    }
