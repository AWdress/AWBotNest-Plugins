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
    "version": "0.1.3",
    "author": "AWdress",
    "description": "使用百度贴吧 Cookie 自动完成关注贴吧签到，支持多账号、定时执行和结果通知。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/tieba_signin/logo.png",
    "changelog": "v0.0.1 首次发布\n- 根据百度贴吧签到流程接入 Cookie 校验、TBS 获取、关注贴吧扫描和一键签到\n- 支持逐账号配置、定时签到、立即执行、签到统计与历史记录\n- 仅依据贴吧接口返回的签到数量生成结果，不把 HTTP 成功误判为签到成功",
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

__plugin__["changelog"] = (
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
    + __plugin__["changelog"]
)


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
    return any(marker in value for marker in ("已签到", "已经签到", "签过到", "已经签过", "之前已经", "重复签到", "already signed", "already"))


def _signin_one(account: Dict[str, str], delay: int, timeout: int, log=None) -> Dict[str, Any]:
    name = account.get("name") or "默认账号"
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
            if current.status_code == 200:
                bars.extend(_bars(current.text))
        bars = list(dict.fromkeys(bars))
        if log:
            log.info("[百度贴吧签到] [%s] 获取关注贴吧 %d 个，共 %d 页", name, len(bars), pages)

        individual_failed = 0
        individual_already = 0
        for bar in bars:
            response = session.post(SIGN_API, data={"ie": "utf-8", "kw": bar, "tbs": tbs}, timeout=timeout)
            body = _json(response)
            message = _message(body, response.text)
            if _already_signed(message) or body.get("no") in (1101, "1101"):
                individual_already += 1
            elif response.status_code not in (200, 201) or (body and body.get("no") not in (None, 0, "0")):
                individual_failed += 1
            if delay:
                time.sleep(delay)

        summary = session.post(ONEKEY_API, data={"ie": "utf-8", "tbs": tbs}, timeout=timeout)
        body = _json(summary)
        text = summary.text or ""
        signed = int(body.get("signedForumAmount") or 0)
        failed = int(body.get("signedForumAmountFail") or individual_failed or 0)
        unsigned = int(body.get("unsignedForumAmount") or 0)
        success_marker = any(marker in text.lower() for marker in ("success", "forums is signed", "there is no forum"))
        already = _already_signed(text) or individual_already >= len(bars) > 0
        if already and individual_failed == 0:
            # 部分版本的一键接口会把“今日已签到”计入失败字段，不能因此误报失败。
            failed = 0
        # 一键接口 HTTP 200 不等于签到成功；例如 signed=0、fail=72 表示全部失败。
        # 只有明确签到数量、明确无关注贴吧，或接口返回无失败的成功标记时才算成功。
        completed = signed > 0 or already or (not bars and failed == 0 and unsigned == 0) or (success_marker and failed == 0)
        if summary.status_code != 200 or (not body and not success_marker and not already) or not completed or failed > 0:
            return {"ok": False, "name": name, "message": _message(body, text) or f"一键签到失败：HTTP {summary.status_code}", "signed": signed, "failed": failed, "unsigned": unsigned}
        return {"ok": True, "already": already and signed == 0, "name": name, "message": "今天已经签到" if already and signed == 0 else "贴吧签到完成", "signed": signed, "failed": failed, "unsigned": unsigned, "bars": len(bars)}
    except requests.RequestException as exc:
        # 某些运行环境的 Python TLS 出站链路不可达，但同机 Chromium 可正常访问贴吧。
        # 标记网络错误，调用方随后使用平台浏览器携带同一 Cookie 重试完整流程。
        return {"ok": False, "network_error": True, "name": name, "message": f"网络请求失败：{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "name": name, "message": f"签到处理失败：{exc}"}


async def _browser_signin_one(account: Dict[str, str], delay: int, timeout: int, browser, log=None) -> Dict[str, Any]:
    """用平台浏览器重试贴吧签到，解决 Python TLS/出口不可达但 Chromium 可访问的环境。"""
    name = account.get("name") or "默认账号"

    async def action(page):
        """通过浏览器上下文的 APIRequestContext 发起同源请求。

        页面内 fetch 在部分 CF/贴吧响应重定向时会被 CORS 拦截；
        APIRequestContext 仍使用同一浏览器 Cookie，但不受页面 CORS 限制。
        """
        base = "https://tieba.baidu.com"
        out: Dict[str, Any] = {"user": None, "tbs": None, "likes": [], "signs": [], "summary": None, "error": ""}
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
            out["tbs"] = await request("/dc/common/tbs?_=" + str(int(time.time() * 1000)))
            first = await request("/f/like/mylike")
            out["likes"].append(first)
            page_count = 1
            match = re.search(r"(?:[?&]pn=|pn%3D)(\d+)[^>]{0,80}>\s*尾页", first.get("text", ""), re.I)
            if match:
                page_count = max(1, int(match.group(1)))
            else:
                pages = [int(value) for value in re.findall(r"[?&]pn=(\d+)", first.get("text", ""), re.I)]
                if pages:
                    page_count = max(1, *pages)
            for page_no in range(2, page_count + 1):
                out["likes"].append(await request(f"/f/like/mylike?pn={page_no}"))

            tbs_text = str((out["tbs"] or {}).get("text") or "")
            tbs = ""
            try:
                tbs_body = json.loads(tbs_text)
                if isinstance(tbs_body, dict):
                    tbs = str(tbs_body.get("tbs") or (tbs_body.get("data") or {}).get("tbs") or "")
            except (TypeError, ValueError):
                pass
            if not tbs:
                tbs_match = re.search(r'"tbs"\s*:\s*"([^"]+)"', tbs_text)
                tbs = tbs_match.group(1) if tbs_match else ""

            bars: List[str] = []
            for like in out["likes"]:
                for value in _bars(like.get("text", "")):
                    if value not in bars:
                        bars.append(value)
            for bar in bars:
                out["signs"].append(await request("/sign/add", method="POST", data={"ie": "utf-8", "kw": bar, "tbs": tbs}))
                if delay > 0:
                    await asyncio.sleep(int(delay))
            out["summary"] = await request("/tbmall/onekeySignin1", method="POST", data={"ie": "utf-8", "tbs": tbs})
            out["barCount"] = len(bars)
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
        return {"ok": False, "name": name, "message": f"浏览器签到失败：{exc}"}
    if not isinstance(payload, dict):
        return {"ok": False, "name": name, "message": "浏览器签到未返回有效结果"}
    if payload.get("error"):
        return {"ok": False, "name": name, "message": f"浏览器请求失败：{payload.get('error')}"}

    user = payload.get("user") or {}
    user_text = str(user.get("text") or "")
    if int(user.get("status") or 0) != 200 or "session_id" not in user_text:
        return {"ok": False, "name": name, "message": "Cookie 已失效或未登录贴吧"}
    tbs = payload.get("tbs") or {}
    tbs_text = str(tbs.get("text") or "")
    tbs_body: dict = {}
    try:
        value = json.loads(tbs_text)
        if isinstance(value, dict):
            tbs_body = value
    except (TypeError, ValueError):
        pass
    sign_results = payload.get("signs") or []
    individual_failed = 0
    individual_already = 0
    for item in sign_results:
        item = item or {}
        text = str(item.get("text") or "")
        try:
            item_body = json.loads(text)
        except (TypeError, ValueError):
            item_body = {}
        if _already_signed(text) or (isinstance(item_body, dict) and item_body.get("no") in (1101, "1101")):
            individual_already += 1
        elif int((item or {}).get("status") or 0) not in (200, 201):
            individual_failed += 1
    summary = payload.get("summary") or {}
    summary_status = int(summary.get("status") or 0)
    summary_text = str(summary.get("text") or "")
    try:
        body = json.loads(summary_text)
        if not isinstance(body, dict):
            body = {}
    except (TypeError, ValueError):
        body = {}
    signed = int(body.get("signedForumAmount") or 0)
    failed = int(body.get("signedForumAmountFail") or individual_failed or 0)
    unsigned = int(body.get("unsignedForumAmount") or 0)
    bar_count = int(payload.get("barCount") or 0)
    success_marker = any(marker in summary_text.lower() for marker in ("success", "forums is signed", "there is no forum"))
    already = _already_signed(summary_text) or individual_already >= bar_count > 0
    if already and individual_failed == 0:
        failed = 0
    completed = signed > 0 or already or (not bar_count and failed == 0 and unsigned == 0) or (success_marker and failed == 0)
    if summary_status != 200 or (not body and not success_marker and not already) or not completed or failed > 0:
        return {"ok": False, "name": name, "message": _message(body, summary_text) or f"一键签到失败：HTTP {summary_status}", "signed": signed, "failed": failed, "unsigned": unsigned}
    return {"ok": True, "already": already and signed == 0, "name": name, "message": "今天已经签到" if already and signed == 0 else "贴吧签到完成", "signed": signed, "failed": failed, "unsigned": unsigned, "bars": bar_count, "browser_fallback": True}


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
            "last_result": f"{stamp} · 成功 {ok_count}/{len(results)}",
            "history": "\n".join(f"{item['time']} · {item.get('name', '')} · {item.get('message', '')}" for item in reversed(history[-10:])),
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
                results[index] = await _browser_signin_one(accounts[index], delay, timeout, ctx.browser, ctx.log)
            await save_results(results, source)
            rows = []
            for item in results:
                rows.append({"账号": item.get("name", "-"), "状态": "已签到" if item.get("already") else ("成功" if item.get("ok") else "失败"), "已签到": item.get("signed", "-"), "失败": item.get("failed", "-"), "未签到": item.get("unsigned", "-"), "详情": item.get("message", "")})
            if ctx.config.get("notify", True):
                try:
                    await asyncio.wait_for(ctx.notify(rows, category="百度贴吧签到"), timeout=30)
                except Exception as exc:  # noqa: BLE001
                    ctx.log.warning("[百度贴吧签到] 通知发送失败：%r", exc)
            ok_count = sum(bool(item.get("ok")) for item in results)
            (ctx.log.info if ok_count == len(results) else ctx.log.warning)("[百度贴吧签到] 完成：成功 %d/%d", ok_count, len(results))
            return {"ok": ok_count == len(results), "results": results, "message": f"成功 {ok_count}/{len(results)}"}

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
