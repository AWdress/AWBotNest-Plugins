# =============================================================================
# AWBotNest 插件：发红包（red_packet_send）
#
# 用你的「用户账号」在群里发拼手气红包（验证码防脚本版）：
#   1. 你发命令 `创建红包 总额 个数` 创建活动；
#   2. 系统随机生成一张扭曲验证码图片发到群里作为参与口令；
#   3. 群友肉眼识别验证码、发送图中字符（不区分大小写）参与，脚本无法自动匹配；
#   4. 按拼手气随机分配，用 `+金额` reply 给每个参与者（群转账bot实际打款）；
#   5. 抢完或超时后自动结算公布；创建者可发 `结束红包` 提前结束、`红包状态` 查看进度。
#
# 迁移自 AWLottery plugins/user/games/red_packet.py（InstantRedPacketMonitor）的
# 发包侧。原「固定文本口令 / 贴图口令」参与方式脚本可秒匹配，已重构为验证码图片。
# 验证码用 PIL 纯 Python 绘制（平台 venv 已装 Pillow），见 _captcha.py。
#
# 不依赖平台 service / DB / libs.others：
#   - build_user_markdown_link → _activity.build_user_link
#   - is_user_in_send_blacklist → config 字段「屏蔽用户ID」（blacklist_ids）
# 活动状态为短时进程内内存；后台任务（超时结算、延迟删消息）登记集合，teardown 全 cancel。
# MY_TGID→ctx.owner_id，通知→ctx.notify。
#
# scope=user：靠你的账号发命令 + 收参与 + 发钱。
# =============================================================================
from __future__ import annotations

from ._activity import (
    ActivityManager, cancel_all_tasks, is_create_command, to_int, delete_message,
)

__plugin__ = {
    "name": "发红包",
    "id": "red_packet_send",
    "version": "1.0.9",
    "author": "AWdress",
    "scope": "user",
    "default_enabled": False,
    "render_mode": "vue",
    "description": "用你的账号在群里发拼手气红包：口令（可自定义前缀）+随机防挂码渲染成验证码图片，群友识别并输入完整字符才算参与（防脚本）；可选每抢一个换码，命令消息秒删，按拼手气随机分配并自动发放魔力，每个红包带递增编号便于对照。自带 Vue 配置界面 + 红包监控。",
}

# vue 模式无 config_schema：配置默认值集中此处备查（后端各处 ctx.config.get(k, 默认) 已带默认，
# 前端 Config.vue 用同一套默认初始化表单）。
DEFAULTS = {
    "enabled": True, "create_word": "创建红包", "status_word": "红包状态", "end_word": "结束红包",
    "code_length": 4, "rotate_code": False,
    "max_amount": 0, "max_count": 0, "activity_timeout_minutes": 30, "end_delete_delay": 10,
    "transfer_prefix": "+", "congrats_text": "恭喜 {name} 抢到 {amount} 魔力！",
    "blacklist_ids": "",
}

# 活动管理器（setup 时创建）
_manager: ActivityManager | None = None


async def setup(ctx):
    global _manager
    _manager = ActivityManager(ctx)

    # ───────── 创建红包：你的账号发出命令（outgoing）─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text & ctx.filters.group, group=-10)
    async def on_create(client, message):
        if not ctx.config.get("enabled", True):
            return
        create_word = ctx.config.get("create_word", "创建红包") or "创建红包"
        params = is_create_command(
            message.text,
            create_word,
            to_int(ctx.config.get("max_amount", 0), 0),
            to_int(ctx.config.get("max_count", 0), 0),
        )
        if not params:
            return
        try:
            await _manager.create_redpacket(client, message, params)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 创建活动失败: %r", e)
        finally:
            # 命令秒删：保持群内整洁，也避免口令以可复制的文本形式留在群里
            await delete_message(message)

    # ───────── 查看状态 / 结束：你的账号发出命令（outgoing）─────────
    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text & ctx.filters.group, group=-9)
    async def on_status_or_end(client, message):
        if not ctx.config.get("enabled", True):
            return
        text = (message.text or "").strip()
        status_word = ctx.config.get("status_word", "红包状态") or "红包状态"
        end_word = ctx.config.get("end_word", "结束红包") or "结束红包"
        if text != status_word and text != end_word:
            return
        try:
            if text == status_word:
                await _manager.get_activity_status(client, message.chat.id)
            else:
                await _manager.end_activity_by_user(client, message)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 状态/结束命令失败: %r", e)
        finally:
            await delete_message(message)

    # ───────── 群友参与：群内进来的文本消息（incoming）─────────
    @ctx.on_message(
        ctx.filters.incoming & ctx.filters.group & ctx.filters.text,
        group=5,
    )
    async def on_participation(client, message):
        if not ctx.config.get("enabled", True):
            return
        try:
            await _manager.handle_participation(client, message)
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 处理参与失败: %r", e)

    # ───────── 前端(Config.vue)用的后端接口 ─────────
    @ctx.on_api("/activities", methods=["GET"])
    async def _api_activities(req):
        return {"items": _manager.snapshot() if _manager else []}

    @ctx.on_api("/history", methods=["GET"])
    async def _api_history(req):
        return {"items": _manager.history() if _manager else []}

    @ctx.on_api("/end", methods=["POST"])
    async def _api_end(req):
        data = req.json or {}
        key = data.get("key")
        if not key or not _manager:
            return {"ok": False, "message": "缺少活动标识"}
        try:
            ok = await _manager.end_by_key(str(key))
        except Exception as e:  # noqa: BLE001
            ctx.log.error("[发红包] 前端结束活动失败: %r", e)
            return {"ok": False, "message": f"结束异常：{e}"}
        return {"ok": ok, "message": "已结束" if ok else "未找到进行中的红包"}

    ctx.log.info("[发红包] 已加载")


async def teardown(ctx):
    global _manager
    cancel_all_tasks()
    if _manager is not None:
        _manager.clear()
    _manager = None
