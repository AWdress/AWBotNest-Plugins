"""百度贴吧签到：AWBotNest V2 原生实现。"""
from __future__ import annotations

import asyncio
import html
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import unquote, unquote_to_bytes

import requests


__plugin__ = {
    "name": "百度贴吧签到",
    "id": "tieba_signin",
    "version": "0.1.5",
    "author": "AWdress",
    "description": "使用百度贴吧 Cookie 自动完成关注贴吧签到，支持多账号、定时执行，通知显示简洁统计，完整吧名及结果保留在记录中。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/tieba_signin/logo.png",
    "changelog": (
        "v0.1.5 精简签到通知\n"
        "- 通知改为紧凑文字，保留状态和本次/此前已签到数量，不再铺开成功贴吧名单\n"
        "- 失败/未确认仅预览最多 3 个吧名和一条原因，完整明细仍保留在插件记录中\n\n"
        "v0.1.4 显示已签到贴吧\n"
        "- 结果通知、日志和最近记录列出本次签到、此前已签到及失败/未确认的吧名与数量\n"
        "- 以逐吧回执统计已签到数量，避免一键接口返回 0 时覆盖已签到结果\n"
        "- HTTP 与浏览器共用结果判定，中途断网或浏览器重试失败时保留已确认记录\n\n"
        "v0.1.3 修复浏览器回退签到请求\n"
        "- CloakBrowser/Chromium 统一使用异步 API，避免同步 Playwright 在事件循环中报错\n"
        "- 贴吧接口 POST 改用 application/x-www-form-urlencoded，修复未知错误和目录问题\n"
        "- 兼容关注列表 GB18030 编码及 no=1101 已签到回执，准确识别成功/已签到状态\n"
        "- 为浏览器请求增加 30 秒单请求超时，避免异常网络导致任务长期挂起\n\n"
        "v0.1.2 增加浏览器网络回退\n"
        "- Python HTTP 连接超时时自动切换平台浏览器，携带当前账号 Cookie 重试完整签到流程\n"
        "- 浏览器回退同样执行关注贴吧扫描、逐吧签到和一键签到结果确认\n"
        "- 日志明确记录切换原因，避免仅显示 0/1 而无法定位网络问题\n\n"
        "v0.1.1 修复已签到识别\n"
        "- 识别贴吧接口返回的已签到、签过到和重复签到提示\n"
        "- 通知状态显示为“已签到”，不再把重复签到报成失败\n\n"
        "v0.1.0 修复贴吧签到结果判定\n"
        "- 不再把 HTTP 200 或接口返回空值误判为成功，失败数量大于零时明确标记失败\n\n"
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
        "- 根据百度贴吧签到流程接入 Cookie 校验、TBS 获取、关注贴吧扫描和一键签到\n"
        "- 支持逐账号配置、定时签到、立即执行、签到统计与历史记录\n"
        "- 仅依据贴吧接口返回的签到数量生成结果，不把 HTTP 成功误判为签到成功"
    ),
    "scope": "standalone",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "tags": ["百度贴吧", "自动签到", "Cookie"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "resources": {"timeout_seconds": 900, "max_concurrency": 1, "max_background_tasks": 2},
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "推送签到结果", "section": "功能开关", "order": 2},
        "accounts": {
            "type": "list", "default": [],
            "label": "贴吧账号", "item_label": "账号",
            "help": "逐个添加账号；Cookie 默认隐藏，可按行点击眼睛查看。",
            "section": "账号", "cols": 12, "order": 10,
            "fields": {
                "name": {"type": "string", "label": "账号名称"},
                "cookie": {"type": "password", "label": "Cookie", "secret": True},
            },
        },
        # 旧版本/误填配置可能残留顶层 cookie；隐藏声明仅用于一次性清理，界面不展示。
        "cookie": {"type": "password", "default": "", "secret": True, "show_if": {"_legacy_cookie_visible": True}, "label": ""},
        "delay": {"type": "number", "default": 3, "min": 0, "max": 15, "step": 1, "label": "贴吧间隔（秒）", "help": "每个贴吧签到请求之间的间隔，避免触发频率限制。", "section": "签到设置", "order": 20},
        "cron": {"type": "string", "format": "cron", "default": "5 8 * * *", "label": "签到 Cron", "help": "标准五段 Cron，默认每天 08:05。", "section": "签到设置", "order": 21},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "step": 1, "label": "请求超时（秒）", "section": "签到设置", "order": 22},
        "run_now": {"type": "action", "label": "立即签到", "action": "run_now", "section": "操作", "cols": 6, "order": 30},
        "last_result": {"type": "info", "default": "尚未运行", "label": "最近结果", "section": "运行状态", "cols": 12, "order": 40},
        "history": {"type": "info", "default": "暂无记录", "label": "最近签到记录", "section": "运行状态", "cols": 12, "order": 41},
    },
}

BASE_URL = "https://tieba.baidu.com"
USERINFO_API = f"{BASE_URL}/f/user/json_userinfo"
TBS_API = f"{BASE_URL}/dc/common/tbs"
MYLIKE_URL = f"{BASE_URL}/f/like/mylike"
SIGN_API = f"{BASE_URL}/sign/add"
ONEKEY_API = f"{BASE_URL}/tbmall/onekeySignin1"
_run_lock: asyncio.Lock | None = None


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
    result: List[Dict[str, str]] = []
    if isinstance(raw, list):
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


def _headers(session: requests.Session, referer: str = BASE_URL) -> Dict[str, str]:
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
        "Origin": BASE_URL,
    })
    return dict(session.headers)


def _json(response: requests.Response) -> dict:
    try:
        value = response.json()
        return value if isinstance(value, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def _extract_tbs(response: requests.Response) -> str:
    body = _json(response)
    for value in (body.get("tbs"), (body.get("data") or {}).get("tbs") if isinstance(body.get("data"), dict) else None):
        if value:
            return str(value).strip()
    match = re.search(r'"tbs"\s*:\s*"([^"]+)"', response.text or "")
    return match.group(1).strip() if match else ""


def _page_count(content: str) -> int:
    matches = re.findall(r'(?:[?&]pn=|pn%3D)(\d+)[^>]{0,80}>\s*尾页', content or "", re.I)
    if matches:
        return max(1, max(int(item) for item in matches))
    matches = re.findall(r'[?&]pn=(\d+)', content or "", re.I)
    return max([1, *[int(item) for item in matches]]) if matches else 1


def _bars(content: str) -> List[str]:
    names = []
    for match in re.finditer(r'href=["\']/f\?kw=([^"\']+)["\'][^>]*\btitle=["\']([^"\']+)', content or "", re.I):
        title = html.unescape(match.group(2)).strip()
        # 贴吧关注页声明 charset=GBK，标题偶尔会被浏览器按 UTF-8 替换成“�”；
        # kw 参数本身是 GBK 百分号编码，优先从 URL 还原真实吧名。
        try:
            encoded_name = unquote_to_bytes(match.group(1)).decode("gb18030")
        except (UnicodeDecodeError, ValueError):
            encoded_name = html.unescape(unquote(match.group(1))).strip()
        name = encoded_name.strip() or title
        if "�" in name:
            name = title
        if name and name not in names:
            names.append(name)
    return names


def _message(body: dict, text: str = "") -> str:
    for key in ("message", "msg", "error"):
        if body.get(key):
            return str(body[key]).strip()
    return str(text or "").strip()[:180]


def _already_signed(text: str) -> bool:
    value = str(text or "").lower()
    if any(marker in value for marker in ("未登录", "尚未", "不能", "未签到", "没有签到", "not signed", "not checked in")):
        return False
    return any(marker in value for marker in ("已签到", "已经签到", "签过到", "已经签过", "重复签到", "already signed", "already checked in"))


def _body_from_text(text: str) -> dict:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _bar_result(name: str, status: int, body: dict, text: str = "") -> dict:
    """Only a successful HTTP response and an explicit sign-in receipt confirm a bar."""
    code = body.get("no")
    message = _message(body, text)
    valid_code = type(code) in (int, str)
    if isinstance(code, str):
        code = code.strip()
    if status in (200, 201):
        # Only structured receipts can confirm a sign-in. HTML/login/error pages
        # mentioning "already signed" are not successful sign-in responses.
        if (valid_code and code in (1101, "1101")) or (
            ("no" not in body or valid_code and code in (0, "0"))
            and _already_signed(_message(body))
        ):
            return {"name": name, "status": "already", "message": "今天已签到"}
        if valid_code and code in (0, "0"):
            return {"name": name, "status": "success", "message": "签到成功"}
    reason = (f"签到请求失败：HTTP {status}" if status not in (200, 201)
              else message or "未返回明确的签到结果")
    return {"name": name, "status": "failed", "message": reason}


def _signin_result(name: str, bars: List[str], bar_results: List[dict],
                   summary_status: int | None, body: dict, text: str = "") -> Dict[str, Any]:
    # Missing receipts remain unconfirmed. A final one-key response cannot tell
    # us which named bar succeeded, and must not overwrite earlier sign receipts.
    receipts = {item["name"]: item for item in bar_results}
    details = [receipts.get(bar) or {"name": bar, "status": "failed", "message": "未取得签到回执"} for bar in bars]
    newly = [item["name"] for item in details if item["status"] == "success"]
    already = [item["name"] for item in details if item["status"] == "already"]
    signed = [item["name"] for item in details if item["status"] in {"success", "already"}]
    failed = [item["name"] for item in details if item["status"] == "failed"]

    def count(key):
        value = body.get(key)
        if type(value) is int and value >= 0:
            return value
        if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
            return int(value.strip())
        return None

    summary_signed = count("signedForumAmount") or 0
    counts = [count(key) for key in ("signedForumAmount", "signedForumAmountFail", "unsignedForumAmount")]
    empty_confirmed = (summary_status == 200 and not bars
                       and (counts == [0, 0, 0] or
                            "there is no forum" in text.lower() and
                            not any(key in body and count(key) != 0 for key in
                                    ("signedForumAmount", "signedForumAmountFail", "unsignedForumAmount"))))
    ok = (bool(bars) and not failed) or empty_confirmed
    if bars:
        message = f"关注 {len(bars)} 个吧，已签到 {len(signed)} 个（本次 {len(newly)}，此前 {len(already)}），失败/未确认 {len(failed)} 个"
        if summary_status is not None and summary_status != 200:
            message += f"；一键接口 HTTP {summary_status}，以上按逐吧回执统计"
        elif failed and summary_signed:
            message += f"；一键接口报告签到 {summary_signed} 个，未据此猜测具体吧名"
    else:
        message = "未关注贴吧，无需签到" if empty_confirmed else "未获取到可确认的贴吧签到结果"
    return {"ok": ok, "already": bool(bars) and len(already) == len(bars), "name": name,
            "message": message, "signed": len(signed), "new_signed": len(newly),
            "already_count": len(already), "failed": len(failed), "unsigned": len(failed),
            "bars": len(bars), "bar_results": details, "signed_bars": signed,
            "newly_signed_bars": newly, "already_bars": already, "failed_bars": failed,
            "summary_signed": summary_signed}


def _bar_names(names: List[str]) -> str:
    return f"{len(names)} 个：" + "、".join(names) if names else "0 个"


def _display_result(item: dict) -> str:
    lines = [f"{item.get('name', '账号')} · {item.get('message', '')}"]
    if "bar_results" in item:
        lines.extend(("本次签到：" + _bar_names(item.get("newly_signed_bars", [])),
                      "此前已签到：" + _bar_names(item.get("already_bars", [])),
                      "失败/未确认：" + _bar_names(item.get("failed_bars", []))))
    return "\n".join(lines)


def _notice_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _notice_result(item: dict) -> str:
    """Keep push notifications short; full forum receipts stay in the records."""
    status = ("已签到" if item.get("already") else "签到成功") if item.get("ok") else "签到失败"
    lines = [f"{_notice_text(item.get('name') or '账号', 40)} · {status}"]
    if not item.get("bars"):
        lines.append(_notice_text(item.get("message") or "未取得签到结果", 120))
        return "\n".join(lines)
    lines.append(f"已签到 {item.get('signed', 0)}/{item['bars']}"
                 f"（本次 {item.get('new_signed', 0)}，此前 {item.get('already_count', 0)}）"
                 f" · 失败/未确认 {item.get('failed', 0)}")
    failed = item.get("failed_bars", [])
    if failed:
        names = "、".join(_notice_text(name, 16) for name in failed[:3])
        if len(failed) > 3:
            names += f" 等 {len(failed)} 个"
        lines.append("失败/未确认：" + names)
        reason = next((entry.get("message") for entry in item.get("bar_results", [])
                       if entry.get("status") == "failed" and entry.get("message")), "")
        if reason:
            lines.append("原因：" + _notice_text(reason, 80))
    return "\n".join(lines)


def _merge_signin_results(previous: dict, retry: dict) -> dict:
    """Preserve confirmed HTTP receipts when the browser retries the account."""
    if not previous.get("bar_results"):
        return retry
    receipts = {item["name"]: item for item in previous["bar_results"]}
    for item in retry.get("bar_results", []):
        current = receipts.get(item["name"])
        if not current or current["status"] == "failed":
            receipts[item["name"]] = item
    result = _signin_result(previous["name"], list(receipts), list(receipts.values()), None, {})
    result["browser_fallback"] = True
    result["summary_signed"] = retry.get("summary_signed", previous.get("summary_signed", 0))
    if not retry.get("ok"):
        result["message"] += "；浏览器重试：" + str(retry.get("message") or "未完成")
    return result


def _signin_one(account: Dict[str, str], delay: int, timeout: int, log=None) -> Dict[str, Any]:
    name = account.get("name") or "默认账号"
    bars: List[str] = []
    bar_results: List[dict] = []
    ready = False
    session = requests.Session()
    session.headers.update(_headers(session))
    try:
        session.headers["Cookie"] = account["cookie"]
        userinfo = session.get(USERINFO_API, params={"_": int(time.time() * 1000)}, timeout=timeout)
        user_text = userinfo.text or ""
        if userinfo.status_code != 200 or "session_id" not in user_text:
            return {"ok": False, "name": name, "message": "Cookie 已失效或未登录贴吧"}

        tbs_response = session.get(TBS_API, timeout=timeout)
        tbs = _extract_tbs(tbs_response)
        if tbs_response.status_code != 200 or not tbs:
            return {"ok": False, "name": name, "message": "获取 TBS 令牌失败"}

        first = session.get(MYLIKE_URL, timeout=timeout)
        if first.status_code != 200:
            return {"ok": False, "name": name, "message": f"获取关注贴吧列表失败：HTTP {first.status_code}"}
        pages = _page_count(first.text)
        bars = _bars(first.text)
        for page in range(2, pages + 1):
            current = session.get(MYLIKE_URL, params={"pn": page}, timeout=timeout)
            if current.status_code != 200:
                return {"ok": False, "name": name, "message": f"获取关注贴吧第 {page} 页失败：HTTP {current.status_code}，未开始签到"}
            bars.extend(_bars(current.text))
        bars = list(dict.fromkeys(bars))
        ready = True
        if log:
            log.info("[百度贴吧签到] [%s] 获取关注贴吧 %d 个，共 %d 页", name, len(bars), pages)

        for bar in bars:
            response = session.post(SIGN_API, data={"ie": "utf-8", "kw": bar, "tbs": tbs}, timeout=timeout)
            bar_results.append(_bar_result(bar, response.status_code, _json(response), response.text))
            if delay:
                time.sleep(delay)

        try:
            summary = session.post(ONEKEY_API, data={"ie": "utf-8", "tbs": tbs}, timeout=timeout)
            return _signin_result(name, bars, bar_results, summary.status_code, _json(summary), summary.text or "")
        except requests.RequestException:
            return _signin_result(name, bars, bar_results, 0, {}, "")
    except requests.RequestException as exc:
        # 某些运行环境的 Python TLS 出站链路不可达，但同机 Chromium 可正常访问贴吧。
        # 标记网络错误，调用方随后使用平台浏览器携带同一 Cookie 重试完整流程。
        result = _signin_result(name, bars, bar_results, 0, {}) if ready else {"ok": False, "name": name}
        message = f"网络请求失败：{exc}"
        result["message"] = f"{result['message']}；{message}" if ready else message
        result["network_error"] = True
        return result
    except Exception as exc:  # noqa: BLE001
        result = _signin_result(name, bars, bar_results, 0, {}) if ready else {"ok": False, "name": name}
        message = f"签到处理失败：{exc}"
        result["message"] = f"{result['message']}；{message}" if ready else message
        return result
    finally:
        session.close()


async def _browser_signin_one(account: Dict[str, str], delay: int, timeout: int, browser, log=None) -> Dict[str, Any]:
    """用平台浏览器重试贴吧签到，解决 Python TLS/出口不可达但 Chromium 可访问的环境。"""
    name = account.get("name") or "默认账号"
    out: Dict[str, Any] = {"user": None, "tbs": None, "likes": [], "bars": [],
                           "signs": [], "summary": None, "ready": False, "error": ""}

    async def action(page):
        """通过浏览器上下文的 APIRequestContext 发起同源请求。

        页面内 fetch 在部分 CF/贴吧响应重定向时会被 CORS 拦截；
        APIRequestContext 仍使用同一浏览器 Cookie，但不受页面 CORS 限制。
        """
        base = "https://tieba.baidu.com"
        request_ctx = getattr(page, "request", None)
        if request_ctx is None:
            request_ctx = page.context.request

        async def request(path: str, *, method: str = "GET", data: Dict[str, str] | None = None) -> Dict[str, Any]:
            url = f"{base}{path}"
            request_args = {"timeout": 30_000}
            response = await (
                # Playwright 的 ``data`` 会按 JSON/原始载荷处理；贴吧接口要求
                # application/x-www-form-urlencoded，必须使用 ``form``。
                request_ctx.post(url, form=data or {}, **request_args)
                if method == "POST"
                else request_ctx.get(url, **request_args)
            )
            try:
                text = await response.text()
            except UnicodeDecodeError:
                # 贴吧关注列表仍可能返回 GBK/GB18030，Playwright 的 response.text
                # 默认严格按 UTF-8 解码会直接抛异常，导致整轮签到中断。
                raw = await response.body()
                text = raw.decode("gb18030", errors="replace")
            return {"status": response.status, "text": text}

        try:
            out["user"] = await request("/f/user/json_userinfo?_=" + str(int(time.time() * 1000)))
            if out["user"]["status"] != 200 or "session_id" not in out["user"]["text"]:
                raise ValueError("Cookie 已失效或未登录贴吧")
            out["tbs"] = await request("/dc/common/tbs?_=" + str(int(time.time() * 1000)))
            tbs_text = str(out["tbs"].get("text") or "")
            tbs_body = _body_from_text(tbs_text)
            tbs_data = tbs_body.get("data") if isinstance(tbs_body.get("data"), dict) else {}
            tbs = str(tbs_body.get("tbs") or tbs_data.get("tbs") or "").strip()
            if not tbs:
                tbs_match = re.search(r'"tbs"\s*:\s*"([^"]+)"', tbs_text)
                tbs = tbs_match.group(1).strip() if tbs_match else ""
            if out["tbs"]["status"] != 200 or not tbs:
                raise ValueError("获取 TBS 令牌失败")
            first = await request("/f/like/mylike")
            if first["status"] != 200:
                raise ValueError(f"获取关注贴吧列表失败：HTTP {first['status']}")
            out["likes"].append(first)
            page_count = _page_count(first.get("text", ""))
            for page_no in range(2, page_count + 1):
                like = await request(f"/f/like/mylike?pn={page_no}")
                if like["status"] != 200:
                    raise ValueError(f"获取关注贴吧第 {page_no} 页失败：HTTP {like['status']}，未开始签到")
                out["likes"].append(like)

            bars: List[str] = []
            for like in out["likes"]:
                for value in _bars(like.get("text", "")):
                    if value not in bars:
                        bars.append(value)
            out["bars"] = bars
            out["ready"] = True
            if log:
                log.info("[百度贴吧签到] [%s] 获取关注贴吧 %d 个，共 %d 页", name, len(bars), page_count)
            for bar in bars:
                receipt = await request("/sign/add", method="POST", data={"ie": "utf-8", "kw": bar, "tbs": tbs})
                out["signs"].append({"name": bar, **receipt})
                if delay > 0:
                    await asyncio.sleep(int(delay))
            out["summary"] = await request("/tbmall/onekeySignin1", method="POST", data={"ie": "utf-8", "tbs": tbs})
        except Exception as error:  # noqa: BLE001
            out["error"] = f"{type(error).__name__}: {error}"
        return out

    try:
        # BrowserService 会把字符串 Cookie 注入为上下文级请求头，HttpOnly Cookie 也能携带。
        payload = await browser.run(
            USERINFO_API,
            action,
            headless=True,
            timeout=max(120, min(600, int(timeout) * 10)),
            cookies=account["cookie"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        )
    except Exception as exc:  # noqa: BLE001
        # The browser can fail after some bars were signed. Keep those receipts.
        out["error"] = f"{type(exc).__name__}: {exc}"
        payload = out
    if not isinstance(payload, dict):
        return {"ok": False, "name": name, "message": "浏览器签到未返回有效结果"}
    if not payload.get("ready"):
        return {"ok": False, "name": name, "message": f"浏览器请求失败：{payload.get('error')}"}
    bar_results = []
    for item in payload.get("signs") or []:
        text = str(item.get("text") or "")
        bar_results.append(_bar_result(item["name"], int(item.get("status") or 0), _body_from_text(text), text))
    summary = payload.get("summary") or {}
    summary_status = int(summary.get("status") or 0)
    summary_text = str(summary.get("text") or "")
    result = _signin_result(name, payload.get("bars") or [], bar_results,
                            summary_status, _body_from_text(summary_text), summary_text)
    result["browser_fallback"] = True
    if payload.get("error") and not result["ok"]:
        result["message"] += f"；浏览器请求中断：{payload['error']}"
    return result


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
        ctx.log.info("[百度贴吧签到] 已将残留顶层 Cookie 转入逐账号列表")
    elif legacy_cookie:
        ctx.update_config({"cookie": ""})
        ctx.log.info("[百度贴吧签到] 已清理残留顶层 Cookie 配置")
    if isinstance(raw_accounts, str) and normalized_accounts and not legacy_cookie:
        ctx.update_config({"accounts": normalized_accounts})
        ctx.log.info("[百度贴吧签到] 已将旧账号 Cookie 文本转换为逐账号列表")
    _run_lock = asyncio.Lock()
    scheduled_jobs = []

    async def save_results(results: List[Dict[str, Any]], source: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history = await ctx.storage.get("history", [])
        if not isinstance(history, list):
            history = []
        for result in results:
            history.append({"time": stamp, "source": source, **result})
        history = history[-100:]
        await ctx.storage.set("history", history)
        await ctx.storage.set("last_result", {"time": stamp, "source": source, "results": results})
        ok_count = sum(bool(item.get("ok")) for item in results)
        ctx.update_config({
            "last_result": f"{stamp} · 成功 {ok_count}/{len(results)}\n" + "\n\n".join(_display_result(item) for item in results),
            "history": "\n\n".join(f"{item['time']} · {_display_result(item)}" for item in reversed(history[-10:])),
        })

    async def run_once(source: str) -> Dict[str, Any]:
        assert _run_lock is not None
        if _run_lock.locked():
            return {"ok": False, "message": "百度贴吧签到任务正在运行"}
        async with _run_lock:
            accounts = _accounts(ctx.config.get("accounts"))
            if not accounts:
                result = {"ok": False, "message": "未配置贴吧 Cookie"}
                await save_results([result], source)
                ctx.log.error("[百度贴吧签到] %s", result["message"])
                return result
            delay = _bounded_int(ctx.config.get("delay"), 3, 0, 15)
            timeout = _bounded_int(ctx.config.get("timeout"), 30, 5, 120)
            ctx.log.info("[百度贴吧签到] 开始执行，来源=%s，账号=%d", source, len(accounts))
            results = await asyncio.gather(*(
                asyncio.to_thread(_signin_one, account, delay, timeout, ctx.log) for account in accounts
            ))
            # Python requests 在部分 Windows/Docker 出口上会被 Baidu TLS 握手阻断，
            # 而平台 Chromium 可以正常访问；对这类网络错误逐账号切换浏览器完整重试。
            for index, result in enumerate(results):
                if not result.get("network_error") or not getattr(ctx, "browser", None):
                    continue
                ctx.log.warning("[百度贴吧签到] [%s] Python HTTP 不可达，切换平台浏览器重试", accounts[index].get("name") or f"账号 {index + 1}")
                retry = await _browser_signin_one(accounts[index], delay, timeout, ctx.browser, ctx.log)
                results[index] = _merge_signin_results(result, retry)
            await save_results(results, source)
            for item in results:
                (ctx.log.info if item.get("ok") else ctx.log.warning)("[百度贴吧签到] %s", _display_result(item))
            if ctx.config.get("notify", True):
                # Explicit rich text bypasses the platform's automatic table conversion.
                notice = "<br><br>".join(html.escape(_notice_result(item)).replace("\n", "<br>") for item in results)
                try:
                    await asyncio.wait_for(ctx.notify(notice, category="百度贴吧签到", format="rich"), timeout=30)
                except Exception as exc:  # noqa: BLE001
                    ctx.log.warning("[百度贴吧签到] 通知发送失败：%r", exc)
            ok_count = sum(bool(item.get("ok")) for item in results)
            (ctx.log.info if ok_count == len(results) else ctx.log.warning)("[百度贴吧签到] 完成：成功 %d/%d", ok_count, len(results))
            return {"ok": ok_count == len(results), "results": results,
                    "message": f"成功 {ok_count}/{len(results)}\n" + "\n\n".join(_display_result(item) for item in results)}

    @ctx.action("run_now")
    async def run_now():
        return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(request):
        return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(request):
        return {"running": bool(_run_lock and _run_lock.locked()), "last_result": await ctx.storage.get("last_result", None), "history": await ctx.storage.get("history", [])}

    if ctx.config.get("enabled", False):
        try:
            fields = _cron_fields(ctx.config.get("cron") or "5 8 * * *")
            scheduled_jobs.append(ctx.schedule_cron("百度贴吧签到·定时", lambda: run_once("定时"), **fields))
            ctx.log.info("[百度贴吧签到] 定时任务已启用：%s", ctx.config.get("cron") or "5 8 * * *")
        except ValueError as exc:
            ctx.log.error("[百度贴吧签到] Cron 配置无效：%s", exc)

    async def cleanup():
        for job in scheduled_jobs:
            try:
                if hasattr(job, "cancel"):
                    job.cancel()
            except Exception:
                pass

    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[百度贴吧签到] 插件已停用")
