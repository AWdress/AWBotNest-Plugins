"""AWBlackJack：单站点账号 21 点挂机与 MQTT 跨实例协同。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

import aiohttp
import aiomqtt


__plugin__ = {
    "name": "AWBlackJack",
    "id": "awblackjack",
    "version": "1.0.0",
    "author": "AWdress",
    "description": "SpringSunday 21 点单账号自动挂机插件，通过 MQTT 与其他实例同步对局状态并协助处理平局。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/awblackjack.png",
    "scope": "standalone",
    "default_enabled": False,
    "requirements": ["aiomqtt>=2.0", "aiohttp>=3.9", "beautifulsoup4>=4.12", "lxml>=5.0"],
    "changelog": "v1.0.0 初始迁移\n- 完整迁移 AWBlackJack 单账号挂机、自动抓牌、对战和平局协助逻辑\n- 保留 MQTT 跨实例状态同步，每个插件实例仅运行一个站点账号\n- 配置、日志、运行目录与生命周期接入 AWBotNest 平台\n- 支持连接测试、后台重启、崩溃自动拉起和平台错误通知",
    "config_schema": {
        "enabled": {
            "type": "boolean", "default": False, "label": "启用自动挂机",
            "help": "保存并重新加载插件后启动。每个插件实例只配置一个站点账号。",
            "section": "功能开关", "cols": 4, "order": 1,
        },
        "notify_errors": {
            "type": "boolean", "default": True, "label": "推送异常通知",
            "section": "功能开关", "cols": 4, "order": 2,
        },
        "auto_restart": {
            "type": "boolean", "default": True, "label": "崩溃后自动重启",
            "section": "功能开关", "cols": 4, "order": 3,
        },
        "my_id": {
            "type": "number", "default": 0, "label": "站点用户 ID",
            "help": "用于 MQTT 区分不同实例，所有实例必须使用不同 ID。",
            "section": "站点账号", "cols": 4, "order": 10,
        },
        "nickname": {
            "type": "string", "default": "", "label": "协同昵称",
            "help": "仅用于 MQTT 消息和日志展示。",
            "section": "站点账号", "cols": 4, "order": 11,
        },
        "cookie": {
            "type": "password", "default": "", "label": "站点 Cookie",
            "help": "SpringSunday 登录后的完整 Cookie。",
            "section": "站点账号", "cols": 12, "order": 12,
        },
        "mqtt_host": {
            "type": "string", "default": "", "label": "MQTT 地址",
            "help": "格式：host 或 host:port。所有实例必须连接同一个 Broker。",
            "section": "跨实例协同", "cols": 6, "order": 20,
        },
        "mqtt_user": {
            "type": "string", "default": "", "label": "MQTT 用户名",
            "section": "跨实例协同", "cols": 3, "order": 21,
        },
        "mqtt_password": {
            "type": "password", "default": "", "label": "MQTT 密码",
            "section": "跨实例协同", "cols": 3, "order": 22,
        },
        "test_connection": {
            "type": "action", "label": "测试站点与 MQTT", "action": "test_connection",
            "section": "跨实例协同", "cols": 6, "order": 23,
        },
        "loop_interval": {
            "type": "slider", "default": 120, "label": "基础轮询间隔（秒）",
            "min": 20, "max": 600, "step": 10,
            "section": "常规挂机", "cols": 6, "order": 30,
        },
        "max_help_bonus": {
            "type": "number", "default": 100000, "label": "最大协助魔力",
            "help": "队友平局金额超过此值时不协助。",
            "section": "常规挂机", "cols": 3, "order": 31,
        },
        "friends_count": {
            "type": "slider", "default": 2, "label": "同时挂机账号上限",
            "min": 1, "max": 20, "step": 1,
            "section": "常规挂机", "cols": 3, "order": 32,
        },
        "bonus": {
            "type": "select", "default": 10000, "label": "默认下注魔力",
            "options": [100, 1000, 10000, 100000],
            "section": "常规挂机", "cols": 6, "order": 33,
        },
        "remain_point": {
            "type": "slider", "default": 18, "label": "默认停牌点数",
            "min": 12, "max": 21, "step": 1,
            "section": "常规挂机", "cols": 6, "order": 34,
        },
        "time_ranges": {
            "type": "text", "default": "10:00-11:30\n21:00-22:30", "label": "挂机时间段",
            "help": "每行一个时间段，例如 21:00-23:30；支持跨零点。",
            "section": "常规挂机", "cols": 12, "order": 35,
        },
        "multi_bonus_enabled": {
            "type": "boolean", "default": False, "label": "启用多金额自动选择",
            "section": "多金额", "cols": 4, "order": 40,
        },
        "multi_bonus": {
            "type": "string", "default": "1000,10000,100000", "label": "监控金额",
            "help": "逗号分隔，仅支持 100、1000、10000、100000。",
            "section": "多金额", "cols": 4, "order": 41,
        },
        "multi_remain_points": {
            "type": "string", "default": "17,17,18", "label": "对应停牌点数",
            "help": "与监控金额一一对应。",
            "section": "多金额", "cols": 4, "order": 42,
        },
        "active_enabled": {
            "type": "boolean", "default": False, "label": "启用主动对战模式",
            "section": "主动对战", "cols": 4, "order": 50,
        },
        "win_rate_min": {
            "type": "slider", "default": 0, "label": "最低胜率",
            "min": 0, "max": 1, "step": 0.05,
            "help": "达到此胜率时允许在挂机时段外主动对战；0 表示禁用。",
            "section": "主动对战", "cols": 4, "order": 51,
        },
        "win_rate_apply_in_time": {
            "type": "boolean", "default": False, "label": "时段内也使用对战模式",
            "section": "主动对战", "cols": 4, "order": 52,
        },
        "battle_amounts": {
            "type": "text", "default": "100:21\n1000:18\n10000:17", "label": "对战金额与停牌点数",
            "help": "每行“金额:停牌点数”，例如 10000:17。",
            "section": "主动对战", "cols": 12, "order": 53,
        },
        "active_sleep": {
            "type": "slider", "default": 30, "label": "每局等待（秒）",
            "min": 5, "max": 600, "step": 5,
            "section": "主动对战", "cols": 6, "order": 54,
        },
        "active_max_games": {
            "type": "number", "default": 0, "label": "每日最多局数",
            "help": "0 表示不限制。",
            "section": "主动对战", "cols": 6, "order": 55,
        },
        "user_agent": {
            "type": "string", "default": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "label": "User-Agent", "section": "高级", "cols": 12, "order": 60,
        },
        "restart": {
            "type": "action", "label": "重启挂机进程", "action": "restart",
            "section": "操作", "cols": 6, "order": 70,
        },
        "runtime_status": {
            "type": "info", "default": "尚未启动", "label": "运行状态",
            "section": "运行状态", "cols": 12, "order": 80,
        },
    },
}


_process: asyncio.subprocess.Process | None = None
_supervisor_task: asyncio.Task | None = None
_mqtt_task: asyncio.Task | None = None
_reader_tasks: set[asyncio.Task] = set()
_stopping = False


def _bounded_int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _toml_string(value) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def _number_list(value, allowed=None) -> list[int]:
    result = []
    for raw in re.split(r"[,，\s]+", str(value or "")):
        if not raw:
            continue
        try:
            number = int(raw)
        except ValueError:
            continue
        if allowed is None or number in allowed:
            result.append(number)
    return result


def _time_ranges(value) -> list[list[str]]:
    result = []
    for line in str(value or "").splitlines():
        match = re.fullmatch(r"\s*(\d{1,2}:\d{2})\s*[-~至]\s*(\d{1,2}:\d{2})\s*", line)
        if not match:
            continue
        try:
            for part in match.groups():
                datetime.strptime(part, "%H:%M")
        except ValueError:
            continue
        result.append([*match.groups()])
    return result


def _battle_amounts(value) -> list[list[int]]:
    result = []
    for line in str(value or "").splitlines():
        match = re.fullmatch(r"\s*(\d+)\s*[:：]\s*(\d+)\s*", line)
        if not match:
            continue
        amount, point = map(int, match.groups())
        if amount in {100, 1000, 10000, 100000} and 12 <= point <= 21:
            result.append([amount, point])
    return result


def _toml_array(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _render_config(cfg: dict) -> str:
    valid_amounts = {100, 1000, 10000, 100000}
    multi_bonus = _number_list(cfg.get("multi_bonus"), valid_amounts)
    multi_points = _number_list(cfg.get("multi_remain_points"))
    nickname = str(cfg.get("nickname") or f"队友{cfg.get('my_id') or ''}")
    lines = [
        "[BASIC]",
        f"MYID = {_bounded_int(cfg.get('my_id'), 0, 0, 9999999999)}",
        f"NICKNAME = {_toml_string(nickname)}",
        f"COOKIE = {_toml_string(cfg.get('cookie'))}",
        'LANGUAGE = "zh-CN,zh;q=0.9"',
        'SEC_CH_UA = "\\\"Google Chrome\\\";v=\\\"137\\\", \\\"Chromium\\\";v=\\\"137\\\", \\\"Not/A)Brand\\\";v=\\\"24\\\""',
        'SEC_FETCH_MODE = "navigate"',
        'SEC_FETCH_DEST = "document"',
        f"USER_AGENT = {_toml_string(cfg.get('user_agent'))}",
        "",
        "[MQTT]",
        f"HOST = {_toml_string(cfg.get('mqtt_host'))}",
        f"USER = {_toml_string(cfg.get('mqtt_user'))}",
        f"PASSWORD = {_toml_string(cfg.get('mqtt_password'))}",
        "",
        "[GAME.GLOBAL]",
        f"SLEEP = {_bounded_int(cfg.get('loop_interval'), 120, 20, 600)}",
        f"MAX_HELP_BONUS = {_bounded_int(cfg.get('max_help_bonus'), 100000, 0, 999999999)}",
        f"FRIENDS_COUNT = {_bounded_int(cfg.get('friends_count'), 2, 1, 20)}",
        "",
        "[GAME.AFK]",
        f"BONUS = {_bounded_int(cfg.get('bonus'), 10000, 100, 100000)}",
        f"REMAIN_POINT = {_bounded_int(cfg.get('remain_point'), 18, 12, 21)}",
        f"TIME = {_toml_array(_time_ranges(cfg.get('time_ranges')))}",
        f"MULTI_BONUS_ENABLED = {'true' if cfg.get('multi_bonus_enabled') else 'false'}",
        f"MULTI_BONUS = {_toml_array(multi_bonus)}",
        f"MULTI_BONUS_REMAIN_POINT = {_toml_array(multi_points)}",
        "",
        "[GAME.ACTIVE]",
        f"WIN_RATE_MIN = {max(0.0, min(1.0, float(cfg.get('win_rate_min') or 0)))}",
        f"BATTLE_AMOUNTS = {_toml_array(_battle_amounts(cfg.get('battle_amounts')))}",
        f"WIN_RATE_APPLY_IN_TIME = {'true' if cfg.get('win_rate_apply_in_time') else 'false'}",
        f"ENABLED = {'true' if cfg.get('active_enabled') else 'false'}",
        f"SLEEP = {_bounded_int(cfg.get('active_sleep'), 30, 5, 600)}",
        f"MAX_GAMES = {_bounded_int(cfg.get('active_max_games'), 0, 0, 100000)}",
        "",
    ]
    return "\n".join(lines)


def _mqtt_address(raw: str) -> tuple[str, int]:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("未配置 MQTT 地址")
    if ":" in value:
        host, port = value.rsplit(":", 1)
        return host.strip(), int(port)
    return value, 1883


def _validate_config(cfg: dict) -> list[str]:
    errors = []
    if _bounded_int(cfg.get("my_id"), 0, 0, 9999999999) <= 0:
        errors.append("站点用户 ID 必须大于 0")
    if not str(cfg.get("cookie") or "").strip():
        errors.append("未填写站点 Cookie")
    try:
        _mqtt_address(cfg.get("mqtt_host"))
    except Exception as exc:
        errors.append(str(exc))
    if not _time_ranges(cfg.get("time_ranges")) and not cfg.get("active_enabled"):
        errors.append("至少填写一个有效挂机时间段，或启用主动对战模式")
    return errors


async def _read_stream(ctx, stream, level: str):
    while True:
        line = await stream.readline()
        if not line:
            return
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        history = ctx.kv.get("recent_logs", [])
        if not isinstance(history, list):
            history = []
        ctx.kv.set("recent_logs", [*history, text][-100:])
        getattr(ctx.log, level)("[AWBlackJack] %s", text)


async def _stop_worker(ctx):
    global _process
    process, _process = _process, None
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
    for task in list(_reader_tasks):
        task.cancel()
    _reader_tasks.clear()


async def _launch_worker(ctx):
    global _process
    cfg = dict(ctx.config or {})
    errors = _validate_config(cfg)
    if errors:
        message = "；".join(errors)
        ctx.update_config({"runtime_status": f"配置不完整：{message}"})
        ctx.log.warning("AWBlackJack 未启动：%s", message)
        return False

    runtime_dir = Path(ctx.data_dir)
    config_dir = runtime_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "logs").mkdir(parents=True, exist_ok=True)
    (runtime_dir / "temp_file").mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(_render_config(cfg), encoding="utf-8")

    worker = Path(__file__).with_name("worker.py")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    _process = await asyncio.create_subprocess_exec(
        sys.executable, "-u", str(worker),
        cwd=str(runtime_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=creationflags,
    )
    for stream, level in ((_process.stdout, "info"), (_process.stderr, "warning")):
        task = asyncio.create_task(_read_stream(ctx, stream, level))
        _reader_tasks.add(task)
        task.add_done_callback(_reader_tasks.discard)
    status = f"运行中 · PID {_process.pid} · 账号 {cfg.get('nickname') or cfg.get('my_id')}"
    ctx.update_config({"runtime_status": status})
    ctx.log.info("AWBlackJack 已启动：%s", status)
    return True


async def _supervise(ctx):
    global _process
    while not _stopping:
        if not _process:
            if not await _launch_worker(ctx):
                return
        process = _process
        code = await process.wait()
        if _stopping or process is not _process:
            return
        _process = None
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx.update_config({"runtime_status": f"{stamp} · 进程异常退出，代码 {code}"})
        ctx.log.error("AWBlackJack 工作进程退出，代码=%s", code)
        if ctx.config.get("notify_errors", True):
            try:
                await ctx.notify(f"挂机进程异常退出，代码 {code}", level="error", category="运行状态")
            except Exception as exc:
                ctx.log.warning("AWBlackJack 异常通知失败：%r", exc)
        if not ctx.config.get("auto_restart", True):
            return
        ctx.log.warning("10 秒后自动重启 AWBlackJack")
        await asyncio.sleep(10)


async def _handle_alert(ctx, cfg: dict, payload: dict) -> None:
    try:
        sender_id = int(payload.get("sender_id") or 0)
        configured_id = int(cfg.get("my_id") or 0)
    except (TypeError, ValueError):
        return
    if sender_id != configured_id:
        return

    events = ctx.kv.get("alert_events", [])
    if not isinstance(events, list):
        events = []
    ctx.kv.set("alert_events", [*events, payload][-100:])
    alert_type = str(payload.get("type") or "")
    if alert_type == "help_failed" and cfg.get("notify_errors", True):
        try:
            await ctx.notify(
                str(payload.get("message") or "平局协助失败"),
                level="warning",
                category="平局协同",
            )
        except Exception as exc:
            ctx.log.warning("AWBlackJack 平局协助通知失败：%r", exc)
    elif alert_type == "personal_stats":
        try:
            rate = float(payload.get("win_rate") or 0)
        except (TypeError, ValueError):
            rate = 0.0
        status = (
            f"运行中 · 战绩 {payload.get('wins', 0)}胜/{payload.get('losses', 0)}负 "
            f"· 胜率 {rate:.1%} · 余额 {payload.get('balance', 0)}"
        )
        ctx.update_config({"runtime_status": status})


async def _monitor_alerts(ctx):
    cfg = dict(ctx.config or {})
    try:
        host, port = _mqtt_address(cfg.get("mqtt_host"))
    except Exception:
        return
    while not _stopping:
        try:
            async with aiomqtt.Client(
                hostname=host,
                port=port,
                username=str(cfg.get("mqtt_user") or "") or None,
                password=str(cfg.get("mqtt_password") or "") or None,
                identifier=f"awblackjack-platform-{cfg.get('my_id')}",
                keepalive=20,
            ) as client:
                await client.subscribe("blackjack/alerts")
                async for message in client.messages:
                    try:
                        raw_payload = message.payload
                        if isinstance(raw_payload, bytes):
                            raw_payload = raw_payload.decode("utf-8")
                        payload = json.loads(raw_payload)
                    except (AttributeError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    await _handle_alert(ctx, cfg, payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ctx.log.warning("AWBlackJack MQTT 通知监听断开：%s；5 秒后重连", exc)
            await asyncio.sleep(5)


async def setup(ctx):
    global _supervisor_task, _mqtt_task, _stopping
    _stopping = False

    @ctx.action("test_connection")
    async def _test_connection():
        cfg = dict(ctx.config or {})
        errors = _validate_config(cfg)
        if errors:
            return {"ok": False, "message": "；".join(errors)}
        host, port = _mqtt_address(cfg.get("mqtt_host"))
        try:
            async with aiomqtt.Client(
                hostname=host,
                port=port,
                username=str(cfg.get("mqtt_user") or "") or None,
                password=str(cfg.get("mqtt_password") or "") or None,
                identifier=f"awblackjack-test-{cfg.get('my_id')}",
                timeout=10,
            ):
                pass
        except Exception as exc:
            return {"ok": False, "message": f"MQTT 连接失败：{exc}"}
        headers = {"Cookie": str(cfg.get("cookie") or ""), "User-Agent": str(cfg.get("user_agent") or "")}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get("https://springsunday.net/blackjack.php", headers=headers) as response:
                    text = await response.text()
                    if response.status != 200:
                        return {"ok": False, "message": f"站点连接失败：HTTP {response.status}"}
                    if "blackjack" not in text.casefold() and "21" not in text and "游戏" not in text:
                        return {"ok": False, "message": "站点已响应，但未识别到 21 点页面，请检查 Cookie"}
        except Exception as exc:
            return {"ok": False, "message": f"站点连接失败：{exc}"}
        return {"ok": True, "message": "站点 Cookie 与 MQTT Broker 均连接成功"}

    @ctx.action("restart")
    async def _restart():
        global _supervisor_task
        await _stop_worker(ctx)
        if _supervisor_task and not _supervisor_task.done():
            _supervisor_task.cancel()
            try:
                await _supervisor_task
            except asyncio.CancelledError:
                pass
        if not ctx.config.get("enabled", False):
            return {"ok": False, "message": "请先启用自动挂机并保存配置"}
        if await _launch_worker(ctx):
            _supervisor_task = asyncio.create_task(_supervise(ctx))
            return {"ok": True, "message": "AWBlackJack 已重启"}
        return {"ok": False, "message": "启动失败，请检查配置和运行日志"}

    if ctx.config.get("enabled", False):
        _supervisor_task = asyncio.create_task(_supervise(ctx))
        _mqtt_task = asyncio.create_task(_monitor_alerts(ctx))
    else:
        ctx.update_config({"runtime_status": "已停用"})
        ctx.log.info("AWBlackJack 自动挂机未启用")


async def teardown(ctx):
    global _supervisor_task, _mqtt_task, _stopping
    _stopping = True
    if _supervisor_task and not _supervisor_task.done():
        _supervisor_task.cancel()
        try:
            await _supervisor_task
        except asyncio.CancelledError:
            pass
    _supervisor_task = None
    if _mqtt_task and not _mqtt_task.done():
        _mqtt_task.cancel()
        try:
            await _mqtt_task
        except asyncio.CancelledError:
            pass
    _mqtt_task = None
    await _stop_worker(ctx)
    ctx.log.info("AWBlackJack 插件已停用")
