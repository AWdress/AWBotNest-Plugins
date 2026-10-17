"""通过平台 Telegram Bot 发布更新、回复文档问题并收取问题反馈。"""

__plugin__ = {
    "id": "platform_release",
    "name": "开发者助手",
    "version": "0.0.3",
    "author": "AWdress",
    "scope": "bot",
    "instance_mode": "shared",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "default_enabled": False,
    "description": "使用平台 Telegram Bot 发布 AWBotNest 最新版本并置顶，支持自定义关键词回复、内置手册原文问答和问题反馈，临时答复到时自动清理。",
    "changelog": "v0.0.3\n- 更名开发者助手，保留发布缓存和原有发布设置\n- 新增自定义关键词回复，内置 v2.0.1.6 手册的 11 篇文档，离线检索原文与来源链接\n- 问答不请求 GitHub Wiki，手册随插件升级更新\n- 新增 #bug反馈 通知平台主人，不规范时提示填写方式\n- 临时答复支持延迟删除、持久队列与重启恢复，不删除公告和用户原文\nv0.0.2\n- 新增包含预发行版开关，按发布时间只选最新一条，草稿不发送\n- 分页及条件缓存按接口隔离，切换版本类型不回发旧版\n- 通知标注预发行版，同一发布转为正式版不重复发送，兼容原缓存\nv0.0.1 首次发布\n- 使用平台 Telegram Bot 发布最新正式版本并置顶\n- 持久化缓存及逐目标防重，默认关闭自动检查，检查间隔 15 分钟",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/platform_release/icon.svg?v=0.0.3",
    "tags": ["开发者助手", "版本更新", "Telegram Bot", "Wiki问答"],
    "requirements": [],
    "resources": {"timeout_seconds": 300, "max_concurrency": 4, "max_background_tasks": 1},
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
            "section": "发布设置", "order": 10,
        },
        "show_status": {
            "type": "action", "action": "show_status", "label": "查看发布记录",
            "help": "读取缓存、各目标发布和置顶状态，不发送消息；执行后关闭并重新打开配置页，在下方查看具体结果。",
            "section": "发布设置", "order": 11,
        },
        "retry_uncertain": {
            "type": "action", "action": "retry_uncertain", "danger": True,
            "label": "确认未发送并重试",
            "help": "仅在目标群/频道核对确实未收到后使用；网络中断可能实际已发送，盲目重试会重复。只恢复发送结果不明确的目标，不清除成功记录。执行后关闭并重新打开配置页查看具体结果。",
            "section": "发布设置", "order": 12,
        },
        "last_result": {
            "type": "info", "default": "尚未检查", "label": "检查结果与发布记录",
            "section": "发布设置", "cols": 12, "order": 20,
        },
        "keyword_enabled": {
            "type": "boolean", "default": False, "label": "启用关键词回复",
            "help": "默认关闭。开启后先匹配下方规则，命中只回复这一条，不再检索 Wiki。不会回复其他机器人或频道广播消息。",
            "section": "关键词回复", "order": 30,
        },
        "keyword_rules": {
            "type": "list", "label": "关键词与回复内容", "item_label": "回复规则",
            "default": [
                {"keywords": "最新版本,版本", "match": "exact", "reply": "当前最新版本：{version}\n{release_url}"},
                {"keywords": "帮助", "match": "exact", "reply": "使用文档：{wiki_url}\n提交问题请以 #bug反馈 开头，并说明版本、操作步骤和报错。"},
            ],
            "help": "按列表顺序匹配，命中第一条后停止。多个关键词用逗号分隔；回复按纯文本发送，可换行。支持变量 {version}（最新版本）、{release_url}（发布链接）、{wiki_url}（使用文档）。修改后请保存。",
            "fields": {
                "keywords": {
                    "type": "string", "default": "", "label": "关键词",
                    "help": "例如：最新版本,版本。多个关键词用英文或中文逗号分隔。",
                },
                "match": {
                    "type": "select", "default": "exact", "label": "匹配方式",
                    "options": [{"value": "exact", "label": "完全一致"}, {"value": "contains", "label": "包含关键词"}],
                    "help": "完全一致：整条消息等于关键词；包含关键词：消息中出现关键词即可。",
                },
                "reply": {
                    "type": "text", "default": "", "label": "回复内容",
                    "help": "直接填写要回复的文字，可换行；不解析 HTML 或 Markdown。",
                },
            },
            "section": "关键词回复", "cols": 12, "order": 31,
        },
        "wiki_enabled": {
            "type": "boolean", "default": False, "label": "启用 Wiki 问答",
            "help": "默认关闭。从插件内置手册离线检索问题，回复相关原文及 Wiki 来源链接。不请求 GitHub Wiki、不额外调用 AI、不编造答案；关键词命中时不再检索。内置手册为 v2.0.1.6 的 11 篇文档，随插件升级更新。",
            "section": "Wiki问答", "order": 40,
        },
        "refresh_wiki": {
            "type": "action", "action": "refresh_wiki", "label": "重新读取内置文档",
            "help": "重新读取插件包中的离线手册，不连接 GitHub Wiki，也不会下载新手册；手册随插件升级更新。执行后关闭并重新打开配置页，查看下方文档状态。",
            "section": "Wiki问答", "order": 41,
        },
        "wiki_status": {
            "type": "info", "default": "内置手册：v2.0.1.6（11篇）", "label": "内置手册状态",
            "section": "Wiki问答", "cols": 12, "order": 42,
        },
        "bug_feedback_enabled": {
            "type": "boolean", "default": False, "label": "启用问题反馈",
            "help": "默认关闭。用户以 #bug反馈 开头发送问题，Bot 通知平台主人；内容不规范时提示填写方式。建议包含版本、问题、操作步骤和报错，勿发送 Cookie、密码或 API 密钥。主人收件人读取平台默认 Bot 私聊接收人；未填写时由平台账号 SDK 解析，只接受正数用户 ID。主人须先私聊此 Bot 并发送 /start；通知成功后才回复已送达，主人收到的反馈不会自动删除。",
            "section": "问题反馈", "cols": 12, "order": 50,
        },
        "reply_chats": {
            "type": "text", "default": "", "label": "在哪些群组回复",
            "help": "每行填写一个负数群组 ID（如 -1001234567890）或 @群组用户名；留空沿用发布目标中的群组。Bot 私聊在开启任一回复功能后可用；频道广播不答复，频道讨论群需单独填写。群内需把 Bot 设为管理员，或在 BotFather 关闭 Privacy Mode 后重新加群，才能接收普通文字。只使用平台 Bot，不使用人形。",
            "section": "回复范围与清理", "cols": 12, "order": 60,
        },
        "reply_delete_seconds": {
            "type": "number", "default": 60, "min": 0, "max": 86400, "step": 1,
            "label": "回复保留多少秒",
            "help": "默认 60 秒；0 表示不自动删除，最长 86400 秒（1 天）。只删除 Bot 的临时答复和填写提示，不删除用户原文、发布公告（含置顶公告）或发给主人的反馈。手动置顶的临时答复仍按此时间清理。重启后恢复待删队列；插件停用期间不执行。",
            "section": "回复范围与清理", "order": 61,
        },
        "reply_cooldown": {
            "type": "number", "default": 15, "min": 3, "max": 300, "step": 1,
            "label": "同一用户回复间隔（秒）",
            "help": "默认 15 秒，可设 3～300 秒。同一用户短时间连续发消息只回复一次，避免刷屏。",
            "section": "回复范围与清理", "order": 62,
        },
    },
}


async def setup(ctx):
    from .core import setup as setup_core

    await setup_core(ctx)
