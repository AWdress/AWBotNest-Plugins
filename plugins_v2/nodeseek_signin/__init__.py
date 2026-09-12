"""NodeSeek 签到（AWBotNest V2 原生实现）。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List

import requests

__plugin__ = {
    "name": "NodeSeek 签到",
    "id": "nodeseek_signin",
    "version": "0.0.1",
    "author": "AWdress",
    "description": "NodeSeek 论坛自动签到，支持多 Cookie、签到奖励和定时执行。",
    "icon": "https://raw.githubusercontent.com/SAGIRIxr/MoviePilot-Plugins/main/icons/Nodeseek_A.png",
    "changelog": "v0.0.1 首次发布\n- 使用 AWBotNest V2 原生异步存储、生命周期、定时任务和动作接口\n- 支持多账号 Cookie、签到奖励解析、历史记录和立即签到",
    "scope": "user",
    "plugin_api_version": 2,
    "tags": ["NodeSeek", "自动签到", "论坛工具"],
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "启用自动签到", "section": "功能开关", "order": 1},
        "notify": {"type": "boolean", "default": True, "label": "发送签到通知", "section": "功能开关", "order": 2},
        "cookies": {"type": "textarea", "default": "", "label": "NodeSeek Cookie", "help": "多账号每行一个，也支持用 & 分隔。", "section": "账号", "order": 10, "secret": True},
        "random_reward": {"type": "boolean", "default": True, "label": "随机鸡腿奖励", "section": "签到设置", "order": 20},
        "cron": {"type": "string", "default": "0 8 * * *", "label": "签到 Cron", "help": "五段 Cron，默认每天 08:00。", "section": "签到设置", "order": 21},
        "timeout": {"type": "number", "default": 30, "min": 5, "max": 120, "label": "请求超时（秒）", "section": "签到设置", "order": 22},
    },
}

ATTENDANCE_API = "https://www.nodeseek.com/api/account/signIn"
COOKIE_RE = re.compile(r"(?:^|;)\s*([^=;\s]+)=([^;]*)")


def _cookies(raw: str) -> List[str]:
    out = []
    for line in re.split(r"[&\n\r]+", str(raw or "")):
        line = line.strip()
        if line:
            out.append(line)
    return out


def _signin_one(cookie: str, reward: bool, timeout: int) -> Dict[str, Any]:
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (AWBotNest NodeSeekSignin)", "Accept": "application/json, text/plain, */*", "Referer": "https://www.nodeseek.com/"}
    try:
        parsed = dict(COOKIE_RE.findall(cookie))
        session.cookies.update(parsed)
        payload = {"random": bool(reward)}
        response = session.post(ATTENDANCE_API, json=payload, headers=headers, timeout=timeout)
        text = response.text or ""
        try:
            data = response.json()
        except ValueError:
            data = {}
        message = str(data.get("message") or data.get("msg") or text[:120]).strip()
        ok = response.status_code < 400 and any(x in message.lower() for x in ("success", "already", "签到", "鸡腿", "已签"))
        if not message:
            message = f"HTTP {response.status_code}"
        return {"ok": ok, "message": message, "status": response.status_code}
    except Exception as exc:
        return {"ok": False, "message": f"请求失败：{exc}"}


async def setup(ctx):
    state = dict(await ctx.storage.items())
    active = None
    scheduled = []

    def cfg():
        return {**__plugin__["config_schema"], **dict(ctx.config or {})}

    async def run_once(source: str = "手动"):
        nonlocal active
        if active and not active.done():
            return {"ok": False, "message": "签到任务正在运行"}
        c = dict(ctx.config or {})
        entries = _cookies(c.get("cookies", ""))
        if not entries:
            return {"ok": False, "message": "请先配置 NodeSeek Cookie"}
        timeout = max(5, min(120, int(c.get("timeout", 30) or 30)))
        reward = bool(c.get("random_reward", True))

        async def worker():
            rows = []
            for index, cookie in enumerate(entries, 1):
                result = await asyncio.to_thread(_signin_one, cookie, reward, timeout)
                rows.append({"账号": f"账号 {index}", "状态": "成功" if result["ok"] else "失败", "详情": result["message"]})
                ctx.log.info(f"[NodeSeek签到] 账号 {index}: {result['message']}")
            success = sum(r["状态"] == "成功" for r in rows)
            summary = {"时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "来源": source, "成功": success, "总数": len(rows), "rows": rows}
            state["last_result"] = summary
            history = list(state.get("history", []) or [])
            history.insert(0, summary)
            state["history"] = history[:30]
            await ctx.storage.set("last_result", summary)
            await ctx.storage.set("history", state["history"])
            if c.get("notify", True):
                await ctx.notify([{"项目": "任务", "内容": "NodeSeek 签到"}, {"项目": "结果", "内容": f"成功 {success}/{len(rows)}"}, *rows], category="NodeSeek签到")
            active = None

        active = ctx.create_task(worker(), name="NodeSeek签到")
        return {"ok": True, "message": "已开始 NodeSeek 签到"}

    @ctx.action("run_now")
    async def run_now():
        return await run_once("手动")

    @ctx.on_api("/run", methods=["POST"])
    async def api_run(req):
        return await run_once("API")

    @ctx.on_api("/status", methods=["GET"])
    async def api_status(req):
        return {"running": bool(active and not active.done()), "last_result": state.get("last_result"), "history": list(state.get("history", []) or [])[:10]}

    c = dict(ctx.config or {})
    if c.get("enabled"):
        parts = str(c.get("cron", "0 8 * * *") or "0 8 * * *").split()
        if len(parts) == 5:
            kwargs = {k: int(v) for k, v in zip(("minute", "hour", "day", "month", "day_of_week"), parts) if v != "*"}
            scheduled.append(ctx.schedule(lambda: run_once("定时"), "cron", id="NodeSeek签到·定时", **kwargs))
            ctx.log.info(f"[NodeSeek签到] 定时任务已启用：{c.get('cron')}")

    async def cleanup():
        nonlocal active
        for job in scheduled:
            try:
                job.cancel() if hasattr(job, "cancel") else None
            except Exception:
                pass
        if active and not active.done():
            active.cancel()
            await asyncio.gather(active, return_exceptions=True)
    ctx.add_cleanup(cleanup)


async def teardown(ctx):
    ctx.log.info("[NodeSeek签到] 插件已停用")
