"""通过平台 Telegram Bot 发布 AWBotNest 最新版本，可包含预发行版。"""

__plugin__ = {
    "id": "platform_release",
    "name": "平台发布通知",
    "version": "0.0.2",
    "author": "AWdress",
    "scope": "bot",
    "instance_mode": "shared",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "default_enabled": False,
    "description": "监测 AWBotNest 最新发布，可选择包含预发行版；通过平台 Telegram Bot 向指定群组或频道发送更新内容并置顶，缓存防旧、逐目标防重。",
    "changelog": "v0.0.2\n- 新增包含预发行版开关，按发布时间只选最新一条，草稿不发送\n- 分页及条件缓存按接口隔离，切换版本类型不回发旧版\n- 通知标注预发行版，同一发布转为正式版不重复发送，兼容原缓存\nv0.0.1 首次发布\n- 使用平台 Telegram Bot 发布最新正式版本并置顶\n- 持久化缓存及逐目标防重，默认关闭自动检查，检查间隔 15 分钟",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/platform_release/icon.svg",
    "tags": ["版本更新", "Telegram Bot", "发布通知"],
    "requirements": [],
    "resources": {"timeout_seconds": 300, "max_concurrency": 2, "max_background_tasks": 1},
    "config_schema": {
        "auto_check": {
            "type": "boolean", "default": False, "label": "自动检查最新版本",
            "help": "默认关闭。开启并保存后按下方间隔检查；首次发布所选类型中的最新版本，后续不补发历史。",
            "section": "发布设置", "order": 1,
        },
        "include_prereleases": {
            "type": "boolean", "default": False, "label": "包含预发行版",
            "help": "默认关闭，只检查正式版。开启后从正式版和预发行版中按发布时间选最新一条；不发送草稿、不补历史。关闭后若正式版更旧，也不会回发旧版。",
            "section": "发布设置", "order": 2,
        },
        "targets": {
            "type": "text", "default": "", "label": "发到哪些群组或频道",
            "help": "每行填写一个群组/频道 ID（例如 -1001234567890）或公开用户名（例如 @your_channel）。不支持用户私聊。先把平台 Bot 加入目标；群组需发送消息、置顶权限，频道需发布消息、编辑消息权限（用于置顶）。发送后固定置顶首条。",
            "section": "发布设置", "cols": 12, "order": 3,
        },
        "check_interval": {
            "type": "number", "default": 15, "min": 5, "max": 1440, "step": 1,
            "label": "每隔多少分钟检查",
            "help": "默认 15 分钟，每天最多约 96 次检查；可设 5～1440 分钟。使用缓存及 GitHub 条件请求，无变化不发消息，不持续占用浏览器。关闭自动检查后不创建定时任务。",
            "section": "发布设置", "order": 4,
        },
        "run_now": {
            "type": "action", "action": "run_now", "label": "检查并发布最新版本",
            "help": "使用已保存的配置。只发送尚未收到最新版本的目标；正文已发出但置顶失败时只补置顶。执行后关闭并重新打开配置页，在下方查看具体结果。",
            "section": "操作", "order": 10,
        },
        "show_status": {
            "type": "action", "action": "show_status", "label": "查看发布记录",
            "help": "读取缓存、各目标发布和置顶状态，不发送消息；执行后关闭并重新打开配置页，在下方查看具体结果。",
            "section": "操作", "order": 11,
        },
        "retry_uncertain": {
            "type": "action", "action": "retry_uncertain", "danger": True,
            "label": "确认未发送并重试",
            "help": "仅在目标群/频道核对确实未收到后使用；网络中断可能实际已发送，盲目重试会重复。只恢复发送结果不明确的目标，不清除成功记录。执行后关闭并重新打开配置页查看具体结果。",
            "section": "操作", "order": 12,
        },
        "last_result": {
            "type": "info", "default": "尚未检查", "label": "检查结果与发布记录",
            "section": "运行状态", "cols": 12, "order": 20,
        },
    },
}


async def setup(ctx):
    from .core import setup as setup_core

    await setup_core(ctx)
