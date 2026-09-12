"""NodeSeek 签到（AWBotNest V2 原生实现）。"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

__plugin__ = {
    "name": "NodeSeek 签到", "id": "nodeseek_signin", "version": "0.0.8", "author": "AWdress",
    "description": "NodeSeek 论坛自动签到，支持多 Cookie、账密自动登录、Cookie 刷新和定时执行。",
    "icon": "https://raw.githubusercontent.com/SAGIRIxr/MoviePilot-Plugins/main/icons/Nodeseek_A.png",
    "changelog": "v0.0.8 改进多账号账密配置\n- 账号密码改为逐账号添加和删除，不再填写整段分隔文本\n- 每个密码独立隐藏并可按需显示，旧格式启动时自动迁移且不丢失账号\n- 保留多 Cookie 按账号顺序对应和失效后自动登录逻辑\n\nv0.0.7 修复重复签到识别与通知\n- HTTP 400 但提示今天已签到或请勿重复操作时按成功处理\n- 通知发送增加开始、完成、跳过与失败日志，避免通知异常静默\n- 立即签到和后台任务异常均输出明确日志\n\nv0.0.6 修复 Docker Turnstile 超时\n- 使用登录页原生 Turnstile 控件及站点参数，不再额外创建缺少 action/cData 的验证控件\n- 原生令牌未签发时受控重置并刷新页面重试一次\n- Docker 检测到 Xvfb 显示器时自动改用虚拟有头 CloakBrowser，并固定持久指纹\n\nv0.0.5 适配平台敏感配置规范\n- Cookie 与账号密码改为受控显示的 password 字段，避免公开接口泄露\n- 多账号改用“ & ”分隔的单行格式，并自动迁移旧换行配置\n- 移除对平台 Settings 的直接修改，停用的打码配置通过隐藏兼容字段安全清空\n\nv0.0.4 改用浏览器原生验证\n- 移除 YesCaptcha、2Captcha、验证码 API 地址和 Client Key 配置\n- 使用真实 CloakBrowser 持久会话完成 Cloudflare 页面验证并获取 NodeSeek Turnstile 登录令牌\n- Cookie 失效后直接通过账密自动登录，不再依赖第三方打码服务\n- Cookie 与账号密码改为直接显示，首次启用自动补齐默认配置\n\nv0.0.3 修正独立运行与配置保存\n- 调整为独立插件，不再为每个 Telegram 用户重复创建签到实例\n- 按平台 schema 规范修正多行密钥和数值字段，解决账密被错误填充及保存失败\n\nv0.0.2 新增账密自动登录\n- Cookie 失效时通过 CloakBrowser 重新登录并完成签到\n- 登录成功后自动回写新 Cookie，多账号严格按顺序对应\n- 修正 NodeSeek 签到 API 地址和 Cloudflare 拦截识别\n\nv0.0.1 首次发布\n- 使用 AWBotNest V2 原生异步存储、生命周期、定时任务和动作接口\n- 支持多账号 Cookie、签到奖励解析、历史记录和立即签到",
    "scope": "standalone", "plugin_api_version": 2, "tags": ["NodeSeek", "自动签到", "论坛工具"],
    "render_mode": "vue",
    "default_enabled": False, "requirements": ["requests>=2.28", "cloakbrowser>=0.5.10"],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "发送签到通知", "section": "功能开关", "order": 2},
        "auto_save_cookie": {"type": "boolean", "default": True, "label": "自动回写新 Cookie", "help": "账密登录成功后按账号顺序更新 Cookie 配置。", "section": "功能开关", "order": 3},
        "cookies": {"type": "password", "default": "", "label": "NodeSeek Cookie", "help": "多账号使用“ & ”分隔，顺序必须与账号密码一致；可用显示按钮受控查看。", "section": "账号", "cols": 12, "order": 10},
        "accounts": {
            "type": "list", "default": [], "label": "登录账号", "item_label": "账号",
            "secret": True, "help": "逐个添加登录账号；Cookie 失效时按顺序自动登录并刷新对应 Cookie。",
            "section": "账号", "cols": 12, "order": 11,
            "fields": {
                "user": {"type": "string", "label": "用户名或邮箱"},
                "password": {"type": "password", "label": "密码"},
            },
        },
        "solver_type": {"type": "string", "default": "", "label": "旧验证服务", "show_if": {"legacy_solver_visible": True}, "section": "兼容迁移", "order": 90},
        "api_base_url": {"type": "string", "default": "", "label": "旧验证地址", "show_if": {"legacy_solver_visible": True}, "section": "兼容迁移", "order": 91},
        "client_key": {"type": "password", "default": "", "label": "旧验证密钥", "show_if": {"legacy_solver_visible": True}, "section": "兼容迁移", "order": 92},
        "browser_login": {"type": "info", "default": "Cookie 失效时自动使用 CloakBrowser 完成验证并重新登录，无需第三方验证码服务。", "label": "自动登录方式", "section": "自动登录", "cols": 12, "order": 20},
        "random_reward": {"type": "boolean", "default": True, "label": "随机鸡腿奖励", "section": "签到设置", "order": 30},
        "cron": {"type": "string", "default": "0 8 * * *", "label": "签到 Cron", "help": "五段 Cron，默认每天 08:00。", "section": "签到设置", "order": 31},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "step": 1, "label": "请求超时（秒）", "section": "签到设置", "order": 32},
        "captcha_timeout": {"type": "number", "default": 90, "min": 30, "max": 300, "step": 1, "label": "浏览器验证超时（秒）", "section": "签到设置", "order": 33},
        "run_now": {"type": "action", "label": "立即签到", "action": "run_now", "section": "操作", "cols": 6, "order": 40},
        "last_result": {"type": "info", "default": "尚未运行", "label": "最近结果", "section": "运行状态", "cols": 12, "order": 50},
        "history": {"type": "info", "default": "暂无记录", "label": "最近签到记录", "section": "运行状态", "cols": 12, "order": 51},
    },
}

SIGNIN_PAGE = "https://www.nodeseek.com/signIn.html"
ATTENDANCE_API = "https://www.nodeseek.com/api/attendance"
COOKIE_RE = re.compile(r"(?:^|;)\s*([^=;\s]+)=([^;]*)")


def _cookies(raw: str) -> List[str]:
    return [item.strip() for item in re.split(r"(?:\r?\n|\s+&\s+)", str(raw or "")) if item.strip()]


def _accounts(raw: Any) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            user = str(item.get("user") or item.get("username") or "").strip()
            password = str(item.get("password") or "")
            if user and password:
                result.append({"user": user, "password": password})
        return result
    for line in re.split(r"(?:\r?\n|\s+&\s+)", str(raw or "")):
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


def _signin_status(data: Dict[str, Any], message: str) -> Tuple[bool, bool]:
    """返回 ``(签到有效, 已经签到)``，不受响应 HTTP 状态码误导。"""
    lower = str(message or "").lower()
    already = any(
        marker in lower
        for marker in (
            "已完成签到", "已经完成签到", "今日已签到", "今天已签到",
            "已签到", "请勿重复操作", "already",
        )
    )
    return bool(data.get("success")) or already or "鸡腿" in lower, already


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
        ok, already = _signin_status(data, message)
        return {"ok": ok, "already": already, "refresh": not ok and (response.status_code in (401, 403) or data.get("status") == 404), "message": message or f"HTTP {response.status_code}", "status": response.status_code}
    except Exception as exc:
        return {"ok": False, "refresh": False, "message": f"请求失败：{exc}"}


def _browser_action(user: str, password: str, reward: bool, captcha_timeout: int):
    def action(page):
        def wait_app_ready(limit: int = 40) -> bool:
            deadline = time.monotonic() + limit
            while time.monotonic() < deadline:
                try:
                    if page.evaluate("()=>performance.getEntriesByType('resource').some(e=>/\\/assets\\/preLogin-[^/]*\\.js/.test(e.name))"):
                        return True
                except Exception:
                    pass
                time.sleep(1)
            return False

        try:
            page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            pass
        if not wait_app_ready():
            return {"phase": "cf-fail", "captchaError": "Cloudflare 页面验证未完成，NodeSeek 登录页面尚未加载"}
        script = r"""
        async ({username, password, reward, captchaTimeout}) => {
          const out = {phase: 'start'}; let preMod = null;
          async function turnstileToken() {
            const readToken = () => {
              const field = document.querySelector('input[name="cf-turnstile-response"], textarea[name="cf-turnstile-response"]');
              if (field && field.value) return field.value;
              try { return window.turnstile && window.turnstile.getResponse ? window.turnstile.getResponse() : ''; } catch (_) { return ''; }
            };
            const started = Date.now(); let reset = false;
            while (Date.now() - started < captchaTimeout * 1000) {
              const current = readToken();
              if (current) return current;
              if (!reset && Date.now() - started > 12000 && window.turnstile?.reset) {
                try { window.turnstile.reset(); reset = true; out.nativeReset = true; } catch (_) {}
              }
              await new Promise(resolve => setTimeout(resolve, 500));
            }
            throw new Error('登录页原生 Turnstile 未在限定时间内签发令牌');
          }
          async function authHeaders() {
            try {
              const urls = performance.getEntriesByType('resource').map(e => e.name);
              const preUrl = urls.find(u => /\/assets\/preLogin-[^/]*\.js/.test(u));
              if (!preUrl) throw new Error('preLogin 模块未加载');
              if (!preMod) preMod = await import(preUrl); return await preMod.g();
            } catch (e) { out.authError = String(e); return {}; }
          }
          try { localStorage.removeItem('security_token'); localStorage.removeItem('csrf_token'); } catch (_) {}
          let token = '';
          try { token = await turnstileToken(); } catch (e) { out.phase='captcha-fail'; out.captchaError=String(e); return out; }
          if (!token) { out.phase='captcha-fail'; out.captchaError='Turnstile 返回空令牌'; return out; }
          out.hasCaptchaToken = true;
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
        first_timeout = min(30, captcha_timeout)
        result = page.evaluate(script, {"username": user, "password": password, "reward": reward, "captchaTimeout": first_timeout}) or {}
        if result.get("phase") == "captcha-fail" and captcha_timeout > first_timeout:
            try:
                page.reload(wait_until="domcontentloaded", timeout=60_000)
                if wait_app_ready(30):
                    result = page.evaluate(script, {
                        "username": user,
                        "password": password,
                        "reward": reward,
                        "captchaTimeout": captcha_timeout - first_timeout,
                    }) or {}
                    result["pageReloaded"] = True
            except Exception as exc:
                result = {"phase": "captcha-fail", "captchaError": f"原生 Turnstile 页面刷新失败：{exc}"}
        try:
            cookies = page.context.cookies()
        except Exception:
            cookies = []
        pairs = {item.get("name"): item.get("value") for item in cookies if item.get("name") and "nodeseek.com" in str(item.get("domain") or "") and item.get("name") != "cf_clearance"}
        result["cookie"] = "; ".join(f"{key}={value}" for key, value in pairs.items())
        return result
    return action


def _cookie_items(raw: str) -> List[Dict[str, str]]:
    return [
        {"name": name, "value": value, "url": "https://www.nodeseek.com"}
        for name, value in COOKIE_RE.findall(str(raw or ""))
    ]


def _cloakbrowser_run(ctx, action, profile_name: str, timeout: int, cookie: str = "", clean_login: bool = False):
    import cloakbrowser

    profile_dir = Path(ctx.data_dir) / "cloakbrowser_profiles" / profile_name
    profile_dir.parent.mkdir(parents=True, exist_ok=True)
    proxy_url = str(getattr(getattr(ctx, "settings", None), "proxy_url", "") or "").strip()
    display = str(os.environ.get("DISPLAY") or "").strip()
    if not display and os.path.exists("/.dockerenv"):
        socket_dir = Path("/tmp/.X11-unix")
        if socket_dir.is_dir():
            socket = next((item for item in sorted(socket_dir.glob("X*")) if item.name[1:].isdigit()), None)
            if socket is not None:
                display = f":{socket.name[1:]}"
                os.environ["DISPLAY"] = display
    fingerprint_seed = int(hashlib.sha256(str(profile_dir).encode("utf-8")).hexdigest()[:8], 16)
    options: Dict[str, Any] = {
        "headless": not bool(display and os.path.exists("/.dockerenv")),
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "humanize": True,
        "human_preset": "careful",
        "release_channel": "preview",
        "args": [f"--fingerprint={fingerprint_seed}"],
    }
    if proxy_url:
        options.update({"proxy": proxy_url, "geoip": True})
    context = None
    try:
        context = cloakbrowser.launch_persistent_context(str(profile_dir), **options)
        if clean_login:
            clearance = [
                item for item in (context.cookies() or [])
                if item.get("name") == "cf_clearance" and "nodeseek.com" in str(item.get("domain") or "")
            ]
            context.clear_cookies()
            if clearance:
                context.add_cookies(clearance)
        if cookie:
            context.add_cookies(_cookie_items(cookie))
        pages = list(getattr(context, "pages", []) or [])
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(timeout * 1000)
        page.goto(SIGNIN_PAGE, wait_until="domcontentloaded", timeout=timeout * 1000)
        return action(page)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass


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


async def _signin_with_browser_cookie(ctx, cookie: str, reward: bool, index: int, timeout: int) -> Dict[str, Any]:
    try:
        raw = await asyncio.to_thread(
            _cloakbrowser_run, ctx, _browser_cookie_action(reward), f"cookie_{index + 1}", timeout, cookie,
        ) or {}
    except Exception as exc:
        return {"ok": False, "refresh": False, "message": f"CloakBrowser Cookie 签到失败：{exc}"}
    data = raw.get("body") or {}
    message = str(data.get("message") or raw.get("error") or f"HTTP {raw.get('status')}")
    ok, already = _signin_status(data, message)
    # 浏览器 Cookie 路径未成功时继续走账密自动登录；不能因为页面脚本
    # 没有返回 HTTP 状态而提前终止刷新流程。
    refresh = not ok
    return {"ok": ok, "already": already, "refresh": refresh, "message": message}


async def _login_and_signin(ctx, account: Dict[str, str], config: Dict[str, Any], reward: bool, index: int) -> Dict[str, Any]:
    captcha_timeout = max(30, min(300, int(config.get("captcha_timeout", 90) or 90)))
    browser_timeout = max(90, min(360, captcha_timeout + 90))
    ctx.log.info("[NodeSeek签到] Cookie 失效，正在使用 CloakBrowser 完成 Cloudflare 验证并登录")
    try:
        digest = hashlib.sha256(account["user"].encode("utf-8")).hexdigest()[:16]
        raw = await asyncio.to_thread(
            _cloakbrowser_run,
            ctx,
            _browser_action(account["user"], account["password"], reward, captcha_timeout),
            f"login_{index + 1}_{digest}",
            browser_timeout,
            "",
            True,
        ) or {}
    except Exception as exc:
        return {"ok": False, "message": f"自动登录失败：{exc}", "cookie": ""}
    if raw.get("phase") in {"cf-fail", "captcha-fail"}:
        return {"ok": False, "message": f"自动登录失败：{raw.get('captchaError') or '页面未签发 Turnstile 令牌'}", "cookie": ""}
    login_body = raw.get("loginBody") or {}
    if raw.get("phase") == "login-fail" or not login_body.get("success"):
        message = str(login_body.get("message") or raw.get("authError") or f"HTTP {raw.get('loginStatus')}")
        if "email" in str(login_body.get("redirect") or "").lower():
            message = "NodeSeek 要求邮箱验证，请先用浏览器登录一次或更换干净 IP"
        return {"ok": False, "message": f"自动登录失败：{message}", "cookie": ""}
    attendance = raw.get("attendanceBody") or {}
    message = str(attendance.get("message") or f"HTTP {raw.get('attendanceStatus')}")
    ok, already = _signin_status(attendance, message)
    return {"ok": ok, "already": already, "message": message, "cookie": str(raw.get("cookie") or "")}


async def setup(ctx):
    obsolete = {
        key: "" for key in ("solver_type", "api_base_url", "client_key")
        if ctx.config.get(key)
    }
    if obsolete:
        ctx.update_config(obsolete)
        ctx.log.info("[NodeSeek签到] 已清理停用的第三方验证码服务配置")
    defaults = {
        key: spec["default"]
        for key, spec in __plugin__["config_schema"].items()
        if "default" in spec and spec.get("type") != "action" and key not in ctx.config
    }
    if defaults:
        ctx.update_config(defaults)
    state = dict(await ctx.storage.items()); active = None; scheduled = []
    raw_cookies = str(ctx.config.get("cookies") or "").strip()
    raw_accounts = ctx.config.get("accounts")
    migrated = {}
    normalized_cookies = " & ".join(_cookies(raw_cookies))
    normalized_accounts = _accounts(raw_accounts)
    if normalized_cookies and normalized_cookies != raw_cookies:
        migrated["cookies"] = normalized_cookies
    if isinstance(raw_accounts, str) and normalized_accounts:
        migrated["accounts"] = normalized_accounts
    if migrated:
        ctx.update_config(migrated)
        ctx.log.info("[NodeSeek签到] 已将旧账号密码配置迁移为逐账号列表")
    raw_cron = str(ctx.config.get("cron") or "0 8 * * *").strip()
    if isinstance(raw_accounts, str) and raw_accounts == raw_cron and len(raw_cron.split()) == 5 and not _accounts(raw_accounts):
        ctx.update_config({"accounts": []})
        ctx.log.warning("[NodeSeek签到] 已清理旧表单错误填入账密字段的 Cron 值")

    async def run_once(source: str = "手动"):
        nonlocal active
        if active and not active.done():
            ctx.log.warning("[NodeSeek签到] %s请求被忽略：签到任务正在运行", source)
            return {"ok": False, "message": "签到任务正在运行"}
        config = dict(ctx.config or {}); cookie_list = _cookies(config.get("cookies", "")); account_list = _accounts(config.get("accounts", "")); count = max(len(cookie_list), len(account_list))
        if not count:
            ctx.log.warning("[NodeSeek签到] %s请求无法执行：未配置 Cookie 或账号密码", source)
            return {"ok": False, "message": "请先配置 NodeSeek Cookie 或账号密码"}
        cookie_list.extend([""] * (count - len(cookie_list))); account_list.extend([{"user": "", "password": ""}] * (count - len(account_list)))
        timeout = max(5, min(120, int(config.get("timeout", 30) or 30))); reward = bool(config.get("random_reward", True))

        async def worker():
            nonlocal active
            rows = []; changed = False
            try:
                ctx.log.info("[NodeSeek签到] 开始执行，来源=%s，账号=%d", source, count)
                for index in range(count):
                    cookie = cookie_list[index]; account = account_list[index]; label = account.get("user") or f"账号 {index + 1}"
                    result = await asyncio.to_thread(_signin_one, cookie, reward, timeout) if cookie else {"ok": False, "refresh": True, "message": "未配置 Cookie"}
                    if not result["ok"] and result.get("refresh") and cookie:
                        ctx.log.info(f"[NodeSeek签到] {label} HTTP 请求被拦截，使用 CloakBrowser 复核 Cookie 并签到")
                        result = await _signin_with_browser_cookie(ctx, cookie, reward, index, max(90, timeout + 60))
                    if not result["ok"] and (result.get("refresh") or not cookie):
                        if account.get("user") and account.get("password"):
                            result = await _login_and_signin(ctx, account, config, reward, index); new_cookie = str(result.get("cookie") or "")
                            if new_cookie:
                                cookie_list[index] = new_cookie; changed = True; ctx.log.info(f"[NodeSeek签到] {label} 登录成功，已获取新会话 Cookie")
                        else: result["message"] += "；未配置对应账号密码，无法自动刷新"
                    status = "已签到" if result.get("already") else ("成功" if result["ok"] else "失败")
                    rows.append({"账号": label, "状态": status, "详情": result["message"]})
                    (ctx.log.info if result["ok"] else ctx.log.error)(f"[NodeSeek签到] {label}: {result['message']}")
                if changed:
                    await ctx.storage.set("refreshed_cookies", cookie_list)
                    if config.get("auto_save_cookie", True): ctx.update_config({"cookies": " & ".join(cookie_list)}); ctx.log.info("[NodeSeek签到] 已将刷新后的 Cookie 回写到插件配置")
                success = sum(row["状态"] in {"成功", "已签到"} for row in rows); summary = {"时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "来源": source, "成功": success, "总数": len(rows), "rows": rows}
                state["last_result"] = summary; history = list(state.get("history", []) or []); history.insert(0, summary); state["history"] = history[:30]
                await ctx.storage.set("last_result", summary); await ctx.storage.set("history", state["history"])
                history_text = "\n".join(
                    f"{item.get('时间', '')} · 成功 {item.get('成功', 0)}/{item.get('总数', 0)}"
                    for item in state["history"][:10]
                )
                ctx.update_config({
                    "last_result": f"{summary['时间']} · 成功 {success}/{len(rows)}",
                    "history": history_text or "暂无记录",
                })
                if config.get("notify", True):
                    ctx.log.info("[NodeSeek签到] 正在发送签到通知：成功 %d/%d", success, len(rows))
                    try:
                        await ctx.notify(rows, category="NodeSeek签到")
                        ctx.log.info("[NodeSeek签到] 签到通知发送完成")
                    except Exception as exc:
                        ctx.log.error("[NodeSeek签到] 签到通知发送失败：%r", exc)
                else:
                    ctx.log.info("[NodeSeek签到] 通知开关已关闭，跳过签到通知")
                ctx.log.info("[NodeSeek签到] %s完成：成功 %d/%d", source, success, len(rows))
            except asyncio.CancelledError:
                ctx.log.info("[NodeSeek签到] 签到任务已取消")
                raise
            except Exception:
                ctx.log.exception("[NodeSeek签到] 签到后台任务异常")
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
