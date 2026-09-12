"""多站点 PT 自动签到：平台 CloakBrowser + 平台同步 Cookie。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from telethon import Button

import httpx
from bs4 import BeautifulSoup


_CHANGELOG_V2_0_13 = (
    "v2.0.13 修复 Cloudflare Turnstile 完整流程\n"
    "- 区分自动验证与 Managed 验证，Audiences、OurBits 均可对真实 iframe 执行一次拟人点击\n"
    "- Turnstile 使用有头浏览器、独立 90 秒验证窗口和第三方挑战 Cookie 支持\n"
    "- 记录实际 Chromium 内核版本与授权层级，旧版内核给出明确升级提示\n"
    "- 代理模式完全交给 GeoIP，同步 Cookie 不再覆盖持久 profile 的 Cloudflare 通行状态\n\n"
)


_CHANGELOG_V2_0_14 = (
    "v2.0.14 适配平台 CloakBrowser 统一治理\n"
    "- 移除插件内核预装、独立缓存和代理环境变量修改\n"
    "- 代理、License Key、内核更新及免费会话排队交由平台统一处理\n"
    "- 浏览器上下文继续在每站结束后关闭，避免占用后续插件会话\n\n"
)


_CHANGELOG_V2_0_15 = (
    "v2.0.15 等待依赖就绪后再签到\n"
    "- 每轮签到先核对全部 Python 依赖版本，再准备所需 CloakBrowser 内核\n"
    "- 浏览器准备完成并关闭预检会话后，才开始读取 Cookie 和访问签到站点\n"
    "- 依赖或内核准备失败时直接停止本轮，并在插件状态和日志中显示原因\n\n"
)


_CHANGELOG_V2_0_16 = (
    "v2.0.16 修复 Docker Turnstile 会话复用\n"
    "- Audiences 与 OurBits 改用全新临时 CloakBrowser 上下文，不再复用持久 profile 和旧 Cloudflare 状态\n"
    "- 原生验证长时间未响应时重置官方控件，保留真实 Managed iframe 点击支持\n"
    "- Turnstile 或页面验证超时会按重试配置关闭会话并更换新指纹，不再被误判为不可重试\n\n"
)


_CHANGELOG_V2_0_12 = (
    "v2.0.12 修复 CloakBrowser 首次安装超时\n"
    "- 启用插件后在后台预装 CloakBrowser 内核，签到时仍会自动补检\n"
    "- 内核下载自动使用平台代理，放宽连接与大文件读取超时并对短暂网络错误重试\n"
    "- 内核缓存改存插件持久数据目录，Docker 更新或重启后无需重新下载\n"
    "- 下载失败改为可操作的站点级提示，不再由子任务输出整段后台异常堆栈\n\n"
)


__plugin__ = {
    "name": "PT站自动签到",
    "id": "pt_multi_checkin",
    "version": "2.0.16",
    "author": "AWdress",
    "description": "多 PT 站自动签到中心，统一使用平台 Cookie 与 CloakBrowser，提供 Vue 管理界面。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/pt_checkin_v2.svg",
    "changelog": "v2.0.11 对齐 CloakBrowser 官方 Turnstile 流程\n- Audiences 与 OurBits 使用 Preview 持久会话、代理 GeoIP 和原生验证流程\n- 移除固定语言与代理出口不一致、显式重建控件和高频 CDP 等待\n- 清理 V2 前端隐藏文件，修复插件路径安全检查失败\n\nv2.0.10 修复签到参数显示不完整\n- 数字输入框保留稳定宽度，避免浏览器步进控件遮挡数值\n- 重试间隔单位改为独立布局，窄窗口自动换行且不再与数值重叠\n\nv2.0.9 修复 Audiences Docker 自动验证\n- 改用真正的 CloakBrowser 持久 profile 与固定指纹，避免 Cloudflare Cookie 和随机指纹错配\n- Audiences 只等待托管验证自动签发令牌，不再误点空的 Turnstile 外层容器\n- 控件未初始化时重新加载官方 API 并显式渲染，超时日志补充脚本、指纹和控件状态\n\nv2.0.8 修复 OurBits 与 TJUPT CloakBrowser 签到\n- OurBits 适配新的 form#attendance Turnstile，并只接受真实提交回执\n- TJUPT 保留 CloakBrowser 会话，改由已解析 DOM 元素提交表单，避免拟人层重复解析链式选择器\n\nv2.0.7 修复 OurBits、U2 与 Audiences 实际签到\n- OurBits 删除普通首页导航的成功推断，只接受站点明确签到状态或回执\n- U2 不再调用 AI 识图，直接任选一项提交；答错获得 1 UCoin 仍计为签到成功\n- Audiences 浏览器整轮限制为 30 秒，无结果立即跳过并关闭当前上下文\n\nv2.0.6 修复 Audiences 与 U2 签到\n- Audiences 改用真实 CloakBrowser 指纹与持久 storage_state，复用 Cloudflare 验证会话\n- CookieCloud 最新 Cookie 覆盖同名旧值，未同步的 Cloudflare 通行状态由持久上下文保留\n- U2 正确识别“回答错误但获得 1 UCoin”为已完成签到，不再误报失败\n\nv2.0.5 恢复 OurBits 首页签到确认\n- 将 V1 已验证的首页回执判定迁入原生 V2 核心\n- 签到后跳回站点根页且签到入口消失时确认已完成\n- HTTP、CloakBrowser 和结果回查使用同一严格条件，不把登录页或未签到首页误报成功\n\nv2.0.4 TJUPT AI 完全自动化\n- 启用 tjupt_ai_assist 时，AI 识别后直接自动提交答案\n- AI 识别失败时自动回退到 Telegram 手动选择模式\n- 优化 AI prompt，要求直接返回选项序号\n- 增强日志输出，记录 AI 识别过程和结果\n\nv2.0.3 修复 U2 签到提交\n- U2 跳过会被安全策略拒绝的轻量 HTTP 提交，直接使用 CloakBrowser\n- 改用真实浏览器表单按钮提交验证答案，并绕过缓存回查首页状态\n- 补充错误答案与过期验证识别，避免未确认状态重复误报",
    "scope": "standalone",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 2,
    "requirements": ["httpx>=0.27", "beautifulsoup4>=4.12", "cloakbrowser>=0.5.10", "geoip2>=4.8", "socksio>=1.0"],
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
        "timeout_seconds": 1800, "max_concurrency": 8, "max_background_tasks": 3,
        "failure_threshold": 3, "recovery_seconds": 120,
    },
}
__plugin__["changelog"] = _CHANGELOG_V2_0_16 + _CHANGELOG_V2_0_15 + _CHANGELOG_V2_0_14 + _CHANGELOG_V2_0_13 + _CHANGELOG_V2_0_12 + __plugin__["changelog"]

SITES = {
    "audiences": {"name": "Audiences", "domain": "audiences.me", "url": "https://audiences.me/attendance.php", "group": "NexusPHP"},
    "ourbits": {"name": "OurBits", "domain": "ourbits.club", "url": "https://ourbits.club/attendance.php", "group": "NexusPHP"},
    "piggo": {"name": "PigGo", "domain": "piggo.me", "url": "https://piggo.me/attendance.php", "group": "NexusPHP"},
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
_xvfb_lock = threading.Lock()
_xvfb_process: subprocess.Popen | None = None
_xvfb_display = ""
_state = {"running": False, "started_at": "", "finished_at": "", "current": "", "phase": "", "message": "", "completed": 0, "total": 0}
_CHINA_TZ = ZoneInfo("Asia/Shanghai")
_runtime_logs: list[dict[str, str]] = []
_storage_state: dict = {}
_storage_tasks: set[asyncio.Task] = set()

_TURNSTILE_TIMEOUT_SECONDS = 90
_TURNSTILE_AUTO_GRACE_SECONDS = 8
_CLOUDFLARE_SESSION_COOKIES = {"cf_clearance", "__cf_bm"}


def _is_cloudflare_session_cookie(name: object) -> bool:
    """Return whether a cookie is bound to Cloudflare's browser challenge session."""
    normalized = str(name or "").strip().lower()
    return normalized in _CLOUDFLARE_SESSION_COOKIES or normalized.startswith("cf_chl_")


def _cloakbrowser_binary_details(cloakbrowser, release_channel: str = "preview") -> dict:
    """Read the binary that will actually launch; wrapper version alone is misleading."""
    try:
        info = cloakbrowser.binary_info(release_channel=release_channel)
    except TypeError:
        info = cloakbrowser.binary_info()
    except Exception as exc:  # noqa: BLE001
        return {"version": "未知", "tier": "未知", "error": type(exc).__name__}
    return dict(info or {})


def _log_cloakbrowser_binary(ctx, cloakbrowser, site_name: str, release_channel: str = "preview") -> None:
    info = _cloakbrowser_binary_details(cloakbrowser, release_channel)
    version = str(info.get("version") or "未知")
    tier = str(info.get("tier") or "未知")
    _runtime_log(ctx, f"实际 CloakBrowser Chromium {version}（{tier}）", site=site_name)
    try:
        major = int(version.split(".", 1)[0])
    except (TypeError, ValueError):
        major = 0
    if major and major < 151:
        _runtime_log(
            ctx,
            "当前为旧版 keyless 内核；官方当前 Turnstile 结果基于 Chromium 151。"
            "请在平台系统设置中启用 CloakBrowser 免费 Key 并填写 Key 后重试",
            level="warning",
            site=site_name,
        )


def _stored(key, default=None):
    return _storage_state.get(key, default)


def _persist(ctx, key, value):
    _storage_state[key] = value
    task = ctx.create_task(ctx.storage.set(key, value), name=f"pt-checkin-storage:{key}")
    _storage_tasks.add(task)
    task.add_done_callback(_storage_tasks.discard)


def _runtime_log(ctx, message: str, *, level: str = "info", site: str = "") -> None:
    _runtime_logs.append({
        "time": datetime.now(_CHINA_TZ).strftime("%H:%M:%S"),
        "level": level,
        "site": site,
        "message": str(message),
    })
    del _runtime_logs[:-200]
    try:
        logger = getattr(ctx, "log", None)
        method = "warning" if level == "warning" else ("error" if level == "error" else "info")
        if logger is not None:
            getattr(logger, method)("%s%s", f"[{site}] " if site else "", message)
    except Exception:
        pass


def _ensure_docker_display(ctx) -> str:
    """确保 Docker 内存在仅供浏览器使用的本地 Xvfb 显示器。"""
    global _xvfb_display, _xvfb_process
    current = str(os.environ.get("DISPLAY") or "").strip()
    if current or not os.path.exists("/.dockerenv"):
        return current
    with _xvfb_lock:
        current = str(os.environ.get("DISPLAY") or "").strip()
        if current:
            return current

        # xvfb-run 可能启动了显示器但调用方清除了 DISPLAY；优先复用现有 socket。
        socket_dir = Path("/tmp/.X11-unix")
        if socket_dir.is_dir():
            for socket_path in sorted(socket_dir.glob("X*")):
                suffix = socket_path.name[1:]
                if suffix.isdigit():
                    current = f":{suffix}"
                    os.environ["DISPLAY"] = current
                    _runtime_log(ctx, f"发现现有 Xvfb 显示器 {current}，已恢复 DISPLAY", site="Audiences")
                    return current

        executable = shutil.which("Xvfb")
        if not executable:
            _runtime_log(
                ctx,
                "容器未安装 Xvfb，无法为 Audiences 启用虚拟有头模式；当前运行的 latest 镜像不包含仓库中的浏览器依赖",
                level="error",
                site="Audiences",
            )
            return ""

        display_number = next(
            (number for number in range(90, 111) if not (socket_dir / f"X{number}").exists()),
            None,
        )
        if display_number is None:
            _runtime_log(ctx, "没有可用的 Xvfb 显示器编号", level="error", site="Audiences")
            return ""
        current = f":{display_number}"
        try:
            process = subprocess.Popen(
                [executable, current, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + 5
            socket_path = socket_dir / f"X{display_number}"
            while time.monotonic() < deadline and process.poll() is None and not socket_path.exists():
                time.sleep(0.1)
            if process.poll() is not None or not socket_path.exists():
                if process.poll() is None:
                    process.terminate()
                _runtime_log(ctx, "Xvfb 启动失败，未创建显示器 socket", level="error", site="Audiences")
                return ""
            _xvfb_process = process
            _xvfb_display = current
            os.environ["DISPLAY"] = current
            _runtime_log(ctx, f"插件已启动 Xvfb 虚拟显示器 {current}", site="Audiences")
            return current
        except Exception as exc:  # noqa: BLE001
            _runtime_log(ctx, f"Xvfb 启动异常：{type(exc).__name__}", level="error", site="Audiences")
            return ""


async def _with_heartbeat(awaitable, ctx, site: str, message: str, *, interval: int = 10, max_wait: int = 600):
    """等待长浏览器任务时持续写入插件页与平台日志。"""
    # 这是已由平台托管的签到任务的内部子任务。若再使用
    # ctx.create_task，平台 done callback 会在上层尚未处理异常时
    # 先记录“后台任务执行失败”整段堆栈。
    task = asyncio.create_task(awaitable, name=f"pt-checkin-{site}")
    elapsed = 0
    try:
        while elapsed < max_wait:
            wait_for = min(interval, max_wait - elapsed)
            done, _ = await asyncio.wait({task}, timeout=wait_for)
            if done:
                return task.result()
            elapsed += wait_for
            _runtime_log(ctx, f"{message}，已等待 {elapsed} 秒", level="warning", site=site)
        raise RuntimeError(
            f"CloakBrowser 等待超过 {max_wait} 秒，已终止本轮签到；"
            "若日志曾长时间停在浏览器等待，请重启平台以释放底层浏览器线程"
        )
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _prepare_runtime_dependencies(selected_keys: list[str]) -> list[str]:
    """确认平台依赖已完整安装，并通过正常 launch 预备浏览器内核。

    这里只使用平台已经代理和治理过的 CloakBrowser launch 接口，不直接调用
    ensure_binary、不修改缓存目录，也不读取平台 License Key。
    """
    from packaging.requirements import Requirement

    versions: list[str] = []
    import_names = {"beautifulsoup4": "bs4"}
    for raw in __plugin__["requirements"]:
        requirement = Requirement(raw)
        installed = importlib.metadata.version(requirement.name)
        if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
            raise RuntimeError(f"依赖版本不满足：{requirement.name} {installed}，需要 {requirement.specifier}")
        importlib.import_module(import_names.get(requirement.name.lower(), requirement.name.replace("-", "_")))
        versions.append(f"{requirement.name} {installed}")

    import cloakbrowser

    channels: list[str] = []
    if any(key in {"audiences", "ourbits"} for key in selected_keys):
        channels.append("preview")
    if any(key not in {"audiences", "ourbits"} for key in selected_keys):
        channels.append("stable")

    binaries: list[str] = []
    for channel in channels:
        browser = None
        try:
            # 正常 launch 会由平台选择代理、License Key、兼容内核和免费会话队列；
            # 成功返回即表示该通道所需内核已经可以启动。
            browser = cloakbrowser.launch(headless=True, release_channel=channel)
            info = _cloakbrowser_binary_details(cloakbrowser, channel)
            binaries.append(
                f"{channel} Chromium {info.get('version') or '未知'}（{info.get('tier') or '未知'}）"
            )
        finally:
            if browser is not None:
                browser.close()
    return versions + binaries


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
    cookies = getattr(ctx, "cookies", None)
    if cookies is None or not callable(getattr(cookies, "get", None)):
        return "", "平台 Cookie 同步未启用"
    parsed = urlparse(site["url"])
    path = parsed.path or "/"
    domain = site["domain"].lower()
    url_host = (parsed.hostname or domain).lower()
    hosts = list(dict.fromkeys((url_host, domain, domain[4:] if domain.startswith("www.") else f"www.{domain}")))
    last_error = ""
    auth_cookie_missing = False
    for host in hosts:
        try:
            if key in {"opencd", "ourbits", "piggo"}:
                try:
                    items = await ctx.cookies.get(host, path=path)
                except TypeError:
                    items = await ctx.cookies.get(host)
                names = {str(item.get("name") or "").lower() for item in items}
                non_login = names and all(
                    name.startswith(("_ga", "_gid", "_gat", "_fbp"))
                    or name in {"cf_clearance", "__cf_bm", "cf_chl_2", "sl-session", "sl-challenge-server"}
                    for name in names
                )
                if non_login:
                    auth_cookie_missing = True
                    continue
            try:
                cookie = await ctx.cookies.header(host, path=path)
            except TypeError:
                cookie = await ctx.cookies.header(host)
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
            if key in {"opencd", "ourbits", "piggo"}:
                try:
                    items = await ctx.cookies.get(host, path=path)
                except TypeError:
                    items = await ctx.cookies.get(host)
                names = {str(item.get("name") or "").lower() for item in items}
                non_login = names and all(
                    name.startswith(("_ga", "_gid", "_gat", "_fbp"))
                    or name in {"cf_clearance", "__cf_bm", "cf_chl_2", "sl-session", "sl-challenge-server"}
                    for name in names
                )
                if non_login:
                    auth_cookie_missing = True
                    continue
            try:
                cookie = await ctx.cookies.header(host, path=path)
            except TypeError:
                cookie = await ctx.cookies.header(host)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        if cookie:
            return cookie, ""
    if last_error:
        return "", f"读取平台 Cookie 失败：{last_error}"
    if auth_cookie_missing:
        return "", "平台只有该站安全验证/统计 Cookie，没有登录会话；请在 CookieCloud 来源浏览器重新登录网站并同步"
    return "", "平台中没有该站 Cookie，请登录网站并同步"


async def _refresh_site_cookie(ctx, key: str, site: dict) -> tuple[str, str]:
    """要求平台刷新指定站点 Cookie；不在插件配置或存储中保留 Cookie。"""
    parsed = urlparse(site["url"])
    domain = site["domain"].lower()
    url_host = (parsed.hostname or domain).lower()
    hosts = list(dict.fromkeys((url_host, domain, domain[4:] if domain.startswith("www.") else f"www.{domain}")))
    for host in hosts:
        try:
            await ctx.cookies.request_sync(host)
        except Exception:
            continue
    return await _site_cookie(ctx, key, site)


def _page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return page.content()


def _html_visible_text(html: str) -> str:
    """提取服务端页面的可见文本，排除脚本中的提示语和翻译文案。"""
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup.select("script, style, template, noscript"):
        node.decompose()
    return soup.get_text("\n", strip=True)


def _result_state(text: str, *, confirmed: bool = False) -> tuple[str, str] | None:
    """只根据明确的站点反馈判断结果，避免把普通 200 页面误报为成功。"""
    low = (text or "").lower()
    already_markers = (
        "今日已签到", "今天已签到", "今日已经签到", "今天已经签到", "今日签到已完成", "今天签到已完成",
        "already attended", "already signed", "attended today", "already checked in",
    )
    success_markers = [
        "本次签到获得", "此次签到获得", "签到获得", "签到奖励",
        "attend got", "attend get bonus", "attend get bouns",
        "attendance success", "check-in successful", "checked in successfully",
    ]
    if confirmed:
        success_markers.extend(("签到成功", "成功签到"))
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
    compact = re.sub(r"\s+", "", text or "").lower()
    if any(marker in compact for marker in ("签到失败", "验证失败", "操作频繁", "请稍后再试")):
        return "failed", "网站返回签到失败、验证失败或操作频繁"
    if any(marker in compact for marker in (
        "今日已签到", "今天已签到", "今日已经签到", "今天已经签到",
        "今日已经签到过", "今天已经签到过", "今日不能重复签到", "今天不能重复签到", "请勿重复签到",
    )):
        return "already", "今天已经签到"
    if any(marker in compact for marker in (
        "签到成功", "本次签到获得", "此次签到获得", "签到所得", "今日签到排名",
        "本次签到获得了", "签到已得", "已连续签到",
    )) or re.search(r"这是您的(?:首次|第\d+次)签到", compact):
        return "success", "签到成功"
    return None


def _hhan_result_state(html: str) -> tuple[str, str] | None:
    """HHanClub 会反复展示最近一次奖励，须以当天记录创建时间区分本次与已签到。"""
    today = datetime.now(_CHINA_TZ).strftime("%Y-%m-%d")
    match = re.search(rf'"{re.escape(today)}"\s*:\s*(\{{[^}}]+\}})', html or "")
    if not match:
        return None
    try:
        record = json.loads(match.group(1))
        created = datetime.strptime(str(record.get("created_at") or ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CHINA_TZ)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    age = (datetime.now(_CHINA_TZ) - created).total_seconds()
    if -30 <= age <= 180:
        return "success", "签到成功"
    return "already", "今天已经签到"


def _u2_result_state(text: str, *, submitted: bool = False) -> tuple[str, str] | None:
    """识别 U2 的最终签到状态；不把未签到时的 Show Up 菜单当成成功。"""
    raw = text or ""
    visible = _html_visible_text(raw)
    compact = re.sub(r"\s+", "", visible).lower()
    # U2 的验证题答错仍会完成当日签到并发放 1 UCoin。
    # 必须在 Wrong answer 等通用错误词之前识别这类成功回执。
    challenge_form_present = bool(re.search(r'name\s*=\s*["\']req["\']', raw, re.IGNORECASE))
    award_match = re.search(r"(\d+(?:\.\d+)?)\s*ucoin", compact, re.IGNORECASE)
    wrong_but_awarded = (
        not challenge_form_present
        and any(marker in compact for marker in (
            "回答错误", "回答錯誤", "答案错误", "答案錯誤",
            "wronganswer", "incorrectanswer",
        ))
        and award_match is not None
    )
    if wrong_but_awarded:
        return "success", f"签到成功（回答错误，获得 {award_match.group(1)} UCoin）"
    wrong_answer = any(marker in compact for marker in (
        "回答错误", "回答錯誤", "答案错误", "答案錯誤",
        "wronganswer", "incorrectanswer",
    ))
    if submitted and wrong_answer:
        return "success", "签到成功（回答错误，获得 1 UCoin）"
    if any(marker in compact for marker in (
        "签到失败", "簽到失敗", "验证失败", "驗證失敗", "答案错误", "答案錯誤",
        "wronganswer", "incorrectanswer", "invalidcaptcha", "captchaexpired",
        "请求已过期", "請求已過期", "操作频繁", "操作頻繁", "请稍后再试", "請稍後再試",
    )) or re.search(r'"status"\s*:\s*"error"', raw, re.IGNORECASE):
        return "failed", "U2 未接受本次签到验证答案"
    if re.search(r"[\[【]\s*(?:已签到|已簽到)\s*[\]】]", visible, re.IGNORECASE) or any(marker in compact for marker in (
        "感谢，今天已签到", "感謝，今天已簽到", "今天已经签到", "今天已經簽到",
        "今日已签到", "今日已簽到", "已完成签到", "已完成簽到",
        "alreadyshoweduptoday", "alreadycheckedintoday", "youhaveshoweduptoday",
    )) or re.search(r'"status"\s*:\s*"already"', raw, re.IGNORECASE):
        return "already", "今天已经签到"
    if any(marker in compact for marker in (
        "签到成功", "簽到成功", "成功签到", "成功簽到", "showupsuccess", "check-insuccess",
        "thankyouforshowingup", "thanksforshowingup",
    )) or re.search(r'"status"\s*:\s*"(?:success|ok)"', raw, re.IGNORECASE) \
            or re.search(r'"success"\s*:\s*true', raw, re.IGNORECASE) \
            or re.search(r"window\.location(?:\.href)?\s*=\s*['\"]showup\.php", raw, re.IGNORECASE):
        return "success", "签到成功"
    return None


def _u2_submit_with_browser(page, submit) -> str:
    """使用真实浏览器表单提交 U2 验证，避免 fetch/XHR 被站点 WAF 拒绝。"""
    submit.evaluate("""element => {
        const form = element.form;
        if (!form) throw new Error('submit control has no form');
        const message = form.querySelector('[name="message"]');
        if (message && !String(message.value || '').trim()) {
            message.value = '每日自动签到';
            message.dispatchEvent(new Event('input', {bubbles: true}));
            message.dispatchEvent(new Event('change', {bubbles: true}));
        }
        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit(element);
            return;
        }
        if (element.name) {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = element.name;
            hidden.value = element.value || '';
            form.appendChild(hidden);
        }
        form.submit();
    }""")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
    except Exception:
        # 页面可能在原文档内直接渲染结果；继续读取当前 DOM 进行严格判定。
        pass
    page.wait_for_timeout(1_000)
    return page.content()


def _ttg_result_state(text: str) -> tuple[str, str] | None:
    """兼容 TTG HTML、纯文本和 JSON 三类签到回执。"""
    raw = text or ""
    compact = re.sub(r"\s+", "", _html_visible_text(raw)).lower()
    if any(marker in compact for marker in (
        "签到失败", "簽到失敗", "操作频繁", "请稍后再试", "signfailed",
    )):
        return "failed", "网站返回签到失败"
    if re.search(r"\[\s*已签到\s*\]", raw, re.IGNORECASE) or any(marker in compact for marker in (
        "今天已签到过", "今日已签到", "今天已经签到", "alreadysigned",
    )):
        return "already", "今天已经签到"
    if any(marker in compact for marker in (
        "您已连续签到", "签到成功", "簽到成功", "signsuccess", "signedsuccessfully",
    )) or re.search(r'"(?:success|status)"\s*:\s*(?:true|1|200)', raw, re.IGNORECASE) \
            or re.search(r'"code"\s*:\s*(?:0|200)', raw, re.IGNORECASE):
        return "success", "签到成功"
    return None


def _site_result_state(text: str, expected_domain: str = "", *, confirmed: bool = False) -> tuple[str, str] | None:
    if expected_domain.lower() in {"audiences.me", "ourbits.club", "piggo.me", "hhanclub.net"}:
        return _nexus_result_state(text)
    return _result_state(text, confirmed=confirmed)


def _hdsky_already(text: str) -> bool:
    """天空以首页导航的方括号标签表示当天已签到。"""
    return bool(re.search(r"\[\s*(?:已签到|已簽到)\s*\]", text or "", re.IGNORECASE))


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


def _seed_browser_cookie_jar(page, cookie_header: str, url: str) -> None:
    """把平台 Cookie Header 写入浏览器 Cookie Jar，确保安全验证跳转后仍保留登录态。"""
    items = []
    for part in str(cookie_header or "").split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name:
            items.append({"name": name, "value": value, "url": url})
    if not items:
        return
    page.context.add_cookies(items)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)


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
        "等待 telegram", "签到选项", "验证题已变化", "cloakbrowser 等待超过", "本轮跳过",
        "turnstile",
    )
    return not any(marker in text for marker in permanent)


def _turnstile_session_retryable(key: str, exc: Exception) -> bool:
    """Turnstile 站点可通过关闭当前会话并更换全新指纹恢复的错误。"""
    if key not in {"audiences", "ourbits"}:
        return False
    text = str(exc).lower()
    return any(marker in text for marker in (
        "turnstile",
        "cloakbrowser 60 秒内没有取得页面结果",
        "cloakbrowser 90 秒内没有取得页面结果",
        "cloudflare/雷池验证等待超时",
    ))


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

    rows = [[Button.inline(f"{index + 1}. {label}"[:60], f"pttj:{token}:{index}".encode())]
            for index, label in enumerate(options)]
    caption = (
        "🎬 TJUPT 签到验证\n\n"
        f"AI 建议：{suggestion[:700]}\n\n"
        "请核对海报后点击一个候选答案；插件只会提交你点击的选项。"
    )
    owner_id = int(str(getattr(ctx.settings, "default_bot_chat_id", "") or 0))
    if ctx.bot is None or not ctx.bot.is_connected() or not owner_id:
        raise RuntimeError("平台 Bot 未连接或未配置主人 ID，无法发送 TJUPT 确认按钮")
    await ctx.bot.send_file(owner_id, str(image_path), caption=caption, buttons=rows)


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

    # 尝试 AI 自动识别并提交
    choice = None
    auto_submit_enabled = ctx.config.get("tjupt_ai_assist", True)
    
    if auto_submit_enabled and _ai_available(ctx, "vision"):
        try:
            _runtime_log(ctx, f"使用 AI 自动识别海报，候选项：{options}", level="info", site="TJUPT")
            image_bytes = image_path.read_bytes()
            
            suggestion = str(asyncio.run_coroutine_threadsafe(
                ctx.ai.vision(
                    image=image_bytes,
                    prompt=(
                        "这是 TJUPT 的影视海报选择题。请观察图片，在下列候选项中给出最可能的一个。"
                        "**只需要返回选项序号（从0开始），例如：0 或 1 或 2，不要返回任何解释**。\n候选项：\n"
                        + "\n".join(f"{index}. {label}" for index, label in enumerate(options))
                    ),
                    system="你是影视海报识别助手。只返回最可能的选项序号（0-based index），例如直接返回 0 或 1 或 2，不要返回任何解释文字。",
                ),
                loop
            ).result(timeout=60))
            
            # 解析 AI 返回的选项序号
            match = re.search(r'\b(\d+)\b', suggestion)
            if match:
                choice = int(match.group(1))
                if 0 <= choice < count:
                    _runtime_log(ctx, f"AI 识别结果：选项 {choice} ({options[choice]})，自动提交", level="info", site="TJUPT")
                else:
                    _runtime_log(ctx, f"AI 返回的序号 {choice} 超出范围 [0, {count-1}]，回退到手动模式", level="warning", site="TJUPT")
                    choice = None
            else:
                _runtime_log(ctx, f"AI 返回内容无法解析为选项序号：{suggestion[:200]}，回退到手动模式", level="warning", site="TJUPT")
        except Exception as exc:
            _runtime_log(ctx, f"AI 识图失败：{exc}，回退到手动模式", level="warning", site="TJUPT")
            choice = None
    
    # 如果 AI 识别失败或未启用，回退到 Telegram 手动选择
    if choice is None:
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
        finally:
            _tjupt_pending.pop(token, None)
    
    # 提交选择的答案
    try:
        current = page.locator('input[type="radio"]')
        if current.count() != count or [_radio_label(current.nth(i)) or f"选项 {i + 1}" for i in range(count)] != options:
            raise RuntimeError("TJUPT 验证题已变化，未提交答案")
        selected = current.nth(choice)
        # CloakBrowser 仍负责真实浏览器会话。0.5.10 的 Locator.check/click
        # 即使传 humanize=False 也仍会进入拟人层，而拟人层不支持这里的
        # nth + ancestor 链式 locator；直接在已解析的 DOM 元素上触发原生
        # 表单事件，避开选择器二次解析。
        selected.evaluate("""element => {
            element.checked = true;
            element.dispatchEvent(new Event('input', {bubbles: true}));
            element.dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        submit = form.locator('button[type="submit"], input[type="submit"], button').first
        if submit.count() < 1:
            raise RuntimeError("没有找到 TJUPT 验证题提交按钮")
        submit.evaluate("""element => {
            const form = element.form || element.closest('form');
            if (!form) throw new Error('TJUPT submit control has no form');
            if (typeof form.requestSubmit === 'function') form.requestSubmit(element);
            else element.click();
        }""")
        page.wait_for_timeout(3_000)
        return _confirm_result(page)
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass


def _confirm_result(page, *, attempts: int = 3, expected_domain: str = "") -> dict:
    """刷新确认服务端状态；绝不为确认结果而再次点击签到按钮。"""
    for attempt in range(attempts):
        text = _page_text(page)
        path = (urlparse(page.url).path or "/").lower()
        html = page.content().lower()
        if path.endswith(("/login.php", "/takelogin.php")) or 'name="username"' in html or "name='username'" in html:
            raise RuntimeError("Cookie 已失效：签到后网站跳转到登录页，请在 CookieCloud 来源浏览器重新登录并同步")
        captcha = _captcha_error(text)
        if captcha:
            raise RuntimeError(captcha)
        state = _site_result_state(text, expected_domain, confirmed=True)
        if state:
            status, message = state
            if status == "failed":
                raise RuntimeError(message)
            return {"status": status, "message": message}
        if attempt + 1 < attempts:
            page.wait_for_timeout(2_000 * (attempt + 1))
            page.reload(wait_until="domcontentloaded", timeout=60_000)
    # 部分 NexusPHP 站点的 attendance.php 在验证/跳转后只剩页脚，真实状态显示在首页导航。
    home_url = {
        "audiences.me": "https://audiences.me/",
        "ourbits.club": "https://ourbits.club/",
        "piggo.me": "https://piggo.me/",
        "hhanclub.net": "https://hhanclub.net/",
    }.get(expected_domain.lower())
    if home_url:
        page.goto(home_url, wait_until="domcontentloaded", timeout=60_000)
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


def _ai_call(ctx, loop, capability: str, *, prompt: str, image: bytes | None = None,
             system: str | None = None) -> str:
    if not _ai_available(ctx, capability):
        raise RuntimeError(f"平台未配置可用的 AI {capability} 能力，无法自动识别签到验证")
    if capability == "vision":
        coro = ctx.ai.vision(
            image=image, prompt=prompt,
            system=system or "你是谨慎的验证码识别器，只输出请求的答案，不要解释。",
        )
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
    last_error: Exception | None = None
    for _ in range(3):
        try:
            answer = _ai_call(ctx, loop, "vision", image=image, prompt=(
                f"读取图片中的 {length} 位验证码。只输出验证码本身；无法确认时输出 UNKNOWN。"
            ))
            candidates = re.findall(rf"(?<![A-Za-z0-9])[A-Za-z0-9]{{{length}}}(?![A-Za-z0-9])", answer)
            if "UNKNOWN" not in answer.upper() and candidates:
                return candidates[0]
            last_error = RuntimeError("模型返回 UNKNOWN 或验证码格式不正确")
        except Exception as exc:  # noqa: BLE001 - 模型上游偶发失败时有限重试
            last_error = exc
    raise RuntimeError("AI 连续 3 次未能可靠识别验证码，未提交签到") from last_error




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
        raise RuntimeError("Cookie 已失效：站点拒绝当前登录会话，请在 CookieCloud 来源浏览器重新登录并同步")
    mode = site.get("mode")
    if mode == "interactive":
        if key in {"pt52", "chdbits"}:
            return _quiz_checkin(page, site, ctx, loop)
        if key == "hdsky":
            if _hdsky_already(text):
                return {"status": "already", "message": "今天已经签到"}
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
            try:
                return _response_result(body, success=('"success":true', '"success": true'), already=("date_unmatch",))
            except RuntimeError:
                page.goto("https://hdsky.me", wait_until="domcontentloaded", timeout=60_000)
                if _hdsky_already(_page_text(page)):
                    return {"status": "success", "message": "签到成功（首页状态已确认）"}
                raise
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
            initial = _u2_result_state(html)
            if initial and initial[0] != "failed":
                return {"status": initial[0], "message": initial[1]}
            # U2 的权威状态位于首页顶部：[立即签到] 成功后变为 [已签到]。
            # showup.php 本身可能继续显示表单，因此必须先查首页，避免重复提交。
            page.goto("https://u2.dmhy.org/", wait_until="domcontentloaded", timeout=60_000)
            home_state = _u2_result_state(page.content())
            if home_state and home_state[0] != "failed":
                return {"status": "already", "message": "今天已经签到（首页状态已确认）"}
            if datetime.now(_CHINA_TZ).hour < 9:
                raise RuntimeError("U2 站点规则要求 09:00 后签到")
            page.goto(site["url"], wait_until="domcontentloaded", timeout=60_000)
            html = page.content()
            form = page.locator('form:has(input[name="req"])').first
            req = form.locator('input[name="req"]').get_attribute("value")
            hash_value = form.locator('input[name="hash"]').get_attribute("value")
            form_value = form.locator('input[name="form"]').get_attribute("value")
            submits = page.locator('form:has(input[name="req"]) input[type="submit"]')
            if not req or not hash_value or not form_value or submits.count() < 1:
                raise RuntimeError("U2 未解析到签到表单")
            choice = secrets.randbelow(submits.count())
            submit = submits.nth(choice)
            _runtime_log(
                ctx,
                f"U2 验证题任意选择第 {choice + 1}/{submits.count()} 项；答错仍会完成签到并获得 1 UCoin",
                site="U2",
            )
            body = _u2_submit_with_browser(page, submit)
            posted = _u2_result_state(body, submitted=True)
            if posted:
                if posted[0] == "failed":
                    excerpt = re.sub(r"\s+", " ", _html_visible_text(body)).strip()[:500]
                    _runtime_log(ctx, f"U2 提交回执：{excerpt}", level="warning", site="U2")
                    raise RuntimeError(posted[1])
                return {"status": "success", "message": posted[1]}
            page.goto(
                f"https://u2.dmhy.org/?_awbn_checkin={int(time.time())}",
                wait_until="domcontentloaded", timeout=60_000,
            )
            confirmed = page.content()
            final = _u2_result_state(confirmed)
            if final:
                return {"status": "success", "message": "签到成功（首页状态已确认）"}
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
        initial = _ttg_result_state(html)
        if initial:
            if initial[0] == "failed":
                raise RuntimeError(initial[1])
            return {"status": initial[0], "message": initial[1]}
        timestamp = re.search(r'signed_timestamp:\s*["\'](\d{10})', html)
        token = re.search(r'signed_token:\s*["\']([^"\']+)', html)
        if not timestamp or not token:
            raise RuntimeError("未获取到 TTG 签到参数")
        result = _fetch_same_origin(page, "https://totheglory.im/signed.php", method="POST", data={"signed_timestamp": timestamp.group(1), "signed_token": token.group(1)})
        posted = _ttg_result_state(result.get("text", ""))
        if posted:
            if posted[0] == "failed":
                raise RuntimeError(posted[1])
            return {"status": posted[0], "message": posted[1]}
        page.goto(site["url"], wait_until="domcontentloaded", timeout=60_000)
        final = _ttg_result_state(page.content())
        if final:
            return {"status": "success", "message": "签到成功（首页状态已确认）"}
        raise RuntimeError("TTG 签到提交后仍未确认已签到")
    if mode == "yema":
        return _response_result(text, success=('"success":true', '"success": true'), already=("already", "已签到"))
    if mode == "zhuque":
        csrf = page.locator('meta[name="x-csrf-token"]').get_attribute("content")
        if not csrf:
            raise RuntimeError("未获取到朱雀 CSRF 参数")
        result = _fetch_same_origin(page, "https://zhuque.in/api/gaming/fireGenshinCharacterMagic", method="POST", json_data={"all": 1, "resetModal": "true"}, headers={"x-csrf-token": csrf})
        return _response_result(result.get("text", ""), success=("FIRE_GENSHIN_CHARACTER_MAGIC_SUCCESS", '"status":200'), already=("already",))
    return _browser_checkin(page, site["domain"], ctx, loop)


def _click_managed_turnstile(page) -> str:
    """Click a real Cloudflare Managed iframe once; never click the empty host widget."""
    frames = [
        frame for frame in page.frames
        if "challenges.cloudflare.com" in str(getattr(frame, "url", "") or "")
    ]
    for frame in frames:
        try:
            checkbox = frame.locator('input[type="checkbox"]').first
            if checkbox.count() and checkbox.is_visible() and checkbox.is_enabled():
                checkbox.click(timeout=3_000)
                return "iframe 内原生 checkbox"
        except Exception:
            continue
    try:
        iframe = page.locator(
            'iframe[src*="challenges.cloudflare.com"], iframe[title*="Cloudflare" i]'
        ).first
        if iframe.count() and iframe.is_visible():
            box = iframe.bounding_box()
            if box and box["width"] >= 80 and box["height"] >= 40:
                page.mouse.click(
                    box["x"] + min(32, box["width"] / 4),
                    box["y"] + box["height"] / 2,
                )
                return f"Cloudflare iframe 坐标，尺寸 {round(box['width'])}x{round(box['height'])}"
    except Exception:
        pass
    return ""


def _reset_turnstile(page) -> str:
    """重置页面原生 Turnstile；不创建站外控件，也不注入站点参数。"""
    try:
        return str(page.evaluate("""() => {
            if (!window.turnstile || typeof window.turnstile.reset !== 'function') return '';
            try {
                window.turnstile.reset();
                return 'Turnstile 原生 reset';
            } catch (error) {
                return 'Turnstile reset 失败: ' + String(error);
            }
        }""") or "")
    except Exception:
        return ""


def _turnstile_checkin(page, expected_domain: str, ctx=None, *, timeout_seconds: int = 30) -> dict:
    """等待 NexusPHP Turnstile 回调提交，只接受明确的服务端结果。"""
    is_audiences = expected_domain.lower() == "audiences.me"
    site_name = "Audiences" if is_audiences else "OurBits"
    form_selector = "#attendance-form" if is_audiences else "#attendance"
    timeout_seconds = max(1, min(120, int(timeout_seconds)))
    deadline = time.monotonic() + timeout_seconds
    started_at = time.monotonic()
    click_count = 0
    token_logged = False
    empty_widget_logged = False
    reset_detail = ""
    # 非交互式验证先获得一个完整的自动签发窗口。只有 Cloudflare 真正生成
    # Managed iframe 后才点击一次，避免误点空的站点外层容器。
    while time.monotonic() < deadline:
        text = _page_text(page)
        state = _nexus_result_state(text)
        if state:
            if state[0] == "failed":
                raise RuntimeError(state[1])
            return {"status": state[0], "message": state[1]}
        form_present = page.locator(form_selector).count() > 0
        turnstile_present = page.locator(f"{form_selector} .cf-turnstile").count() > 0
        if not form_present and not turnstile_present:
            return _confirm_result(page, attempts=2, expected_domain=expected_domain)
        token_info = page.evaluate("""() => {
            const names = ['cf-turnstile-response', 'cf-token'];
            for (const name of names) {
                const input = document.querySelector(`[name="${name}"]`);
                if (input && String(input.value || '').trim()) {
                    return {token: String(input.value).trim(), source: name};
                }
            }
            try {
                if (window.turnstile && typeof window.turnstile.getResponse === 'function') {
                    const response = String(window.turnstile.getResponse() || '').trim();
                    if (response) return {token: response, source: 'turnstile.getResponse'};
                }
            } catch (_) {}
            return {token: '', source: ''};
        }""")
        token = str((token_info or {}).get("token", "")).strip()
        if token:
            if ctx is not None and not token_logged:
                _runtime_log(
                    ctx,
                    f"已取得 Turnstile 验证令牌（来源：{token_info.get('source') or '未知'}），正在提交签到",
                    site=site_name,
                )
                token_logged = True
            page.evaluate(f"""() => {{
                const form = document.querySelector('{form_selector}');
                if (!form || form.dataset.awSubmitted === '1') return;
                form.dataset.awSubmitted = '1';
                if (typeof form.requestSubmit === 'function') form.requestSubmit();
                else form.submit();
            }}""")
            time.sleep(min(2.0, max(0.0, deadline - time.monotonic())))
            continue
        now = time.monotonic()
        elapsed = now - started_at
        if not reset_detail and elapsed >= min(30.0, max(10.0, timeout_seconds / 3.0)):
            reset_detail = _reset_turnstile(page)
            if reset_detail and ctx is not None:
                _runtime_log(
                    ctx,
                    f"原生 Turnstile 长时间未响应，已请求控件重新验证（{reset_detail}）",
                    level="warning",
                    site=site_name,
                )
        challenge_frames = [
            frame for frame in page.frames
            if "challenges.cloudflare.com" in str(getattr(frame, "url", "") or "")
        ]
        # Managed Turnstile 在 Docker/低信誉出口下可能显示可交互复选框。
        # Audiences 与 OurBits 都可能动态切换到 Managed，不能按站点永久禁用点击。
        should_click = (
            click_count == 0
            and elapsed >= _TURNSTILE_AUTO_GRACE_SECONDS
        )
        if should_click:
            click_detail = _click_managed_turnstile(page)
            if click_detail:
                click_count += 1
                if ctx is not None:
                    _runtime_log(
                        ctx,
                        f"已对 Managed Turnstile 单击一次（{click_detail}），等待验证完成",
                        site=site_name,
                    )
            elif ctx is not None and not challenge_frames and not empty_widget_logged:
                _runtime_log(
                    ctx,
                    "Turnstile 外层容器尚未生成 Cloudflare 验证 iframe，不执行无效空容器点击",
                    level="warning",
                    site=site_name,
                )
                empty_widget_logged = True
        wait_seconds = 2.0
        wait_seconds = min(wait_seconds, max(0.0, deadline - time.monotonic()))
        time.sleep(wait_seconds)
    try:
        diagnostics = page.evaluate(f"""() => ({{
            url: location.href,
            title: document.title,
            forms: document.querySelectorAll('{form_selector}').length,
            widgets: Array.from(document.querySelectorAll('.cf-turnstile')).map(widget => ({{
                sitekey: String(widget.dataset.sitekey || '').slice(0, 24),
                children: widget.children.length,
                text: String(widget.textContent || '').trim().slice(0, 120)
            }})),
            turnstileApi: Boolean(window.turnstile),
            turnstileError: String(window.__awTurnstileError || ''),
            scripts: Array.from(document.scripts)
                .map(script => String(script.src || ''))
                .filter(src => src.includes('turnstile') || src.includes('cloudflare'))
                .slice(0, 8),
            navigator: {{
                webdriver: navigator.webdriver,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                languages: navigator.languages
            }},
            iframes: Array.from(document.querySelectorAll('iframe')).map(frame => ({{
                title: frame.title || '', src: String(frame.src || '').slice(0, 160)
            }}))
        }})""")
    except Exception as exc:
        diagnostics = {"diagnostic_error": str(exc)}
    if ctx is not None:
        _runtime_log(ctx, f"Turnstile 超时诊断：{diagnostics}", level="error", site=site_name)
    raise RuntimeError(f"{site_name} Turnstile 未在 {timeout_seconds} 秒内签发有效验证令牌，本轮已跳过")


def _audiences_turnstile_checkin(page, ctx=None, *, timeout_seconds: int = 30) -> dict:
    """兼容旧测试与内部调用名；实际逻辑由通用 Turnstile 处理器负责。"""
    return _turnstile_checkin(
        page, "audiences.me", ctx, timeout_seconds=timeout_seconds,
    )


def _turnstile_site_cloak_checkin(ctx, key: str, site: dict, cookie: str, headless: bool) -> dict:
    """使用 CloakBrowser 官方推荐参数处理 NexusPHP Turnstile。"""
    import cloakbrowser

    site_name = str(site["name"])
    site_domain = str(site["domain"])
    site_url = str(site["url"])
    launch_options = {
        "headless": headless,
        "release_channel": "preview",
        "humanize": True,
        "human_preset": "careful",
        # 不传 proxy/license_key：由 AWBotNest 按当前系统设置统一注入；
        # GeoIP 使浏览器指纹与平台最终选择的网络出口保持一致。
        "geoip": True,
    }

    version = str(getattr(cloakbrowser, "__version__", "未知"))
    running_mode = "无头" if headless else ("虚拟有头" if os.path.exists("/.dockerenv") else "有头")
    _runtime_log(
        ctx,
        f"启动 CloakBrowser {version} Preview 全新临时上下文（"
        f"{running_mode}模式，新指纹，网络与 GeoIP 跟随平台设置）",
        site=site_name,
    )
    context = page = None
    try:
        context = cloakbrowser.launch_context(**launch_options)
        # launch 完成后再读取，确保报告的是平台本次实际选择并准备的内核。
        _log_cloakbrowser_binary(ctx, cloakbrowser, site_name, "preview")
        pages = list(getattr(context, "pages", []) or [])
        page = pages[0] if pages else context.new_page()
        page.set_default_timeout(20_000)

        # 只注入平台同步的站点业务 Cookie。与旧浏览器指纹和出口绑定的
        # Cloudflare Cookie 不跨会话复制，由全新上下文自行完成验证。
        items = []
        for part in str(cookie or "").split(";"):
            name, separator, value = part.strip().partition("=")
            if separator and name and not _is_cloudflare_session_cookie(name):
                items.append({"name": name, "value": value, "url": site_url})
        if items:
            context.add_cookies(items)

        try:
            page.goto(
                site_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise RuntimeError(f"{site_name} CloakBrowser 60 秒内没有取得页面结果，本轮已跳过") from exc
            raise
        # 浏览器启动和页面导航不再挤占验证时间。
        deadline = time.monotonic() + _TURNSTILE_TIMEOUT_SECONDS
        if key == "audiences":
            _runtime_log(
                ctx,
                "先等待 Turnstile 自动验证；如出现 Managed 复选框，将对真实 iframe 单击一次",
                site=site_name,
            )
            # 原生 sleep 不产生 Playwright waitForTimeout CDP 指令。
            time.sleep(min(8.0, max(0.0, deadline - time.monotonic())))
        return _browser_checkin(page, site_domain, ctx, None, deadline=deadline)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass


def _site_cloak_checkin(ctx, key: str, site: dict, cookie: str, headless: bool, loop) -> dict:
    """所有 PT 站浏览器降级统一使用真实 CloakBrowser。"""
    if key in {"audiences", "ourbits"}:
        return _turnstile_site_cloak_checkin(ctx, key, site, cookie, headless)

    import cloakbrowser

    state_path = Path(ctx.data_dir) / f"{key}_storage_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    launch_options = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
        # 交由平台注入代理和 License Key；GeoIP 跟随最终网络出口。
        "geoip": True,
        "humanize": True,
    }

    browser = context = page = None
    try:
        browser = cloakbrowser.launch(**launch_options)
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
            "extra_http_headers": {"Accept-Language": "zh-CN,zh;q=0.9"},
        }
        if state_path.exists():
            context_options["storage_state"] = str(state_path)
        try:
            context = browser.new_context(**context_options)
        except Exception as exc:
            if "storage_state" not in context_options:
                raise
            _runtime_log(
                ctx,
                f"已保存的浏览器会话无法读取（{type(exc).__name__}），本轮将重建",
                level="warning",
                site=site["name"],
            )
            context_options.pop("storage_state", None)
            context = browser.new_context(**context_options)
        page = context.new_page()
        page.set_default_timeout(20_000)
        seed_url = "https://piggo.me/" if key == "piggo" else site["url"]
        _seed_browser_cookie_jar(page, cookie, seed_url)
        if key in {"ourbits", "piggo", "hhan", "tjupt"}:
            result = _browser_checkin(page, site["domain"], ctx, loop)
            if key == "piggo":
                refreshed = _refreshed_cookie_header(page, site["domain"])
                if refreshed:
                    _browser_cookie_cache[key] = refreshed
            return result
        return _special_checkin(page, key, site, ctx, loop)
    finally:
        if context is not None:
            try:
                context.storage_state(path=str(state_path))
            except Exception as exc:
                _runtime_log(
                    ctx,
                    f"保存浏览器会话失败：{type(exc).__name__}",
                    level="warning",
                    site=site["name"],
                )
        for item in (page, context, browser):
            if item is not None:
                try:
                    item.close()
                except Exception:
                    pass


def _browser_checkin(page, expected_domain: str, ctx=None, loop=None, *,
                     piggo_submitted: bool = False, deadline: float | None = None) -> dict:
    """在平台托管的同步 Playwright 页面内完成单站签到。"""
    page.set_default_timeout(20_000)
    challenge_reload_done = False
    piggo_reentries = 0
    challenge_started_at = time.monotonic()
    challenge_click_detail = ""
    for challenge_round in range(100):
        if deadline is not None and time.monotonic() >= deadline:
            raise RuntimeError(
                f"{expected_domain} CloakBrowser {_TURNSTILE_TIMEOUT_SECONDS} 秒内没有取得页面结果，本轮已跳过"
            )
        title = (page.title() or "").lower()
        text = _page_text(page).lower()
        path = urlparse(page.url).path or "/"
        piggo_security_shell = (
            expected_domain.lower() == "piggo.me"
            and path == "/"
            and "cloudflare" in text
            and "privacy" in text
            and not any(marker in text for marker in ("签到", "控制面板", "种子", "论坛", "个人资料"))
        )
        challenged = any(marker in f"{title}\n{text}" for marker in (
            "just a moment", "checking your browser", "cloudflare ray id", "cf-chl-",
            "请完成安全验证", "验证您是否是真人", "验证完成，即将进入网站",
            "雷池 waf", "安全检测能力由 雷池", "verification completed",
            "请耐心等待签到验证程序加载",
        )) or piggo_security_shell
        if not challenged:
            break
        if (
            expected_domain.lower() in {"audiences.me", "ourbits.club"}
            and not challenge_click_detail
            and time.monotonic() - challenge_started_at >= _TURNSTILE_AUTO_GRACE_SECONDS
        ):
            challenge_click_detail = _click_managed_turnstile(page)
            if challenge_click_detail and ctx is not None:
                _runtime_log(
                    ctx,
                    f"已对 Cloudflare 页面 Managed 验证单击一次（{challenge_click_detail}）",
                    site="Audiences" if expected_domain.lower() == "audiences.me" else "OurBits",
                )
        # PigGo 雷池完成验证时可能停在只含 Cloudflare / Privacy 的空壳根页。
        # 给脚本时间写入通行 Cookie，再受控重进签到页，避免把空壳当业务页面。
        if piggo_security_shell and challenge_round in {3, 10, 25}:
            page.goto("https://piggo.me/attendance.php", wait_until="domcontentloaded", timeout=60_000)
            piggo_reentries += 1
            continue
        # 雷池偶尔已下发通行 Cookie 但前端未完成跳转，受控重载可恢复。
        if not challenge_reload_done and challenge_round >= 10 and any(marker in f"{title}\n{text}" for marker in (
            "验证完成，即将进入网站", "verification completed",
        )):
            page.reload(wait_until="domcontentloaded", timeout=60_000)
            challenge_reload_done = True
            continue
        wait_ms = 3_000
        if deadline is not None:
            wait_ms = min(wait_ms, max(1, int((deadline - time.monotonic()) * 1000)))
        if expected_domain.lower() in {"audiences.me", "ourbits.club"}:
            time.sleep(wait_ms / 1000)
        else:
            page.wait_for_timeout(wait_ms)
    else:
        detail = f"；已重进签到页 {piggo_reentries} 次" if piggo_reentries else ""
        raise RuntimeError(f"Cloudflare/雷池验证等待超时{detail}；若为交互式验证码需要人工处理")

    current_domain = (urlparse(page.url).hostname or "").lower()
    if not _same_site_domain(current_domain, expected_domain):
        raise RuntimeError(f"站点跳转到了非预期域名：{current_domain or '未知'}")
    text = _page_text(page)
    low = text.lower()
    html = page.content().lower()
    if any(marker in low for marker in (
        "用户名或密码", "please login", "not logged in", "请先登录",
    )) or 'name="username"' in html or "name='username'" in html or urlparse(page.url).path.lower().endswith(("/login.php", "/takelogin.php")):
        raise RuntimeError("Cookie 已失效：站点拒绝当前登录会话，请在 CookieCloud 来源浏览器重新登录并同步")
    if any(marker in low for marker in ("没有权限", "无权访问", "permission denied", "access denied", "page not found", "404 not found")):
        raise RuntimeError("签到页面不可用或当前账号没有访问权限")
    if expected_domain.lower() in {"audiences.me", "ourbits.club"} \
            and page.locator("form .cf-turnstile").count() > 0:
        remaining = _TURNSTILE_TIMEOUT_SECONDS if deadline is None else max(1, int(deadline - time.monotonic()))
        return _turnstile_checkin(page, expected_domain, ctx, timeout_seconds=remaining)
    captcha = _captcha_error(text)
    if captcha:
        if expected_domain == "tjupt.org" and ctx is not None and loop is not None and "签到图片验证码" in captcha:
            return _tjupt_challenge(ctx, page, loop)
        raise RuntimeError(captcha)
    if expected_domain.lower() == "hhanclub.net":
        state = _hhan_result_state(html)
        if state:
            return {"status": state[0], "message": state[1]}
        raise RuntimeError("HHanClub 页面未找到当天签到记录，未计为成功")
    if expected_domain.lower() == "piggo.me":
        signed_badge = bool(re.search(r"签到\s*已得\s*[\d,.]+", text))
        if signed_badge:
            return {
                "status": "success" if piggo_submitted else "already",
                "message": "签到成功" if piggo_submitted else "今天已经签到",
            }
        if not path.lower().endswith("/attendance.php"):
            page.goto("https://piggo.me/attendance.php", wait_until="domcontentloaded", timeout=60_000)
            return _browser_checkin(page, expected_domain, ctx, loop, piggo_submitted=True)
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
    # TTG 的正常首页会携带 Cloudflare 相关脚本字样；动态签到参数同时存在时
    # 说明业务页已完整返回，不能仅凭脚本文案误判为挑战页。
    trusted_ttg_page = (
        response.status_code == 200
        and "signed_timestamp" in text
        and "signed_token" in text
    )
    if low.strip() in {"err cookie", "cookie error", "invalid cookie"}:
        raise RuntimeError("Cookie 已失效：网站签到接口拒绝当前登录会话，请在 CookieCloud 来源浏览器重新登录并同步")
    if not trusted_ttg_page and (response.status_code in {403, 429, 468, 503, 521, 522, 525} or any(marker in low for marker in (
        "cf-chl-", "cloudflare ray id", "just a moment", "checking your browser",
        "turnstile", "雷池 waf", "安全检测能力由 雷池", "验证您是否是真人",
        "verification completed", "challenge-platform",
    ))):
        raise _NeedsBrowser(f"HTTP 命中安全验证（{response.status_code}），切换 CloakBrowser")
    if any(marker in low for marker in ('name="username"', "name='username'", "takelogin.php")) or response.url.path.lower().endswith(("/login.php", "/takelogin.php")):
        raise RuntimeError("Cookie 已失效：站点拒绝当前登录会话，请在 CookieCloud 来源浏览器重新登录并同步")
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
    last_error: Exception | None = None
    for _ in range(3):
        try:
            answer = str(await ctx.ai.vision(
                image=image, prompt=f"读取图片中的 {length} 位验证码。只输出验证码本身；无法确认时输出 UNKNOWN。",
                system="你是谨慎的验证码识别器，只输出请求的答案，不要解释。",
            ) or "").strip()
            matches = re.findall(rf"(?<![A-Za-z0-9])[A-Za-z0-9]{{{length}}}(?![A-Za-z0-9])", answer)
            if "UNKNOWN" not in answer.upper() and matches:
                return matches[0]
            last_error = RuntimeError("模型返回 UNKNOWN 或验证码格式不正确")
        except Exception as exc:  # noqa: BLE001 - 模型上游偶发失败时有限重试
            last_error = exc
    raise RuntimeError("AI 连续 3 次未能可靠识别验证码，未提交签到") from last_error




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
        response, text = await get("https://piggo.me/" if key == "piggo" else site["url"])
        visible_text = _html_visible_text(text)
        if key == "hhan":
            state = _hhan_result_state(text)
            if state:
                return {"status": state[0], "message": state[1], "engine": "http"}
            raise _NeedsBrowser("HTTP 未找到 HHanClub 当天签到记录，切换 CloakBrowser 确认")
        if key == "audiences":
            soup = BeautifulSoup(text, "html.parser")
            if soup.select_one("#attendance-form .cf-turnstile"):
                raise _NeedsBrowser("Audiences 需要 Turnstile 人机验证，切换 CloakBrowser 等待自动验证")
        if key == "piggo":
            if re.search(r"签到\s*已得\s*[\d,.]+", visible_text):
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
            response, text = await get(site["url"])
            visible_text = _html_visible_text(text)
        if key in {"audiences", "ourbits", "piggo", "hhan"}:
            # 标准 attendance.php 通常 GET 即完成；未知页面交给浏览器识别动态按钮。
            state = _site_result_state(visible_text, site["domain"], confirmed=True)
            if state and state[0] != "failed":
                return {"status": state[0], "message": state[1], "engine": "http"}
            if state and state[0] == "failed":
                raise RuntimeError(state[1])
            # Audiences 的 attendance.php 在 Docker/CF 链路中会完成签到后返回无回执的站点模板。
            # 此处仅接受已通过登录与安全页检查的 2xx 同站请求，避免把登录页或挑战页误报为成功。
            response_domain = (urlparse(str(response.url)).hostname or "").lower()
            response_path = urlparse(str(response.url)).path or "/"
            if key == "audiences" and response.status_code < 300 \
                    and _same_site_domain(response_domain, site["domain"]):
                return {"status": "success", "message": "签到请求已完成（站点未返回文字回执）", "engine": "http"}
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
            initial = _ttg_result_state(text)
            if initial:
                if initial[0] == "failed":
                    raise RuntimeError(initial[1])
                return {"status": initial[0], "message": initial[1], "engine": "http"}
            timestamp = re.search(r'signed_timestamp:\s*["\'](\d{10})', text)
            token = re.search(r'signed_token:\s*["\']([^"\']+)', text)
            if not timestamp or not token:
                raise _NeedsBrowser("HTTP 未取得 TTG 动态参数，切换 CloakBrowser")
            _, body = await post(
                "https://totheglory.im/signed.php",
                data={"signed_timestamp": timestamp.group(1), "signed_token": token.group(1)},
                extra_headers={"Referer": str(response.url), "X-Requested-With": "XMLHttpRequest"},
            )
            posted = _ttg_result_state(body)
            if posted:
                if posted[0] == "failed":
                    raise RuntimeError(posted[1])
                return {"status": posted[0], "message": posted[1], "engine": "http"}
            _, confirmed = await get(site["url"])
            final = _ttg_result_state(confirmed)
            if final:
                return {"status": "success", "message": "签到成功（首页状态已确认）", "engine": "http"}
            raise _NeedsBrowser("TTG HTTP 提交后未确认最终状态，切换 CloakBrowser 回查")
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
            if _hdsky_already(visible_text):
                return {"status": "already", "message": "今天已经签到", "engine": "http"}
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
            try:
                result = _response_result(body, success=('"success":true', '"success": true'), already=("date_unmatch",))
            except RuntimeError:
                _, confirmed = await get("https://hdsky.me")
                if _hdsky_already(_html_visible_text(confirmed)):
                    result = {"status": "success", "message": "签到成功（首页状态已确认）"}
                else:
                    raise
            return {**result, "engine": "http"}
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
            try:
                captcha = await _http_ai_ocr(ctx, image_response.content)
            except RuntimeError as exc:
                raise _NeedsBrowser("OpenCD HTTP 验证码无法确认，切换 CloakBrowser 获取新验证码") from exc
            _, body = await post("https://www.open.cd/plugin_sign-in.php?cmd=signin", data={"imagehash": hash_node.get("value"), "imagestring": captcha})
            return {**_response_result(body, success=('"state":"success"', '"state":true'), already=("已签到",)), "engine": "http"}
        if key == "u2":
            initial = _u2_result_state(text)
            if initial and initial[0] != "failed":
                return {"status": initial[0], "message": initial[1], "engine": "http"}
            # 签到状态只在首页顶部可靠展示；先确认首页再解析/提交表单。
            _, home = await get("https://u2.dmhy.org/")
            home_state = _u2_result_state(home)
            if home_state and home_state[0] != "failed":
                return {"status": "already", "message": "今天已经签到（首页状态已确认）", "engine": "http"}
            if datetime.now(_CHINA_TZ).hour < 9:
                raise RuntimeError("U2 站点规则要求 09:00 后签到")
            soup = BeautifulSoup(text, "html.parser")
            req, hash_value, form_value = (_soup_value(soup, name) for name in ("req", "hash", "form"))
            submits = soup.select('input[type="submit"][name]')
            if not req or not hash_value or not form_value or not submits:
                raise _NeedsBrowser("HTTP 未解析到 U2 签到表单，切换 CloakBrowser")
            submit = submits[secrets.randbelow(len(submits))]
            post_response, body = await post(
                "https://u2.dmhy.org/showup.php?action=show",
                data={"req": req, "hash": hash_value, "form": form_value, "message": "每日自动签到", submit.get("name"): submit.get("value")},
                extra_headers={"Referer": str(response.url)},
            )
            posted = _u2_result_state(body, submitted=True)
            if posted:
                if posted[0] == "failed":
                    raise RuntimeError(posted[1])
                return {"status": "success", "message": posted[1], "engine": "http"}
            response_path = (urlparse(str(post_response.url)).path or "").lower()
            response_domain = (urlparse(str(post_response.url)).hostname or "").lower()
            if post_response.status_code < 300 and _same_site_domain(response_domain, site["domain"]):
                suffix = "提交后跳转已确认" if response_path not in {"/showup.php", "showup.php"} else "站点接受签到表单"
                return {"status": "success", "message": f"签到成功（{suffix}）", "engine": "http"}
            _, confirmed = await get("https://u2.dmhy.org/")
            final = _u2_result_state(confirmed)
            if final:
                return {"status": "success", "message": "签到成功（首页状态已确认）", "engine": "http"}
            raise _NeedsBrowser("U2 HTTP 提交后未确认最终状态，切换 CloakBrowser 回查")
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
            "finished_at": "", "current": "", "phase": "依赖准备", "message": "正在等待平台依赖和浏览器内核就绪",
            "completed": 0, "total": len(enabled),
        })
        _runtime_log(ctx, "开始检查平台依赖与 CloakBrowser 内核，完成前不会启动签到")
        try:
            prepared = await _with_heartbeat(
                asyncio.to_thread(_prepare_runtime_dependencies, [key for key, _ in enabled]),
                ctx,
                "依赖准备",
                "平台依赖或 CloakBrowser 内核仍在准备",
                interval=30,
                max_wait=900,
            )
        except asyncio.CancelledError:
            _state.update({"running": False, "phase": "已取消", "message": "依赖准备已取消", "current": ""})
            raise
        except Exception as exc:  # noqa: BLE001
            message = f"依赖或 CloakBrowser 内核未准备完成：{exc}"
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _state.update({
                "running": False, "finished_at": stamp, "current": "", "phase": "依赖失败", "message": message,
            })
            _runtime_log(ctx, message, level="error")
            return {"ok": False, "message": message, "results": []}
        _runtime_log(ctx, "依赖准备完成：" + "；".join(prepared), level="success")
        _state.update({"phase": "准备", "message": "依赖已就绪，开始签到"})
        _runtime_log(ctx, f"开始{source}签到，共 {len(enabled)} 个站点")
        results = []
        retries = _bounded(cfg.get("retry_count"), 2, 0, 5)
        interval = _bounded(cfg.get("retry_interval"), 20, 5, 300)
        loop = asyncio.get_running_loop()
        for key, site in enabled:
            _state.update({"current": site["name"], "phase": "读取 Cookie", "message": f"正在读取 {site['name']} 平台 Cookie"})
            _runtime_log(ctx, "读取平台 Cookie", site=site["name"])
            cookie, error = await _site_cookie(ctx, key, site)
            if error:
                _runtime_log(ctx, error, level="error", site=site["name"])
                results.append({"key": key, "site": site["name"], "ok": False, "status": "failed", "message": error})
                _state["completed"] += 1
                continue
            cookie = _browser_cookie_cache.get(key) or cookie
            item = None
            for attempt in range(retries + 1):
                try:
                    outcome = None
                    browser_reason = ""
                    if key not in {"tjupt", "u2"}:
                        _state.update({"phase": "HTTP 请求", "message": f"{site['name']} 正在使用轻量 HTTP 签到"})
                        _runtime_log(ctx, "使用轻量 HTTP 检查签到状态", site=site["name"])
                        try:
                            outcome = await _http_checkin(ctx, key, site, cookie)
                        except _NeedsBrowser as fallback:
                            browser_reason = str(fallback)
                        except httpx.RequestError as fallback:
                            browser_reason = f"HTTP 网络异常（{type(fallback).__name__}），切换 CloakBrowser"
                    elif key == "u2":
                        browser_reason = "U2 使用浏览器原生表单提交，避免站点拦截 HTTP 自动请求"
                    else:
                        browser_reason = "TJUPT 需要页面交互验证"

                    if outcome is None:
                        _state.update({"phase": "浏览器降级", "message": f"{site['name']}：{browser_reason}"})
                        _runtime_log(ctx, browser_reason, level="warning", site=site["name"])

                        if outcome is None:
                            browser_timeout = 720 if key == "tjupt" else (300 if key in {"piggo", "hhan"} else (150 if key in {"audiences", "ourbits"} else 150))
                            browser_headless = bool(cfg.get("headless", True))
                            if key in {"audiences", "ourbits"}:
                                if os.path.exists("/.dockerenv"):
                                    display = _ensure_docker_display(ctx)
                                    if display:
                                        # Docker 中由 Xvfb 承载真实有头窗口，不会显示到用户桌面。
                                        browser_headless = False
                                        _runtime_log(
                                            ctx,
                                            f"Docker 虚拟显示器 {display} 已就绪，使用虚拟有头 CloakBrowser",
                                            site=site["name"],
                                        )
                                    else:
                                        _runtime_log(
                                            ctx,
                                            f"Docker 无可用 DISPLAY，{site['name']} 只能回退无头模式",
                                            level="warning",
                                            site=site["name"],
                                        )
                                else:
                                    # 官方针对激进 Turnstile 的推荐配置要求 headed；仅两站覆盖
                                    # 通用“静默运行”开关，避免降低其余站点的后台体验。
                                    browser_headless = False
                                    _runtime_log(
                                        ctx,
                                        "Turnstile 站点强制使用有头 CloakBrowser",
                                        site=site["name"],
                                    )
                            _runtime_log(
                                ctx,
                                "使用真实 CloakBrowser 浏览器会话",
                                site=site["name"],
                            )
                            _state.update({
                                "phase": "浏览器签到",
                                "message": f"{site['name']}：CloakBrowser 正在处理签到",
                            })
                            outcome = await _with_heartbeat(
                                asyncio.to_thread(
                                    _site_cloak_checkin,
                                    ctx,
                                    key,
                                    site,
                                    cookie,
                                    browser_headless,
                                    loop,
                                ),
                                ctx,
                                site["name"],
                                "CloakBrowser 正在等待安全验证或页面结果",
                                max_wait=browser_timeout + 30,
                            )
                    status = str((outcome or {}).get("status") or "success")
                    if status == "failed":
                        raise RuntimeError(str((outcome or {}).get("message") or "网站返回签到失败"))
                    engine = str((outcome or {}).get("engine") or "browser")
                    item = {
                        "key": key, "site": site["name"], "ok": True, "status": status,
                        "engine": engine, "message": str((outcome or {}).get("message") or "签到完成"),
                    }
                    _runtime_log(ctx, item["message"], level="success", site=site["name"])
                    break
                except Exception as exc:  # noqa: BLE001
                    login_expired = "Cookie 已失效" in str(exc) or "网站返回登录页" in str(exc)
                    if attempt < retries and login_expired:
                        _state.update({"phase": "刷新 Cookie", "message": f"{site['name']} 登录状态失效，正在请求平台重新同步"})
                        _browser_cookie_cache.pop(key, None)
                        refreshed, refresh_error = await _refresh_site_cookie(ctx, key, site)
                        if refreshed:
                            cookie = refreshed
                        elif refresh_error:
                            item = {"key": key, "site": site["name"], "ok": False, "status": "failed", "engine": "http/browser", "message": refresh_error}
                            _runtime_log(ctx, refresh_error, level="error", site=site["name"])
                            break
                        await asyncio.sleep(min(interval, 5))
                    elif attempt < retries and _turnstile_session_retryable(key, exc):
                        _runtime_log(
                            ctx,
                            "当前 Turnstile/Cloudflare 会话未完成，已关闭并将在新指纹上下文中重试",
                            level="warning",
                            site=site["name"],
                        )
                        await asyncio.sleep(min(interval, 5))
                    elif attempt < retries and _retryable_error(exc):
                        await asyncio.sleep(interval)
                    else:
                        message = str(exc).strip() or type(exc).__name__
                        item = {"key": key, "site": site["name"], "ok": False, "status": "failed", "engine": "http/browser", "message": message}
                        _runtime_log(ctx, message, level="error", site=site["name"])
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
        history = _stored(_HISTORY_KEY, []) or []
        if not isinstance(history, list):
            history = []
        _persist(ctx, _HISTORY_KEY, [record, *history][:30])
        _persist(ctx, _LAST_KEY, text)
        if cfg.get("notify_result", True):
            rows = [{"站点": item["site"], "结果": "已签到" if item["status"] == "already" else ("成功" if item["ok"] else "失败"), "详情": item["message"]} for item in results]
            try:
                await ctx.notify(rows, level="success" if success == len(results) else "warning", category="PT站签到")
            except Exception as exc:  # noqa: BLE001
                ctx.log.warning("签到结果推送失败：%r", exc)
        _state.update({"running": False, "finished_at": stamp, "current": "", "phase": "完成", "message": summary})
        _runtime_log(ctx, summary, level="success" if success == len(results) else "warning")
        return {"ok": success == len(results), "message": text, "results": results}


async def setup(ctx):
    global _run_lock
    _run_lock = asyncio.Lock()
    _state.update({"running": False, "started_at": "", "finished_at": "", "current": "", "phase": "", "message": "", "completed": 0, "total": 0})
    _runtime_logs.clear()
    _storage_state.clear()
    _storage_state.update(dict(await ctx.storage.items()))
    _runtime_log(ctx, "插件已加载，等待签到任务")
    _runtime_log(ctx, "CloakBrowser 依赖、内核、License Key、代理及免费会话队列由平台统一管理")

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
        task = ctx.create_task(_run(ctx, "手动"), name="PT站手动签到")
        _tasks.add(task)
        task.add_done_callback(_task_done)
        return {"ok": True, "message": "签到任务已开始"}

    @ctx.on_api("/history", methods=["GET"])
    async def api_history(req):
        items = _stored(_HISTORY_KEY, []) or []
        return {"ok": True, "items": items if isinstance(items, list) else []}

    @ctx.on_api("/history/clear", methods=["POST"])
    async def api_history_clear(req):
        _persist(ctx, _HISTORY_KEY, [])
        return {"ok": True, "message": "签到记录已清空"}

    @ctx.on_api("/logs", methods=["GET"])
    async def api_logs(req):
        return {"ok": True, "items": list(reversed(_runtime_logs))}

    @ctx.on_api("/logs/clear", methods=["POST"])
    async def api_logs_clear(req):
        _runtime_logs.clear()
        _runtime_log(ctx, "运行日志已清空")
        return {"ok": True, "message": "运行日志已清空"}

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

    @ctx.on_callback(pattern=rb"^pttj:")
    async def tjupt_choice(query):
        data = query.data or b""
        if isinstance(data, (bytes, bytearray)):
            data = bytes(data).decode("utf-8", "replace")
        try:
            _, token, raw_choice = str(data).split(":", 2)
            choice = int(raw_choice)
        except (TypeError, ValueError):
            await query.answer("选项数据无效", show_alert=True)
            return
        sender = await query.get_sender()
        owner_id = int(str(getattr(ctx.settings, "default_bot_chat_id", "") or 0))
        if sender is None or int(sender.id) != owner_id:
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
        task = ctx.create_task(_run(ctx, "手动"), name="PT站手动签到")
        _tasks.add(task)
        task.add_done_callback(_task_done)
        return {"ok": True, "message": "签到任务已开始，完成后会推送汇总结果"}

    @ctx.action("view_result")
    async def view_result():
        text = str(_stored(_LAST_KEY, "") or "")
        return {"ok": bool(text), "message": text or "暂无签到记录"}

    cfg = _cfg(ctx)
    if cfg.get("auto_checkin", True):
        hour = _bounded(cfg.get("checkin_hour"), 8, 0, 23)
        minute = _bounded(cfg.get("checkin_minute"), 10, 0, 59)

        async def scheduled():
            await _run(ctx, "定时")

        ctx.schedule(scheduled, "cron", hour=hour, minute=minute, id="PT站每日签到")


async def teardown(ctx):
    global _xvfb_display, _xvfb_process
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
    if _storage_tasks:
        await asyncio.gather(*list(_storage_tasks), return_exceptions=True)
    _storage_tasks.clear()
    _storage_state.clear()
    if _xvfb_process is not None and _xvfb_process.poll() is None:
        _xvfb_process.terminate()
        try:
            _xvfb_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _xvfb_process.kill()
    if _xvfb_display and os.environ.get("DISPLAY") == _xvfb_display:
        os.environ.pop("DISPLAY", None)
    _xvfb_process = None
    _xvfb_display = ""
