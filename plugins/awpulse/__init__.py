# =============================================================================
# AWBotNest 插件：AWPulse 色花堂助手（awpulse）· Vue 模式
#
# 迁移自独立项目 AWPulse（Playwright/CloakBrowser 浏览器自动化）。功能：账号登录、
# 每日签到、智能回复（模板/规则/特征）、AI 回复、AI 帖子类型识别/过滤、自动发帖、
# 论坛消息、统计、Cookie(storage_state) 管理、定时任务。配置/管理界面由自带 Vue
# 组件渲染（frontend/src/Config.vue，模块联邦）。
#
# 平台落地要点：
# - 浏览器复用平台已装的 Playwright + Chromium（cloakbrowser 走同一内核缓存）；容器无
#   显示器，强制 headless=True。整轮运行（分钟级、同步阻塞）跑在 asyncio.to_thread，
#   绝不阻塞平台事件循环。
# - 砍掉原项目的 License 授权、Flask/PWA/登录、容器自更新（平台负责鉴权与热重载）。
# - 所有可写文件（storage_state / stats / 缓存 / 日志 / 发帖文件夹）落在 ctx.data_dir，
#   通过环境变量 AWPULSE_BASE 注入给 _core（见 _core 里的 base_dir 解析）。
# =============================================================================

import asyncio
import json
import logging
import os
import time
import traceback
from collections import deque
from datetime import datetime

__plugin__ = {
    "name": "AWPulse 色花堂助手",
    "id": "awpulse",
    "version": "0.0.2",
    "author": "AWdress",
    "description": "色花堂论坛自动化：登录/每日签到/智能回复/AI回复/AI帖子过滤/自动发帖/消息统计。基于平台内置浏览器(headless)，定时运行+结果推送，自带 Vue 管理界面。",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    # 平台自带 playwright/ddddocr/opencv/numpy/pillow/bs4/lxml/httpx/apscheduler；
    # 这里只补声明浏览器指纹内核与解析/验证码所需的额外库。
    "requirements": [
        "cloakbrowser>=0.4.9",
        "requests>=2.32.0",
    ],
}

# ── 配置默认值（vue 模式无 config_schema，默认集中在此，供后端/定时任务读取；
#    前端 Config.vue 用同一套默认初始化表单）。源自 AWPulse config.json.example。 ──
DEFAULTS = {
    "base_url": "https://sehuatang.org/",
    "username": "",
    "password": "",
    "security_question_id": "0",
    "security_answer": "",
    # headless 恒为 True（容器无显示器），此处仅占位，运行时强制覆盖。
    "headless": True,
    "enable_auto_reply": True,
    "enable_daily_checkin": True,
    "enable_smart_reply": True,
    "enable_ai_reply": False,
    "enable_ai_post_filter": True,
    "enable_auto_post": False,
    "enable_random_delay": False,
    # 测试模式（只跑单个动作，便于验证流程）
    "enable_test_mode": False,
    "enable_test_checkin": False,
    "enable_test_reply": False,
    "enable_test_post": False,
    "skip_admin_posts": True,
    "max_replies_per_day": 3,
    "reply_interval": [60, 120],
    # 定时：优先 schedule_cron，其次 schedule_times（每天多个时刻），兜底 schedule_time。
    "schedule_cron": "",
    "schedule_times": ["03:00", "09:00", "15:00", "21:00"],
    "schedule_time": "03:00",
    "target_forums": ["fid=141"],
    "forum_names": {
        "fid=141": "网友原创区", "fid=2": "亚洲无码原创区", "fid=36": "亚洲有码原创区",
        "fid=37": "中字原创区", "fid=103": "国产原创区", "fid=139": "色花文学",
    },
    "auto_post": {
        "enabled": False, "target_fid": 139, "category_id": None,
        "post_folder": "novels", "posted_folder": "posted",
        "post_interval": 300, "max_posts_per_day": 5,
        "content_preview_length": 500, "move_after_post": True, "skip_posted_files": True,
    },
    "skip_keywords": [
        "公告", "通知", "规则", "版规", "置顶", "精华", "热门", "APP下载", "白名单",
        "邀请码", "访问方法", "屏蔽", "封禁", "违规", "删除", "警告", "发布器",
        "最新方法", "申诉", "二次验证", "禁止申诉",
    ],
    "skip_prefixes": ["【公告】", "【通知】", "【规则】", "【版规】", "公告:", "通知:", "规则:", "版规:"],
    "admin_usernames": ["admin", "管理员", "版主"],
    "reply_templates": [
        "谢谢楼主分享！", "感谢分享，收藏了！", "好资源，支持一下！", "楼主辛苦了，谢谢分享！",
        "不错的内容，学习了！", "感谢楼主的无私分享！", "收藏了，慢慢看！", "好东西，必须支持！",
    ],
    "smart_reply_templates": {
        "general": ["内容很不错！", "楼主辛苦了！", "感谢分享！", "支持原创！", "很有意思！"],
        "resource": ["资源很棒，感谢分享！", "好东西，必须收藏！", "链接有效，谢谢楼主！", "资源质量很高！"],
        "photo": ["照片拍得真不错！", "颜值很高啊，赞！", "摄影技术很棒！", "拍摄角度很好，学习了！"],
        "video": ["视频质量不错！", "内容很精彩，感谢分享！", "画质清晰，很棒！", "剪辑得很好，专业！"],
        "story": ["好精彩的故事！情节很吸引人！", "写得真好，很有代入感！", "故事很棒，期待后续！"],
    },
    # 自定义特征规则（可选）：{features:{名:{keywords:[],replies:[]}}, generic_fallback:[]}
    "reply_rules": None,
    # AI
    "ai_api_type": "openai",
    "ai_api_url": "",
    "ai_api_key": "",
    "ai_model": "gpt-3.5-turbo",
    "ai_temperature": 0.8,
    "ai_max_tokens": 200,
    "ai_timeout": 10,
    "ai_system_prompt": "你是一个论坛用户，需要根据帖子标题和内容生成简短的回复。回复要自然、简洁，不超过50字。",
    # 代理（AI/浏览器可分别决定是否使用；留空则出站默认走平台代理）
    "proxy": {
        "enabled": False, "http_proxy": "", "https_proxy": "",
        "no_proxy": "localhost,127.0.0.1", "use_for_browser": False, "use_for_ai": True,
    },
    "browser_headers": {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "accept_language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
    "log_level": "INFO",
}

# ── 运行态（单进程内模块级；插件热重载会重置，可接受）──
_RUN = {
    "running": False,
    "task": None,          # 当前 label（手动/定时/消息刷新）
    "started_at": "",
    "finished_at": "",
    "last_result": "",
    "stop": False,
}
_LOG_RING = deque(maxlen=800)   # 供前端「日志」页展示的环形缓冲
_log_handler = None             # 挂到 root 的日志采集器（按 pathname 过滤本插件）


class _RingHandler(logging.Handler):
    """把 AWPulse `_core` 产生的日志（无论用哪个 logger）采集进环形缓冲，供 UI 展示。

    `_core` 大量使用 `logging.info(...)`（root logger），无法靠 logger 名过滤；
    这里按 record.pathname 是否落在本插件目录判定，避免吞掉平台其他日志。
    """

    def __init__(self, marker: str):
        super().__init__()
        self._marker = marker

    def emit(self, record):
        try:
            path = (record.pathname or "").replace("\\", "/")
            if self._marker not in path:
                return
            _LOG_RING.append("%s - %s - %s" % (
                datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                record.levelname,
                record.getMessage(),
            ))
        except Exception:
            pass


def _effective_cfg(ctx) -> dict:
    """默认值 + 已保存配置合并（保存的覆盖默认）。"""
    cfg = {**DEFAULTS, **dict(ctx.config or {})}
    # 容器内无显示器：无论用户如何配置，强制 headless。
    cfg["headless"] = True
    return cfg


def _data_root(ctx) -> str:
    root = str(ctx.data_dir)
    for sub in ("data", "logs", "debug", "novels", "posted"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    return root


def _storage_state_path(ctx) -> str:
    return os.path.join(str(ctx.data_dir), "data", "storage_state.json")


def _stats(ctx):
    """构造 StatsManager（读写 data_dir/data/stats.json）。"""
    os.environ["AWPULSE_BASE"] = _data_root(ctx)
    from ._core.stats_manager import StatsManager
    return StatsManager()


# ────────────────────────── 运行（整轮自动化） ──────────────────────────
def _run_bot_sync(cfg: dict, base: str) -> bool:
    """同步执行整轮：登录 → 回复 → 签到 → 发帖。跑在 to_thread 里，不碰事件循环。"""
    os.environ["AWPULSE_BASE"] = base
    from ._core.playwright_auto_bot import PlaywrightAutoBot
    bot = PlaywrightAutoBot(config=cfg)
    bot.stop_flag = lambda: _RUN["stop"]
    return bool(bot.run())


async def _run(ctx, label: str) -> str:
    """执行一轮自动化并落地状态/通知。返回汇总文本。"""
    if _RUN["running"]:
        return "已有任务在运行中，忽略本次触发"
    cfg = _effective_cfg(ctx)
    if not cfg.get("username") or not cfg.get("password"):
        msg = "未配置论坛账号/密码，跳过"
        ctx.log.warning("[AWPulse] %s", msg)
        return msg

    base = _data_root(ctx)
    _RUN.update(running=True, task=label, stop=False,
                started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                finished_at="", last_result="")
    ctx.log.info("[AWPulse] 开始运行(%s)", label)
    ok = False
    try:
        ok = await asyncio.to_thread(_run_bot_sync, cfg, base)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[AWPulse] 运行异常：%s\n%s", e, traceback.format_exc())
        _RUN.update(running=False, finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    last_result="运行异常：%s" % e)
        if cfg.get("notify", True):
            try:
                await ctx.notify("AWPulse 运行异常：%s" % e, level="error", category="AWPulse")
            except Exception:
                pass
        return "运行异常：%s" % e

    # 汇总今日统计
    try:
        st = _stats(ctx)
        today = st.get_today_stats()
        summary = ("📊 AWPulse · %s\n%s今日回复 %s，签到 %s\n本轮结果：%s" % (
            label,
            "" if ok else "⚠️ 部分步骤失败\n",
            today.get("reply_count", 0),
            "已签到" if today.get("checkin_success") else "未签到",
            "完成" if ok else "失败",
        ))
    except Exception:
        summary = "AWPulse · %s：%s" % (label, "完成" if ok else "失败")

    _RUN.update(running=False, finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_result=summary)
    ctx.update_config({"last_run": _RUN["finished_at"]})
    if cfg.get("notify", True):
        try:
            await ctx.notify(summary, level="success" if ok else "error", category="AWPulse")
        except Exception as e:  # noqa: BLE001 - 通知失败不影响运行结果
            ctx.log.warning("[AWPulse] 结果通知投递失败（不影响运行）：%r", e)
    ctx.log.info("[AWPulse] 完成(%s)：%s", label, "成功" if ok else "失败")
    return summary


# ────────────────────────── 消息刷新（独立浏览器任务） ──────────────────────────
def _refresh_messages_sync(cfg: dict, base: str) -> dict:
    os.environ["AWPULSE_BASE"] = base
    from ._core.playwright_auto_bot import PlaywrightAutoBot
    bot = PlaywrightAutoBot(config=cfg)
    bot.stop_flag = lambda: _RUN["stop"]
    try:
        if not bot.setup_browser():
            return {"ok": False, "message": "浏览器启动失败"}
        logged = False
        if bot.is_cookie_valid():
            try:
                bot.page.goto(bot.base_url + "home.php?mod=space", wait_until="domcontentloaded")
                time.sleep(2)
                logged = bot.check_login_status()
            except Exception:
                logged = False
        if not logged and not bot.login():
            return {"ok": False, "message": "登录失败"}
        # get_messages 返回 {success, messages:[...], total, unread}（不是列表）
        res = bot.message_service.get_messages(max_count=20) if bot.message_service else {}
        if not isinstance(res, dict):
            res = {}
        msgs = res.get("messages", []) or []
        cache = {
            "messages": msgs,
            "total": res.get("total", len(msgs)),
            "unread": res.get("unread", 0),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(os.path.join(base, "data", "messages_cache.json"), "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        return {"ok": True, "count": len(msgs), "unread": cache["unread"]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}
    finally:
        bot.cleanup()


def _read_messages_cache(ctx) -> dict:
    path = os.path.join(str(ctx.data_dir), "data", "messages_cache.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"messages": [], "total": 0, "unread": 0, "timestamp": None}


# ────────────────────────── Cookie(storage_state) 管理 ──────────────────────────
def _cookie_status(ctx) -> dict:
    path = _storage_state_path(ctx)
    if not os.path.exists(path):
        return {"exists": False, "valid": False, "message": "未导入登录状态"}
    try:
        days = (time.time() - os.path.getmtime(path)) / 86400.0
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f).get("cookies", [])
        valid = days <= 7
        return {
            "exists": True, "valid": valid, "age_days": round(days, 1),
            "cookie_count": len(cookies),
            "message": ("有效（已保存 %.1f 天）" % days) if valid else ("已过期（%.1f 天）" % days),
        }
    except Exception as e:  # noqa: BLE001
        return {"exists": True, "valid": False, "message": "读取失败：%s" % e}


# ────────────────────────── 定时任务注册 ──────────────────────────
def _cron_from_cfg(cfg: dict):
    """按配置得到 CronTrigger：优先 schedule_cron；否则由 schedule_times/schedule_time 合成。"""
    from apscheduler.triggers.cron import CronTrigger
    expr = str(cfg.get("schedule_cron") or "").strip()
    if expr:
        return [CronTrigger.from_crontab(expr)]
    times = cfg.get("schedule_times") or ([cfg.get("schedule_time")] if cfg.get("schedule_time") else [])
    triggers = []
    for t in times:
        try:
            hh, mm = str(t).split(":")[:2]
            triggers.append(CronTrigger(hour=int(hh), minute=int(mm)))
        except Exception:
            continue
    return triggers


async def setup(ctx):
    global _log_handler
    _data_root(ctx)

    # 采集 _core 日志到环形缓冲（供 UI）。marker 用插件目录名，避免误采平台日志。
    if _log_handler is None:
        _log_handler = _RingHandler(marker="/awpulse/_core/")
        _log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(_log_handler)

        def _remove_handler():
            global _log_handler
            try:
                if _log_handler is not None:
                    logging.getLogger().removeHandler(_log_handler)
            except Exception:
                pass
            finally:
                # 置空，保证下次启用能重新挂载采集器（否则重载后不再采日志）。
                _log_handler = None
        ctx.add_cleanup(_remove_handler)

    # ── 前端(Config.vue)用的后端接口 ──
    @ctx.on_api("/status", methods=["GET"])
    async def _api_status(req):
        cfg = _effective_cfg(ctx)
        out = {
            "running": _RUN["running"], "task": _RUN["task"],
            "started_at": _RUN["started_at"], "finished_at": _RUN["finished_at"],
            "last_result": _RUN["last_result"], "stop_requested": _RUN["stop"],
            "cookie": _cookie_status(ctx),
        }
        try:
            st = _stats(ctx)
            out["today"] = st.get_today_stats()
            out["user_info"] = st.get_user_info()
        except Exception:
            out["today"], out["user_info"] = {}, {}
        # 下次计划（仅展示配置文本）
        out["schedule"] = cfg.get("schedule_cron") or "、".join(cfg.get("schedule_times") or [])
        return out

    @ctx.on_api("/run", methods=["POST"])
    async def _api_run(req):
        # 整轮跑分钟级：改后台任务，立即返回；结果走通知 + 状态落地，日志见「日志」页。
        if _RUN["running"]:
            return {"ok": False, "message": "已有任务在运行中"}

        async def _bg():
            try:
                await _run(ctx, "手动")
            except Exception as e:  # noqa: BLE001
                ctx.log.error("[AWPulse] 手动运行后台异常：%s\n%s", e, traceback.format_exc())
        asyncio.create_task(_bg())
        return {"ok": True, "started": True,
                "message": "已在后台开始运行。可在「运行状态 / 日志」查看进度，完成后推送通知。"}

    @ctx.on_api("/stop", methods=["POST"])
    async def _api_stop(req):
        if not _RUN["running"]:
            return {"ok": True, "message": "当前没有运行中的任务"}
        _RUN["stop"] = True
        return {"ok": True, "message": "已请求停止，将在当前步骤结束后停下"}

    @ctx.on_api("/stats", methods=["GET"])
    async def _api_stats(req):
        try:
            st = _stats(ctx)
            return {
                "ok": True, "all": st.get_all_stats(),
                "today": st.get_today_stats(), "ai": st.get_ai_stats(),
                "user_info": st.get_user_info(),
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    @ctx.on_api("/posts", methods=["GET"])
    async def _api_posts(req):
        try:
            return {"ok": True, "items": _stats(ctx).get_all_posts(limit=100)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "items": [], "message": str(e)}

    @ctx.on_api("/replies", methods=["GET"])
    async def _api_replies(req):
        try:
            return {"ok": True, "items": _stats(ctx).get_all_replies(limit=100)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "items": [], "message": str(e)}

    @ctx.on_api("/messages", methods=["GET"])
    async def _api_messages(req):
        return {"ok": True, **_read_messages_cache(ctx)}

    @ctx.on_api("/messages/refresh", methods=["POST"])
    async def _api_messages_refresh(req):
        cfg = _effective_cfg(ctx)
        if not cfg.get("username") or not cfg.get("password"):
            return {"ok": False, "message": "未配置论坛账号/密码"}
        if _RUN["running"]:
            return {"ok": False, "message": "有任务运行中，请稍后再刷新消息"}
        try:
            return await asyncio.to_thread(_refresh_messages_sync, cfg, _data_root(ctx))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    @ctx.on_api("/logs", methods=["GET"])
    async def _api_logs(req):
        return {"ok": True, "lines": list(_LOG_RING)}

    @ctx.on_api("/logs/clear", methods=["POST"])
    async def _api_logs_clear(req):
        _LOG_RING.clear()
        return {"ok": True}

    @ctx.on_api("/cookie/check", methods=["GET"])
    async def _api_cookie_check(req):
        return {"ok": True, **_cookie_status(ctx)}

    @ctx.on_api("/cookie/import", methods=["POST"])
    async def _api_cookie_import(req):
        data = req.json or {}
        raw = data.get("storage_state") or data.get("content")
        if not raw:
            return {"ok": False, "message": "请粘贴 storage_state JSON 内容"}
        try:
            obj = raw if isinstance(raw, dict) else json.loads(raw)
            if "cookies" not in obj:
                return {"ok": False, "message": "内容不是有效的 storage_state（缺少 cookies）"}
            path = _storage_state_path(ctx)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            return {"ok": True, "message": "已导入 %d 个 cookie" % len(obj.get("cookies", []))}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": "解析失败：%s" % e}

    @ctx.on_api("/cookie/delete", methods=["POST"])
    async def _api_cookie_delete(req):
        path = _storage_state_path(ctx)
        try:
            if os.path.exists(path):
                os.remove(path)
            return {"ok": True, "message": "已删除登录状态"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    @ctx.on_api("/test_ai", methods=["POST"])
    async def _api_test_ai(req):
        data = req.json or {}
        cfg = _effective_cfg(ctx)
        if not cfg.get("ai_api_url") or not cfg.get("ai_api_key"):
            return {"ok": False, "message": "请先填写 AI 接口地址与密钥"}

        def _do():
            os.environ["AWPULSE_BASE"] = _data_root(ctx)
            from ._core.ai_reply_service import AIReplyService
            svc = AIReplyService({**cfg, "enable_ai_reply": True})
            title = data.get("title") or "【测试】这是一个测试帖子标题"
            content = data.get("content") or "测试内容"
            return svc.generate_reply(title, content)

        try:
            reply = await asyncio.to_thread(_do)
            if reply:
                return {"ok": True, "reply": reply}
            return {"ok": False, "message": "AI 未返回内容（检查地址/密钥/模型/代理）"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}

    # ── 定时任务 ──
    cfg = _effective_cfg(ctx)
    triggers = []
    try:
        triggers = _cron_from_cfg(cfg)
    except Exception as e:  # noqa: BLE001
        ctx.log.error("[AWPulse] 定时表达式无效：%r", e)
    for i, trig in enumerate(triggers):
        ctx.schedule(lambda: asyncio.create_task(_run(ctx, "定时")), trig, id="awpulse_%d" % i)
    if triggers:
        ctx.log.info("[AWPulse] 已注册 %d 个定时触发", len(triggers))


async def teardown(ctx):
    _RUN["stop"] = True
