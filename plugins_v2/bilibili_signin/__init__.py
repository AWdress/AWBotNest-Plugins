"""B 站每日综合签到：AWBotNest V2 原生实现。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List

import requests


__plugin__ = {
    "name": "B站每日综合签到",
    "id": "bilibili_signin",
    "version": "0.1.2",
    "author": "AWdress",
    "description": "使用 B 站 Cookie 完成分享、观看心跳、直播、漫画等每日签到，逐项显示结果和失败原因并推送账号状态。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/bilibili_signin/logo.png",
    "changelog": (
        "v0.1.2 精简签到通知\n"
        "- 通知仅显示失败项目、简短错误码和完成/跳过数量，避免长错误日志撑开表格\n"
        "- 限制通知详情长度，完整原因继续保留在运行日志、最近结果和历史记录中\n\n"
        "v0.1.1 显示具体失败项目\n"
        "- 通知、立即执行、最近结果和历史逐项显示签到状态、HTTP 状态及业务错误码\n"
        "- 分享、观看、直播和漫画独立处理，单项异常或缺少 bili_jct 不再中断其他项目\n"
        "- 漫读券查询失败仅提示查询异常，不再覆盖已完成的签到结果\n"
        "- 修复历史时间和明细丢失，收紧成功、已签到及活动下线判定\n\n"
        "v0.1.0 修复 B 站综合签到\n"
        "- 动态视频接口为空时使用公开视频详情兜底，补齐 cid 与观看心跳参数\n"
        "- 直播签到活动下线时标记为跳过，不再导致整轮失败\n\n"
        "v0.0.9 修复保存后账号列表恢复\n"
        "- 不再对整个账号列表做脱敏，避免平台读取时变成 ******** 导致账号行消失\n"
        "- 每行 Cookie 继续使用 password 字段默认隐藏并支持眼睛查看\n\n"
        "v0.0.8 修复残留 Cookie 导致保存失败\n"
        "- 兼容清理旧配置中的顶层 Cookie 键，避免平台提示包含未声明配置项\n"
        "- 旧 Cookie 启动时自动转入首个账号并清空隐藏旧字段，界面仍保持逐账号配置\n\n"
        "v0.0.7 修复原生配置保存\n"
        "- 显式声明使用平台原生 schema 渲染，确保保存按钮绑定标准配置提交流程\n"
        "- 保持逐账号名称与 Cookie 字段及独立显隐功能\n\n"
        "v0.0.6 修复账号配置界面\n"
        "- 使用平台原生逐账号列表配置，账号名称与 Cookie 分开填写\n"
        "- Cookie 默认隐藏，每个账号独立支持眼睛显示/隐藏、添加与删除\n\n"
        "v0.0.1 首次发布\n"
        "- 接入分享、观看心跳、直播签到和漫画签到接口\n"
        "- 支持多账号 Cookie、定时 Cron、立即执行、硬币/等级/漫读券信息和富文本通知\n"
        "- 仅依据 B 站接口 code 与明确重复签到提示判断结果"
    ),
    "scope": "standalone",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "tags": ["B站", "每日签到", "Cookie"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "resources": {"timeout_seconds": 600, "max_concurrency": 1, "max_background_tasks": 2},
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "推送签到结果", "section": "功能开关", "order": 2},
        "accounts": {
            "type": "list", "default": [],
            "label": "B站账号", "item_label": "账号",
            "help": "逐个添加账号；建议使用浏览器无痕窗口登录 B 站后复制 Cookie，避免顶掉日常登录会话。Cookie 默认隐藏，可按行点击眼睛查看。",
            "section": "账号", "cols": 12, "order": 10,
            "fields": {
                "name": {"type": "string", "label": "账号名称"},
                "cookie": {"type": "password", "label": "Cookie", "secret": True},
            },
        },
        # 旧版本/误填配置可能残留顶层 cookie；隐藏声明仅用于一次性清理，界面不展示。
        "cookie": {"type": "password", "default": "", "secret": True, "show_if": {"_legacy_cookie_visible": True}, "label": ""},
        "share": {"type": "boolean", "default": True, "label": "每日分享签到", "section": "签到项目", "order": 20},
        "heartbeat": {"type": "boolean", "default": True, "label": "每日观看签到", "section": "签到项目", "order": 21},
        "live": {"type": "boolean", "default": True, "label": "直播签到", "section": "签到项目", "order": 22},
        "manga": {"type": "boolean", "default": True, "label": "漫画签到", "section": "签到项目", "order": 23},
        "delay": {"type": "number", "default": 10, "min": 0, "max": 60, "step": 1, "label": "项目间隔（秒）", "help": "项目请求之间的间隔，避免触发接口频率限制。", "section": "签到设置", "order": 30},
        "cron": {"type": "string", "format": "cron", "default": "10 8 * * *", "label": "签到 Cron", "help": "标准五段 Cron，默认每天 08:10。", "section": "签到设置", "order": 31},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "step": 1, "label": "请求超时（秒）", "section": "签到设置", "order": 32},
        "run_now": {"type": "action", "label": "立即签到", "action": "run_now", "section": "操作", "order": 40},
        "last_result": {"type": "info", "default": "尚未运行", "label": "最近结果", "section": "运行状态", "cols": 12, "order": 50},
        "history": {"type": "info", "default": "暂无记录", "label": "最近签到记录", "section": "运行状态", "cols": 12, "order": 51},
    },
}

API = "https://api.bilibili.com"
LIVE_SIGN = "https://api.live.bilibili.com/xlive/web-ucenter/v1/sign/DoSign"
MANGA_CLOCKIN = "https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn"
MANGA_COUPONS = "https://manga.bilibili.com/twirp/user.v1.User/GetCoupons"
_run_lock: asyncio.Lock | None = None
FALLBACK_BVIDS = ("BV1xx411c7mD", "BV1GJ411x7h7", "BV1Q541167Qg")


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _cron_fields(expression: str) -> Dict[str, str]:
    parts = str(expression or "").strip().split()
    if len(parts) != 5:
        raise ValueError("必须是标准五段 Cron：分 时 日 月 星期")
    return dict(zip(("minute", "hour", "day", "month", "day_of_week"), parts))


def _accounts(raw: Any) -> List[Dict[str, str]]:
    if isinstance(raw, list):
        result = []
        for index, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                continue
            cookie = str(item.get("cookie") or "").strip()
            if cookie:
                result.append({"name": str(item.get("name") or f"账号 {index}").strip(), "cookie": cookie})
        if result:
            return result
    result = []
    for index, line in enumerate(re.split(r"(?:\r?\n|\s+&\s+)", str(raw or "")), 1):
        line = line.strip()
        if not line or line == "********":
            continue
        if "----" in line:
            name, cookie = line.split("----", 1)
        else:
            name, cookie = f"账号 {index}", line
        if cookie.strip():
            result.append({"name": name.strip() or f"账号 {index}", "cookie": cookie.strip()})
    return result


def _json(response: requests.Response) -> dict:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _message(body: dict, text: str = "") -> str:
    for key in ("message", "msg", "message_text", "error"):  # B 站不同业务接口字段不完全一致
        if body.get(key):
            return str(body[key]).strip()
    return str(text or "").strip()[:180]


def _already_done(body: dict) -> bool:
    code = body.get("code")
    if "code" in body and (type(code) not in (int, str) or code == ""):
        return False
    if str(code) in {"-101", "-111", "-400", "-403", "-412", "-509"}:
        return False
    message = _message(body).lower()
    if any(word in message for word in ("未登录", "未完成", "未签到", "尚未", "不能", "禁止", "not signed", "not logged")):
        return False
    return any(word in message for word in (
        "已签到", "已经签到", "今日已完成", "今天已完成", "今日已分享", "已经分享", "今日已观看",
        "already signed", "already checked in", "already shared", "already watched",
    ))


def _api_ok(body: dict, text: str = "", allow_duplicate: bool = True, *, http_status: int = 200) -> bool:
    if http_status not in (200, 201):
        return False
    code = body.get("code")
    if type(code) in (int, str) and code in (0, "0"):
        return True
    # Only a structured business receipt can confirm a repeated check-in.
    # An HTML error/login page mentioning "already" is not a receipt.
    return allow_duplicate and _already_done(body)


def _response_detail(response, body: dict) -> str:
    code = body.get("code")
    if _api_ok(body, http_status=response.status_code):
        return "今天已签到" if _already_done(body) else "签到成功"
    hints = {"-101": "未登录或 Cookie 已失效", "-111": "CSRF 校验失败，请重新获取完整 Cookie",
             "-400": "请求参数错误", "-403": "访问权限不足", "-412": "请求被风控拦截，请稍后重试",
             "-509": "请求过于频繁，请稍后重试"}
    message = _message(body) or hints.get(str(code)) or ("缺少明确的业务结果" if body else "接口未返回有效 JSON")
    message = re.sub(r"\s+", " ", message)[:180]
    code_text = f"，code={code}" if "code" in body else "，缺少 code"
    return f"HTTP {response.status_code}{code_text}：{message}"


def _request_error(error: Exception) -> str:
    # Do not echo request headers/cookies or a complete raw response to users.
    if isinstance(error, requests.Timeout):
        return "请求超时，请稍后重试"
    if isinstance(error, requests.ConnectionError):
        return "网络连接失败，请检查服务器网络或代理"
    return f"请求处理失败（{type(error).__name__}）"


def _finish_result(result: dict) -> dict:
    actions = result.get("actions", [])
    failed = [item["项目"] for item in actions if item["状态"] == "失败"]
    result["ok"] = bool(actions) and not failed
    result["message"] = ("部分签到失败：" + "、".join(failed) if failed else
                         "综合签到完成" if actions else "未启用任何签到项目")
    return result


def _result_details(item: dict) -> str:
    lines = []
    for action in item.get("actions", []):
        detail = action.get("详情", "")
        suffix = f"（{detail}）" if detail and detail not in {"签到成功", "今天已签到"} else ""
        lines.append(f"{action['项目']}：{action['状态']}{suffix}")
    if not lines:
        lines.append(str(item.get("message") or "未返回签到结果"))
    for warning in item.get("warnings", []):
        lines.append(f"{warning['项目']}：{warning['详情']}（不影响签到结果）")
    return "；".join(lines)


def _notification_error_suffix(detail: str) -> str:
    code = re.search(r"\bcode\s*=\s*(-?\d{1,6})(?!\d)", detail, re.IGNORECASE)
    if code and int(code[1]) != 0:
        return f"({code[1]})"
    status = re.search(r"\bHTTP\s+([1-5]\d{2})\b", detail, re.IGNORECASE)
    if status and not 200 <= int(status[1]) < 300:
        return f"(HTTP{status[1]})"
    if "超时" in detail or "timeout" in detail.lower():
        return "(超时)"
    if "网络连接失败" in detail:
        return "(网络异常)"
    if "缺少 bili_jct" in detail:
        return "(缺bili_jct)"
    return ""


def _notification_details(item: dict) -> str:
    # Notifications use a bounded summary; logs/history keep _result_details.
    actions = item.get("actions") or []
    parts = []
    if actions:
        labels = {"分享签到": "分享", "观看签到": "观看", "直播签到": "直播", "漫画签到": "漫画"}
        failed = [action for action in actions if action.get("状态") == "失败"]
        for action in failed[:2]:
            label = labels.get(action.get("项目"), "项目")
            parts.append(f"{label}失败{_notification_error_suffix(str(action.get('详情') or ''))}")
        if len(failed) > 2:
            parts.append(f"另{len(failed) - 2}项失败")
        completed = sum(action.get("状态") in {"已完成", "已签到"} for action in actions)
        skipped = sum(action.get("状态") == "跳过" for action in actions)
        counts = []
        if completed:
            counts.append(f"完成{completed}项")
        if skipped:
            counts.append(f"跳过{skipped}项")
        if counts:
            parts.append("，".join(counts))
    else:
        message = str(item.get("message") or "")
        suffix = _notification_error_suffix(message)
        if "未配置" in message and "Cookie" in message:
            parts.append("未配置Cookie")
        elif "已失效" in message or "未登录" in message:
            parts.append("Cookie失效" + suffix)
        elif "未启用" in message:
            parts.append("未启用签到项目")
        elif suffix == "(超时)":
            parts.append("请求超时")
        elif suffix == "(网络异常)":
            parts.append("网络连接失败")
        elif "账号校验失败" in message:
            parts.append("账号校验失败" + suffix)
        else:
            parts.append("签到完成" if item.get("ok") else "签到失败")
    if item.get("warnings"):
        coupon_warning = any(warning.get("项目") == "漫读券查询" for warning in item["warnings"])
        parts.append("漫读券查询失败" if coupon_warning else "附加查询失败")
    summary = "；".join(parts) or "结果待确认"
    return summary if len(summary) <= 48 else summary[:47] + "…"


def _display_result(item: dict) -> str:
    return f"{item.get('name', '账号')} · {item.get('message', '')}\n{_result_details(item)}"


def _cookie_jar(raw: str) -> requests.cookies.RequestsCookieJar:
    jar = requests.cookies.RequestsCookieJar()
    for part in str(raw or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        if name:
            jar.set(name.strip(), value.strip(), domain=".bilibili.com", path="/")
    return jar


def _signin_one(account: Dict[str, str], enabled: Dict[str, bool], delay: int, timeout: int, log=None) -> Dict[str, Any]:
    name = account.get("name") or "默认账号"
    result: Dict[str, Any] = {"name": name, "ok": False, "actions": [], "warnings": []}
    if not any(enabled.get(key) for key in ("share", "heartbeat", "live", "manga")):
        return _finish_result(result)
    session = requests.Session()
    session.cookies.update(_cookie_jar(account.get("cookie", "")))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com/",
    })
    try:
        nav = session.get(f"{API}/x/web-interface/nav", timeout=timeout)
        nav_body = _json(nav)
        nav_data = nav_body.get("data") if isinstance(nav_body.get("data"), dict) else {}
        if not _api_ok(nav_body, allow_duplicate=False, http_status=nav.status_code):
            return {**result, "message": "账号校验失败：" + _response_detail(nav, nav_body)}
        if nav_data.get("isLogin") is not True:
            return {**result, "message": "Cookie 已失效或 B 站未登录，未取得登录确认"}
        level_info = nav_data.get("level_info") if isinstance(nav_data.get("level_info"), dict) else {}
        level_exp = nav_data.get("level_exp") if isinstance(nav_data.get("level_exp"), dict) else {}
        result.update({"uid": nav_data.get("mid", "-"), "uname": nav_data.get("uname", name),
                       "level": level_info.get("current_level", "-"), "coin": nav_data.get("money", "-"),
                       "exp": level_exp.get("current_exp", "-")})
        csrf = next((c.value for c in session.cookies if c.name == "bili_jct"), "")

        def record(label: str, status: str, message: str):
            result["actions"].append({"项目": label, "状态": status, "详情": message})
            if log:
                (log.warning if status == "失败" else log.info)(
                    "[B站每日综合签到] [%s] %s：%s（%s）", name, label, status, message)

        def perform(label: str, callback, *, live: bool = False):
            try:
                response = callback()
                body = _json(response)
                message = _message(body)
                live_offline = (live and response.status_code == 200 and type(body.get("code")) in (int, str)
                                and str(body["code"]) not in {"-101", "-111", "-400", "-403", "-412", "-509"} and any(
                    word in message for word in ("签到活动已下线", "签到活动已结束", "签到活动未开放", "签到活动暂未开放"))
                                )
                if live_offline:
                    record(label, "跳过", message)
                elif _api_ok(body, http_status=response.status_code):
                    record(label, "已签到" if _already_done(body) else "已完成", _response_detail(response, body))
                else:
                    record(label, "失败", _response_detail(response, body))
            except Exception as exc:  # One task must not prevent other independent check-ins.
                record(label, "失败", _request_error(exc))
            if delay:
                time.sleep(delay)

        bvid = ""
        video_error = "Cookie 中缺少 bili_jct，请重新获取完整 Cookie"
        if csrf and (enabled.get("share") or enabled.get("heartbeat")):
            matches = []
            video_errors = []
            try:
                dynamic = session.get(f"{API}/x/web-interface/dynamic/region", params={"pn": 1, "ps": 12, "rid": 0}, timeout=timeout)
                if dynamic.status_code == 200:
                    matches = re.findall(r"BV[A-Za-z0-9]{10}", dynamic.text or "")
                else:
                    video_errors.append(_response_detail(dynamic, _json(dynamic)))
            except Exception as exc:
                video_errors.append(_request_error(exc))
            candidates = list(dict.fromkeys(matches + list(FALLBACK_BVIDS)))
            # A broken dynamic endpoint or candidate must not stop the fallback list.
            for candidate in candidates:
                try:
                    view = session.get(f"{API}/x/web-interface/view", params={"bvid": candidate}, timeout=timeout)
                    view_body = _json(view)
                    data = view_body.get("data") if isinstance(view_body.get("data"), dict) else {}
                    cid = data.get("cid")
                    valid_cid = type(cid) in (int, str) and str(cid).isdigit() and int(cid) > 0
                    if _api_ok(view_body, allow_duplicate=False, http_status=view.status_code) and valid_cid:
                        bvid = candidate
                        result["cid"] = int(cid)
                        break
                    video_errors.append(_response_detail(view, view_body) if not _api_ok(
                        view_body, allow_duplicate=False, http_status=view.status_code) else "视频详情缺少有效 cid")
                except Exception as exc:
                    video_errors.append(_request_error(exc))
            video_error = "未找到可用视频" + ("：" + "；".join(dict.fromkeys(video_errors[-2:])) if video_errors else "")
        if enabled.get("share"):
            if bvid:
                perform("分享签到", lambda: session.post(f"{API}/x/web-interface/share/add", data={"bvid": bvid, "csrf": csrf}, timeout=timeout))
            else:
                record("分享签到", "失败", video_error)
        if enabled.get("heartbeat"):
            if bvid:
                perform("观看签到", lambda: session.post(f"{API}/x/click-interface/web/heartbeat", data={
                    "bvid": bvid, "cid": result["cid"], "csrf": csrf,
                    "played_time": 2, "realtime": 2, "start_ts": int(time.time()) - 2,
                    "type": 3, "dt": 2, "play_type": 1,
                }, timeout=timeout))
            else:
                record("观看签到", "失败", video_error)
        if enabled.get("live"):
            perform("直播签到", lambda: session.get(LIVE_SIGN, timeout=timeout), live=True)
        if enabled.get("manga"):
            perform("漫画签到", lambda: session.post(MANGA_CLOCKIN, data={"platform": "ios"}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=timeout))
            try:
                response = session.post(MANGA_COUPONS, json={"notExpired": True, "pageNum": 1, "pageSize": 20, "tabType": 1, "type": 0}, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=timeout)
                body = _json(response)
                data = body.get("data") if isinstance(body.get("data"), dict) else {}
                if not _api_ok(body, allow_duplicate=False, http_status=response.status_code):
                    raise ValueError(_response_detail(response, body))
                result["manga"] = data.get("total_remain_amount", "-")
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else _request_error(exc)
                result["warnings"].append({"项目": "漫读券查询", "详情": message})
                if log:
                    log.warning("[B站每日综合签到] [%s] 漫读券查询失败，不影响签到结果：%s", name, message)
        return _finish_result(result)
    except requests.RequestException as exc:
        return {**result, "ok": False, "message": "账号校验失败：" + _request_error(exc)}
    except Exception as exc:  # noqa: BLE001
        return {**result, "ok": False, "message": f"账号信息处理失败（{type(exc).__name__}）"}
    finally:
        session.close()


async def setup(ctx):
    global _run_lock
    defaults = {}
    for key, spec in __plugin__["config_schema"].items():
        if "default" not in spec or spec.get("type") == "action":
            continue
        current = ctx.config.get(key)
        if key not in ctx.config or current is None or (isinstance(current, str) and not current.strip()):
            defaults[key] = spec["default"]
    if defaults:
        ctx.update_config(defaults)
    raw_accounts = ctx.config.get("accounts")
    normalized_accounts = _accounts(raw_accounts)
    legacy_cookie = str(ctx.config.get("cookie") or "").strip()
    if legacy_cookie and not normalized_accounts:
        normalized_accounts = [{"name": "账号 1", "cookie": legacy_cookie}]
        ctx.update_config({"accounts": normalized_accounts, "cookie": ""})
        ctx.log.info("[B站每日综合签到] 已将残留顶层 Cookie 转入逐账号列表")
    elif legacy_cookie:
        ctx.update_config({"cookie": ""})
        ctx.log.info("[B站每日综合签到] 已清理残留顶层 Cookie 配置")
    if isinstance(raw_accounts, str) and normalized_accounts and not legacy_cookie:
        ctx.update_config({"accounts": normalized_accounts})
        ctx.log.info("[B站每日综合签到] 已将旧账号 Cookie 文本转换为逐账号列表")
    _run_lock = asyncio.Lock()
    jobs = []

    async def save_results(results: List[Dict[str, Any]], source: str):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = await ctx.storage.get("history", [])
        if not isinstance(history, list): history = []
        history.append({"time": stamp, "source": source, "results": results})
        history = history[-100:]
        await ctx.storage.set("history", history)
        await ctx.storage.set("last_result", {"time": stamp, "source": source, "results": results})
        ok_count = sum(bool(item.get("ok")) for item in results)
        history_lines = []
        for run in reversed(history[-10:]):
            if not isinstance(run, dict):
                continue
            saved_results = run.get("results", [])
            if not isinstance(saved_results, list):
                continue
            for item in saved_results:
                if isinstance(item, dict):
                    history_lines.append(f"{run.get('time', '-')} · {_display_result(item)}")
        ctx.update_config({
            "last_result": f"{stamp} · 成功 {ok_count}/{len(results)}\n" + "\n\n".join(_display_result(item) for item in results),
            "history": "\n\n".join(history_lines),
        })

    async def run_once(source: str):
        assert _run_lock is not None
        if _run_lock.locked(): return {"ok": False, "message": "B站签到任务正在运行"}
        async with _run_lock:
            accounts = _accounts(ctx.config.get("accounts"))
            if not accounts:
                result = {"ok": False, "message": "未配置 B 站 Cookie"}
                await save_results([result], source)
                return result
            enabled = {key: bool(ctx.config.get(key, True)) for key in ("share", "heartbeat", "live", "manga")}
            delay = _bounded_int(ctx.config.get("delay"), 10, 0, 60)
            timeout = _bounded_int(ctx.config.get("timeout"), 30, 5, 120)
            ctx.log.info("[B站每日综合签到] 开始执行，来源=%s，账号=%d", source, len(accounts))
            results = await asyncio.gather(*(asyncio.to_thread(_signin_one, account, enabled, delay, timeout, ctx.log) for account in accounts))
            await save_results(results, source)
            if ctx.config.get("notify", True):
                rows = []
                for item in results:
                    rows.append({"账号": item.get("name", "-"), "状态": "成功" if item.get("ok") else "失败", "等级": item.get("level", "-"), "硬币": item.get("coin", "-"), "漫读券": item.get("manga", "-"), "详情": _notification_details(item)})
                try: await asyncio.wait_for(ctx.notify(rows, category="B站每日综合签到"), timeout=30)
                except Exception as exc: ctx.log.warning("[B站每日综合签到] 通知发送失败：%r", exc)
            ok_count = sum(bool(item.get("ok")) for item in results)
            (ctx.log.info if ok_count == len(results) else ctx.log.warning)("[B站每日综合签到] 完成：成功 %d/%d", ok_count, len(results))
            return {"ok": ok_count == len(results), "results": results,
                    "message": f"成功 {ok_count}/{len(results)}\n" + "\n\n".join(_display_result(item) for item in results)}

    @ctx.action("run_now")
    async def run_now(): return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(request): return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request): return {"running": bool(_run_lock and _run_lock.locked()), "last_result": await ctx.storage.get("last_result", None), "history": await ctx.storage.get("history", [])}

    if ctx.config.get("enabled", False):
        try:
            jobs.append(ctx.schedule_cron("B站每日综合签到·定时", lambda: run_once("定时"), **_cron_fields(ctx.config.get("cron") or "10 8 * * *")))
            ctx.log.info("[B站每日综合签到] 定时任务已启用：%s", ctx.config.get("cron") or "10 8 * * *")
        except ValueError as exc: ctx.log.error("[B站每日综合签到] Cron 配置无效：%s", exc)

    async def cleanup():
        for job in jobs:
            try:
                if hasattr(job, "cancel"): job.cancel()
            except Exception: pass
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[B站每日综合签到] 插件已停用")
