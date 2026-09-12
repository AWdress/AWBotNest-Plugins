"""NodeSeek 签到（AWBotNest V2 原生实现）。"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

__plugin__ = {
    "name": "NodeSeek 签到", "id": "nodeseek_signin", "version": "0.0.2", "author": "AWdress",
    "description": "NodeSeek 论坛自动签到，支持多 Cookie、账密自动登录、Cookie 刷新和定时执行。",
    "icon": "https://raw.githubusercontent.com/SAGIRIxr/MoviePilot-Plugins/main/icons/Nodeseek_A.png",
    "changelog": "v0.0.2 新增账密自动登录\n- Cookie 失效时通过 CloakBrowser 重新登录并完成签到\n- 支持 YesCaptcha 和 2Captcha Turnstile 验证码服务\n- 登录成功后自动回写新 Cookie，多账号严格按顺序对应\n- 修正 NodeSeek 签到 API 地址和 Cloudflare 拦截识别\n\nv0.0.1 首次发布\n- 使用 AWBotNest V2 原生异步存储、生命周期、定时任务和动作接口\n- 支持多账号 Cookie、签到奖励解析、历史记录和立即签到",
    "scope": "user", "plugin_api_version": 2, "tags": ["NodeSeek", "自动签到", "论坛工具"],
    "default_enabled": False, "requirements": ["requests>=2.28"],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "发送签到通知", "section": "功能开关", "order": 2},
        "auto_save_cookie": {"type": "boolean", "default": True, "label": "自动回写新 Cookie", "help": "账密登录成功后按账号顺序更新 Cookie 配置。", "section": "功能开关", "order": 3},
        "cookies": {"type": "textarea", "default": "", "label": "NodeSeek Cookie", "help": "多账号每行一个，也支持用 & 分隔；顺序必须与账号密码一致。", "section": "账号", "order": 10, "secret": True},
        "accounts": {"type": "textarea", "default": "", "label": "账号密码", "help": "可选，Cookie 失效时自动登录。每行：用户名----密码。", "section": "账号", "order": 11, "secret": True},
        "solver_type": {"type": "select", "default": "yescaptcha", "label": "验证码服务", "options": [{"label": "YesCaptcha", "value": "yescaptcha"}, {"label": "2Captcha", "value": "2captcha"}], "section": "自动登录", "order": 20},
        "api_base_url": {"type": "string", "default": "", "label": "验证码 API 地址", "help": "留空使用所选服务的官方地址。", "section": "自动登录", "order": 21},
        "client_key": {"type": "password", "default": "", "label": "验证码 Client Key", "help": "账密登录需要 YesCaptcha 或 2Captcha Client Key。", "section": "自动登录", "order": 22, "secret": True},
        "random_reward": {"type": "boolean", "default": True, "label": "随机鸡腿奖励", "section": "签到设置", "order": 30},
        "cron": {"type": "string", "default": "0 8 * * *", "label": "签到 Cron", "help": "五段 Cron，默认每天 08:00。", "section": "签到设置", "order": 31},
        "timeout": {"type": "integer", "default": 30, "min": 5, "max": 120, "label": "请求超时（秒）", "section": "签到设置", "order": 32},
        "captcha_timeout": {"type": "integer", "default": 90, "min": 30, "max": 300, "label": "验证码超时（秒）", "section": "签到设置", "order": 33},
    },
}

SIGNIN_PAGE = "https://www.nodeseek.com/signIn.html"
ATTENDANCE_API = "https://www.nodeseek.com/api/attendance"
SITEKEY = "0x4AAAAAAAaNy7leGjewpVyR"
COOKIE_RE = re.compile(r"(?:^|;)\s*([^=;\s]+)=([^;]*)")


def _cookies(raw: str) -> List[str]:
    return [item.strip() for item in re.split(r"[&\n\r]+", str(raw or "")) if item.strip()]


def _accounts(raw: str) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        pair: Optional[Tuple[str, str]] = None
        for separator in ("----", "，", ",", "：", ":", "|", "\t"):
            if separator in line:
                pair = tuple(line.split(separator, 1))  # type: ignore[assignment]
                break
        if pair and pair[0].strip() and pair[1].strip():
            result.append({"user": pair[0].strip(), "password": pair[1].strip()})
    return result


def _is_challenge(response: requests.Response) -> bool:
    text = (response.text or "").lower()
    return bool(response.headers.get("cf-mitigated")) or response.status_code in (401, 403) or "just a moment" in text or "cf-chl" in text


def _signin_one(cookie: str, reward: bool, timeout: int) -> Dict[str, Any]:
    session = requests.Session()
    session.cookies.update(dict(COOKIE_RE.findall(cookie)))
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Accept": "application/json, text/plain, */*", "Origin": "https://www.nodeseek.com", "Referer": "https://www.nodeseek.com/board"}
    try:
        response = session.post(f"{ATTENDANCE_API}?random={'true' if reward else 'false'}", json={}, headers=headers, timeout=timeout)
        if _is_challenge(response):
            return {"ok": False, "refresh": True, "message": "Cookie 已失效或请求被 Cloudflare 拦截", "status": response.status_code}
        try:
            data = response.json()
        except ValueError:
            data = {}
        message = str(data.get("message") or data.get("msg") or (response.text or "")[:160]).strip()
        lower = message.lower()
        ok = response.status_code < 400 and (bool(data.get("success")) or any(word in lower for word in ("鸡腿", "已完成签到", "已签到", "already")))
        return {"ok": ok, "refresh": response.status_code in (401, 403) or data.get("status") == 404, "message": message or f"HTTP {response.status_code}", "status": response.status_code}
    except Exception as exc:
        return {"ok": False, "refresh": False, "message": f"请求失败：{exc}"}


def _solve_captcha(config: Dict[str, Any]) -> str:
    client_key = str(config.get("client_key") or "").strip()
    if not client_key:
        raise RuntimeError("未配置验证码 Client Key")
    solver = str(config.get("solver_type") or "yescaptcha").lower()
    base = str(config.get("api_base_url") or "").strip().rstrip("/") or ("https://api.2captcha.com" if solver == "2captcha" else "https://api.yescaptcha.com")
    request_timeout = max(10, min(120, int(config.get("timeout", 30) or 30)))
    total_timeout = max(30, min(300, int(config.get("captcha_timeout", 90) or 90)))
    payload: Dict[str, Any] = {"clientKey": client_key, "task": {"type": "TurnstileTaskProxyless", "websiteURL": SIGNIN_PAGE, "websiteKey": SITEKEY}}
    if solver != "2captcha":
        payload["softID"] = "62709"
    response = requests.post(f"{base}/createTask", json=payload, timeout=request_timeout)
    response.raise_for_status()
    created = response.json()
    if created.get("errorId"):
        raise RuntimeError(f"{created.get('errorCode') or '验证码任务创建失败'}：{created.get('errorDescription') or '未知错误'}")
    task_id = created.get("taskId")
    if not task_id:
        raise RuntimeError("验证码服务未返回 taskId")
    deadline = time.monotonic() + total_timeout
    while time.monotonic() < deadline:
        time.sleep(3)
        response = requests.post(f"{base}/getTaskResult", json={"clientKey": client_key, "taskId": task_id}, timeout=request_timeout)
        response.raise_for_status()
        result = response.json()
        if result.get("errorId"):
            raise RuntimeError(f"{result.get('errorCode') or '验证码解析失败'}：{result.get('errorDescription') or '未知错误'}")
        if result.get("status") == "ready":
            token = str((result.get("solution") or {}).get("token") or "")
            if token:
                return token
            raise RuntimeError("验证码服务返回了空令牌")
    raise RuntimeError(f"验证码在 {total_timeout} 秒内未完成")


def _browser_action(user: str, password: str, token: str, reward: bool):
    def action(page):
        try:
            page.wait_for_load_state("networkidle", timeout=60_000)
        except Exception:
            pass
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                ready = page.evaluate("()=>performance.getEntriesByType('resource').some(e=>/\\/assets\\/preLogin-[^/]*\\.js/.test(e.name))")
                if ready:
                    break
            except Exception:
                pass
            time.sleep(2)
        script = r"""
        async ({token, username, password, reward}) => {
          const out = {phase: 'start'}; let preMod = null;
          async function authHeaders() {
            try {
              const urls = performance.getEntriesByType('resource').map(e => e.name);
              const preUrl = urls.find(u => /\/assets\/preLogin-[^/]*\.js/.test(u));
              if (!preUrl) throw new Error('preLogin 模块未加载');
              if (!preMod) preMod = await import(preUrl); return await preMod.g();
            } catch (e) { out.authError = String(e); return {}; }
          }
          let headers = await authHeaders();
          const login = await fetch('/api/account/signIn', {method:'POST', credentials:'include', headers:Object.assign({'Content-Type':'application/json','x-captcha-token':token,'x-captcha-source':'turnstile'},headers), body:JSON.stringify({username,password})});
          out.loginStatus=login.status; const security=login.headers.get('x-security-token'); const csrf=login.headers.get('x-csrf-token');
          try { out.loginBody=await login.json(); } catch(e) { out.loginBody=null; }
          if (!out.loginBody || !out.loginBody.success) { out.phase='login-fail'; return out; }
          if (security) localStorage.setItem('security_token',security); if (csrf) localStorage.setItem('csrf_token',csrf);
          headers=await authHeaders();
          const attendance=await fetch('/api/attendance?random='+(reward?'true':'false'),{method:'POST',credentials:'include',headers:Object.assign({'Content-Type':'application/json'},headers),body:'{}'});
          out.attendanceStatus=attendance.status; try { out.attendanceBody=await attendance.json(); } catch(e) { out.attendanceBody=null; }
          out.phase='done'; return out;
        }
        """
        result = page.evaluate(script, {"token": token, "username": user, "password": password, "reward": reward}) or {}
        try:
            cookies = page.context.cookies()
        except Exception:
            cookies = []
        pairs = {item.get("name"): item.get("value") for item in cookies if item.get("name") and "nodeseek.com" in str(item.get("domain") or "") and item.get("name") != "cf_clearance"}
        result["cookie"] = "; ".join(f"{key}={value}" for key, value in pairs.items())
        return result
    return action


def _browser_cookie_action(reward: bool):
    def action(page):
        try:
            page.wait_for_load_state("networkidle", timeout=60_000)
        except Exception:
            pass
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                ready = page.evaluate("()=>performance.getEntriesByType('resource').some(e=>/\\/assets\\/preLogin-[^/]*\\.js/.test(e.name))")
                if ready:
                    break
            except Exception:
                pass
            time.sleep(2)
        script = r"""
        async ({reward}) => {
          const out = {};
          try {
            const urls=performance.getEntriesByType('resource').map(e=>e.name);
            const preUrl=urls.find(u=>/\/assets\/preLogin-[^/]*\.js/.test(u));
            if (!preUrl) throw new Error('preLogin 模块未加载');
            const preMod=await import(preUrl); const headers=await preMod.g();
            const response=await fetch('/api/attendance?random='+(reward?'true':'false'),{method:'POST',credentials:'include',headers:Object.assign({'Content-Type':'application/json'},headers),body:'{}'});
            out.status=response.status; try { out.body=await response.json(); } catch(e) { out.body=null; }
          } catch(e) { out.error=String(e); }
          return out;
        }
        """
        return page.evaluate(script, {"reward": reward}) or {}
    return action


async def _signin_with_browser_cookie(ctx, cookie: str, reward: bool) -> Dict[str, Any]:
    try:
        raw = await ctx.browser.run(SIGNIN_PAGE, _browser_cookie_action(reward), cookies=cookie, headless=True, timeout=120) or {}
    except Exception as exc:
        return {"ok": False, "refresh": False, "message": f"CloakBrowser Cookie 签到失败：{exc}"}
    data = raw.get("body") or {}
    message = str(data.get("message") or raw.get("error") or f"HTTP {raw.get('status')}")
    ok = bool(data.get("success")) or any(word in message.lower() for word in ("鸡腿", "已完成签到", "已签到", "already"))
    refresh = raw.get("status") in (401, 403, 404) or data.get("status") == 404
    return {"ok": ok, "refresh": refresh, "message": message}


async def _login_and_signin(ctx, account: Dict[str, str], config: Dict[str, Any], reward: bool) -> Dict[str, Any]:
    ctx.log.info("[NodeSeek签到] Cookie 失效，正在请求 Turnstile 验证令牌")
    try:
        token = await asyncio.to_thread(_solve_captcha, config)
        ctx.log.info("[NodeSeek签到] 验证令牌已获取，启动 CloakBrowser 登录")
        raw = await ctx.browser.run(SIGNIN_PAGE, _browser_action(account["user"], account["password"], token, reward), headless=True, timeout=max(60, min(300, int(config.get("captcha_timeout", 90) or 90) + 60))) or {}
    except Exception as exc:
        return {"ok": False, "message": f"自动登录失败：{exc}", "cookie": ""}
    login_body = raw.get("loginBody") or {}
    if raw.get("phase") == "login-fail" or not login_body.get("success"):
        message = str(login_body.get("message") or raw.get("authError") or f"HTTP {raw.get('loginStatus')}")
        if "email" in str(login_body.get("redirect") or "").lower():
            message = "NodeSeek 要求邮箱验证，请先用浏览器登录一次或更换干净 IP"
        return {"ok": False, "message": f"自动登录失败：{message}", "cookie": ""}
    attendance = raw.get("attendanceBody") or {}
    message = str(attendance.get("message") or f"HTTP {raw.get('attendanceStatus')}")
    ok = bool(attendance.get("success")) or any(word in message.lower() for word in ("鸡腿", "已完成签到", "已签到", "already"))
    return {"ok": ok, "message": message, "cookie": str(raw.get("cookie") or "")}


async def setup(ctx):
    state = dict(await ctx.storage.items()); active = None; scheduled = []

    async def run_once(source: str = "手动"):
        nonlocal active
        if active and not active.done(): return {"ok": False, "message": "签到任务正在运行"}
        config = dict(ctx.config or {}); cookie_list = _cookies(config.get("cookies", "")); account_list = _accounts(config.get("accounts", "")); count = max(len(cookie_list), len(account_list))
        if not count: return {"ok": False, "message": "请先配置 NodeSeek Cookie 或账号密码"}
        cookie_list.extend([""] * (count - len(cookie_list))); account_list.extend([{"user": "", "password": ""}] * (count - len(account_list)))
        timeout = max(5, min(120, int(config.get("timeout", 30) or 30))); reward = bool(config.get("random_reward", True))

        async def worker():
            nonlocal active
            rows = []; changed = False
            try:
                for index in range(count):
                    cookie = cookie_list[index]; account = account_list[index]; label = account.get("user") or f"账号 {index + 1}"
                    result = await asyncio.to_thread(_signin_one, cookie, reward, timeout) if cookie else {"ok": False, "refresh": True, "message": "未配置 Cookie"}
                    if not result["ok"] and result.get("refresh") and cookie:
                        ctx.log.info(f"[NodeSeek签到] {label} HTTP 请求被拦截，使用 CloakBrowser 复核 Cookie 并签到")
                        result = await _signin_with_browser_cookie(ctx, cookie, reward)
                    if not result["ok"] and (result.get("refresh") or not cookie):
                        if account.get("user") and account.get("password"):
                            result = await _login_and_signin(ctx, account, config, reward); new_cookie = str(result.get("cookie") or "")
                            if new_cookie:
                                cookie_list[index] = new_cookie; changed = True; ctx.log.info(f"[NodeSeek签到] {label} 登录成功，已获取新会话 Cookie")
                        else: result["message"] += "；未配置对应账号密码，无法自动刷新"
                    rows.append({"账号": label, "状态": "成功" if result["ok"] else "失败", "详情": result["message"]})
                    (ctx.log.info if result["ok"] else ctx.log.error)(f"[NodeSeek签到] {label}: {result['message']}")
                if changed:
                    await ctx.storage.set("refreshed_cookies", cookie_list)
                    if config.get("auto_save_cookie", True): ctx.update_config({"cookies": "\n".join(cookie_list)}); ctx.log.info("[NodeSeek签到] 已将刷新后的 Cookie 回写到插件配置")
                success = sum(row["状态"] == "成功" for row in rows); summary = {"时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "来源": source, "成功": success, "总数": len(rows), "rows": rows}
                state["last_result"] = summary; history = list(state.get("history", []) or []); history.insert(0, summary); state["history"] = history[:30]
                await ctx.storage.set("last_result", summary); await ctx.storage.set("history", state["history"])
                if config.get("notify", True): await ctx.notify(rows, category="NodeSeek签到")
            finally:
                active = None

        active = ctx.create_task(worker(), name="NodeSeek签到"); return {"ok": True, "message": "已开始 NodeSeek 签到"}

    @ctx.action("run_now")
    async def run_now(): return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(req): return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req): return {"running": bool(active and not active.done()), "last_result": state.get("last_result"), "history": list(state.get("history", []) or [])[:10]}

    config = dict(ctx.config or {})
    if config.get("enabled"):
        parts = str(config.get("cron", "0 8 * * *") or "0 8 * * *").split()
        if len(parts) == 5:
            kwargs = {key: value for key, value in zip(("minute", "hour", "day", "month", "day_of_week"), parts) if value != "*"}; scheduled.append(ctx.schedule(lambda: run_once("定时"), "cron", id="NodeSeek签到·定时", **kwargs)); ctx.log.info(f"[NodeSeek签到] 定时任务已启用：{config.get('cron')}")
        else: ctx.log.error(f"[NodeSeek签到] Cron 必须是五段表达式：{config.get('cron')}")

    async def cleanup():
        nonlocal active
        for job in scheduled:
            try: job.cancel() if hasattr(job, "cancel") else None
            except Exception: pass
        if active and not active.done(): active.cancel(); await asyncio.gather(active, return_exceptions=True)
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[NodeSeek签到] 插件已停用")
