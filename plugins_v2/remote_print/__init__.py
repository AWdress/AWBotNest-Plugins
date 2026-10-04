"""AWBotNest V2 远程打印：FRP / IPP 直连与可选 Windows 打印端。"""

__plugin__ = {
    "id": "remote_print",
    "name": "远程打印",
    "version": "0.0.3",
    "author": "AWdress",
    "repository": "AWdress/AWBotNest-Plugins",
    "scope": "standalone",
    "instance_mode": "shared",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "webhook": True,
    "description": "通过 Telegram 或企业微信自建应用发送 PDF、图片，支持 VPS 经 FRP 直连 IPP 打印机，或由 Windows 打印端领取；提供确认打印、任务查询和取消。",
    "changelog": "v0.0.3 图片完整缩放与平台渠道接入\n- IPP 图片明确使用完整等比缩放，不裁切、不拉伸；设备不支持时停止提交\n- Telegram Bot、企业微信自建应用凭据读取平台配置，移除插件重复设置\n- 企业微信回调密钥自动生成并保存，用按钮查看后复制到企微后台\n- 打印回执只发送给原始上传人，切换应用不发送旧任务到其他应用\n\nv0.0.2 增加 FRP / IPP 直连并修复安装\n- 新增 VPS 直连 IPP 模式、只读连接测试及打印机能力检查\n- PDF/JPEG 直接提交，其他支持图片转 JPEG；不依赖 Windows 电脑\n- 切换打印模式或目标不会把旧任务送到另一台打印机；不重试有歧义的提交\n- 移除发布目录内的隐藏文件，修复平台安装器拒绝安装\n\nv0.0.1 首次发布\n- Telegram 与企业微信共用持久打印队列\n- 配套 Windows 打印端，主动连接服务器，无需开放电脑端口\n- 默认关闭自动打印，按用户授权，断线与重启不自动重打已提交任务\n- 支持 PDF、JPG、PNG、WebP、BMP；打印成功表示系统队列已接收，不代表实际出纸",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/remote_print/icon.svg",
    "tags": ["打印机", "Telegram", "企业微信"],
    "requirements": ["cryptography>=44,<47", "defusedxml>=0.7,<1", "Pillow>=11,<13", "pypdf>=6,<7"],
    "resources": {"timeout_seconds": 180, "max_concurrency": 8, "max_background_tasks": 16},
    "config_schema": {
        "enabled": {"type": "boolean", "default": False, "label": "接收远程打印任务", "section": "基本设置", "order": 1},
        "auto_print": {"type": "boolean", "default": False, "label": "收到文件后自动打印", "help": "关闭时，先收文件，再发送“打印 任务ID”确认。开启后仅授权用户的文件会自动进入打印队列。", "section": "基本设置", "order": 2},
        "print_mode": {"type": "select", "default": "ipp", "label": "打印连接方式", "options": [{"value": "ipp", "label": "VPS / FRP 直连 IPP"}, {"value": "agent", "label": "Windows 电脑打印端"}], "section": "基本设置", "order": 3},
        "public_base_url": {"type": "string", "default": "", "label": "平台外网 HTTPS 地址", "help": "用于显示企微回调地址；Windows 模式也用于电脑端连接。填写域名及必要的部署前缀，不含 /api 路径、密钥或查询参数。", "section": "基本设置", "order": 4},
        "usage": {"type": "info", "default": "支持 PDF、JPG、PNG、WebP、BMP；Office 文档请先另存 PDF。图片完整等比缩放，不裁切、不拉伸；长图会缩小到一页，比例不同会留白。Telegram Bot 和企业微信应用读取平台配置，只需填写打印权限。默认需要确认后打印。", "label": "使用说明", "section": "基本设置", "order": 5},
        "ipp_url": {"type": "string", "default": "", "label": "IPP / FRP 访问地址", "help": "填写服务器容器能访问的地址，例如 http://宿主机地址:FRP映射端口/ipp/print；局域网可直接填 http://打印机IP:631/ipp/print。容器的 127.0.0.1 不是 VPS 宿主机。不要把无鉴权打印端口裸露到公网。", "show_if": {"print_mode": "ipp"}, "section": "IPP / FRP 直连", "order": 6},
        "ipp_printer_uri": {"type": "string", "default": "", "label": "打印机原生 URI（可选）", "help": "通常留空，自动使用打印机报告的 URI。与上面的 FRP 访问地址不同；必要时填写 ipp://打印机局域网IP:631/ipp/print。", "show_if": {"print_mode": "ipp"}, "section": "IPP / FRP 直连", "order": 7},
        "ipp_timeout_seconds": {"type": "number", "default": 30, "min": 5, "max": 120, "label": "IPP 请求超时（秒）", "show_if": {"print_mode": "ipp"}, "section": "IPP / FRP 直连", "order": 8},
        "test_ipp": {"type": "action", "label": "测试 IPP 连接（不打印）", "action": "test_ipp", "help": "只读取打印机名称、状态、格式及份数能力，不发送打印任务。", "show_if": {"print_mode": "ipp"}, "section": "IPP / FRP 直连", "order": 9},
        "channels_usage": {"type": "info", "default": "渠道凭据在平台统一设置，插件不再填写 Bot Token、CorpID、AgentID 或应用 Secret。多个企业微信应用时，在平台通知路由中绑定本插件使用的应用。群机器人只能发通知，不能接收打印文件。", "label": "平台消息渠道", "section": "消息接入与权限", "order": 10},
        "telegram_users": {"type": "text", "default": "", "label": "允许打印的 Telegram 用户 ID", "help": "这是打印权限，不是 Bot 配置。每行一个数字用户 ID，也可用逗号分隔；留空拒绝所有人。仅接收私聊。", "section": "消息接入与权限", "order": 11},
        "wecom_users": {"type": "text", "default": "", "label": "允许打印的企业微信成员 UserID", "help": "这是打印权限。每行一个成员 UserID，也可用逗号分隔；不是手机号或昵称。留空拒绝所有人。", "section": "消息接入与权限", "order": 12},
        "show_wecom_setup": {"type": "action", "label": "查看企业微信接收配置", "action": "show_wecom_setup", "help": "读取平台自建应用，首次自动生成回调 Token 和 AESKey；复制到企业微信后台“接收消息”。只向管理员显示，不会更换已生成的密钥。", "section": "消息接入与权限", "order": 13},
        "device_id": {"type": "string", "default": "home-printer", "label": "电脑端设备 ID", "help": "需与电脑端配置一致。本版连接一台 Windows 电脑，可选择该电脑的多台打印机。", "show_if": {"print_mode": "agent"}, "section": "电脑连接", "order": 30},
        "device_token": {"type": "password", "secret": True, "default": "", "label": "电脑端连接密钥", "help": "至少 32 个字符；可点下方按钮生成，再用眼睛读取，复制到电脑端配置。不要使用平台管理员密码。", "show_if": {"print_mode": "agent"}, "section": "电脑连接", "order": 31},
        "generate_device_token": {"type": "action", "label": "生成 / 更换电脑端密钥", "action": "generate_device_token", "danger": True, "help": "更换后旧打印端不能连接，需要更新电脑端配置。", "show_if": {"print_mode": "agent"}, "section": "电脑连接", "order": 32},
        "printer_name": {"type": "string", "default": "", "label": "默认目标打印机", "help": "留空使用电脑端系统默认打印机；填写时必须与电脑端“允许打印机”中的完整名称一致。", "show_if": {"print_mode": "agent"}, "section": "电脑连接", "order": 33},
        "show_connection": {"type": "action", "label": "查看回调地址与打印机", "action": "show_connection", "section": "任务管理", "order": 49},
        "default_copies": {"type": "number", "default": 1, "min": 1, "max": 5, "label": "默认打印份数", "section": "安全限制", "order": 40},
        "max_copies": {"type": "number", "default": 3, "min": 1, "max": 5, "label": "单任务最多份数", "section": "安全限制", "order": 41},
        "max_pages": {"type": "number", "default": 50, "min": 1, "max": 50, "label": "单份最多页数", "section": "安全限制", "order": 42},
        "max_file_mb": {"type": "number", "default": 20, "min": 1, "max": 25, "label": "单文件上限（MB）", "section": "安全限制", "order": 43},
        "max_queue": {"type": "number", "default": 30, "min": 1, "max": 100, "label": "最多活动任务数", "section": "安全限制", "order": 44},
        "max_storage_mb": {"type": "number", "default": 200, "min": 25, "max": 1000, "label": "文件存储总上限（MB）", "help": "包括待确认、排队和最近完成的文件；到达上限拒绝新文件，不删除正在打印的任务。", "section": "安全限制", "order": 45},
        "retention_hours": {"type": "number", "default": 24, "min": 1, "max": 168, "label": "文件保留时间（小时）", "help": "超时未确认的任务取消；已完成文件到期清理。已开始的任务不重排，不自动重打。", "section": "安全限制", "order": 46},
        "show_jobs": {"type": "action", "label": "查看最近打印任务", "action": "show_jobs", "section": "任务管理", "order": 50},
        "cleanup_files": {"type": "action", "label": "清理已结束任务的文件", "action": "cleanup_files", "danger": True, "help": "只删除已提交、失败、取消的任务文件；未知结果任务先核查打印机，不自动重打。", "section": "任务管理", "order": 51},
        "archive_unknown": {"type": "action", "label": "待核查任务归档（不重打）", "action": "archive_unknown", "danger": True, "help": "先核查打印机队列和实际出纸。此按钮将所有“结果待核查”任务归档，不会重打或取消打印机中的任务。", "section": "任务管理", "order": 52},
    },
}


async def setup(ctx):
    from .core import setup as start
    await start(ctx)


async def teardown(ctx):
    from .core import teardown as stop
    await stop(ctx)
