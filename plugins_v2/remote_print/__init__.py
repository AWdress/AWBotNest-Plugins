"""AWBotNest V2 远程打印：FRP / IPP 直连与可选 Windows 打印端。"""

__plugin__ = {
    "id": "remote_print",
    "name": "远程打印",
    "version": "0.0.7",
    "author": "AWdress",
    "repository": "AWdress/AWBotNest-Plugins",
    "scope": "standalone",
    "instance_mode": "shared",
    "plugin_api_version": 2,
    "render_mode": "schema",
    "webhook": True,
    "description": "通过平台 Telegram Bot 或企业微信自建应用发送 PDF、图片，点“打印一份”即可；支持打印两份、取消和查看进度，使用 IPP 直连或 Windows 打印端。",
    "changelog": "v0.0.7 配置页面说明与默认值\n- 按连接打印机、家人名单、开始接收分组，逐项补充中文说明与填写示例\n- 修复说明框空白，启用时仅保存缺失的默认值，不覆盖用户已有配置\n- 高级连接参数和限制默认收起，开关全部默认关闭\n- 说明后台检查频率，轮询不会重复打印同一任务\n\nv0.0.6 定时任务名称中文化\n- 打印任务处理、打印机器人连接检查、打印文件清理使用中文名称\n- 保持原有执行频率与打印逻辑不变\n\nv0.0.5 简化聊天打印操作\n- Telegram 和企业微信提供打印一份、打印两份、取消打印、查看进度按钮\n- 单个未结束文件可直接回复打印或取消，多个文件必须选择对应按钮\n- 操作消息持久去重，重复点击或回调不重复打印\n- 同步平台最新企微校验，支持官方合法 AESKey 和大小写不敏感的成员 ID\n- 操作在队列锁内重新检查授权，撤权或更换入口后不确认打印\n\nv0.0.4 适配平台企业微信回调配置\n- 回调 Token、EncodingAESKey 直接读取平台新增字段，不再生成或读取插件旧密钥\n- 尊重平台消息回调开关和成员授权，缺少配置时停止接收\n- 查看接收配置只显示插件回调地址，不在可远程调用的按钮中返回密钥\n\nv0.0.3 图片完整缩放与平台渠道接入\n- IPP 图片明确使用完整等比缩放，不裁切、不拉伸；设备不支持时停止提交\n- Telegram Bot、企业微信自建应用凭据读取平台配置，移除插件重复设置\n- 企业微信回调密钥自动生成并保存，用按钮查看后复制到企微后台\n- 打印回执只发送给原始上传人，切换应用不发送旧任务到其他应用\n\nv0.0.2 增加 FRP / IPP 直连并修复安装\n- 新增 VPS 直连 IPP 模式、只读连接测试及打印机能力检查\n- PDF/JPEG 直接提交，其他支持图片转 JPEG；不依赖 Windows 电脑\n- 切换打印模式或目标不会把旧任务送到另一台打印机；不重试有歧义的提交\n- 移除发布目录内的隐藏文件，修复平台安装器拒绝安装\n\nv0.0.1 首次发布\n- Telegram 与企业微信共用持久打印队列\n- 配套 Windows 打印端，主动连接服务器，无需开放电脑端口\n- 默认关闭自动打印，按用户授权，断线与重启不自动重打已提交任务\n- 支持 PDF、JPG、PNG、WebP、BMP；打印成功表示系统队列已接收，不代表实际出纸",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/remote_print/icon.svg",
    "tags": ["打印机", "Telegram", "企业微信"],
    "requirements": ["cryptography>=44,<47", "defusedxml>=0.7,<1", "Pillow>=11,<13", "pypdf>=6,<7"],
    "resources": {"timeout_seconds": 180, "max_concurrency": 8, "max_background_tasks": 16},
    "config_schema": {
        "usage": {
            "type": "info", "label": "第一次设置与日常使用", "section": "使用说明", "order": 1,
            "text": "家人打印：把照片或 PDF 发给平台机器人，再点“打印一份”。不用输入任务编号。\n第一次设置：连接打印机 → 填允许打印的家人 → 保存并测试连接 → 开启接收打印文件。\n新安装如果默认数值为空，请先在插件列表启用一次“远程打印”，再重新打开配置。加载插件不会自动开始打印。\n支持 PDF、JPG、PNG、WebP、BMP。Word、Excel 请先另存为 PDF；图片完整缩放，不裁切，比例不同会留白。",
        },
        "print_mode": {
            "type": "select", "default": "ipp", "label": "打印机如何连接", "section": "连接打印机", "order": 1, "cols": 12,
            "options": [{"value": "ipp", "label": "直接连接网络打印机（推荐）"}, {"value": "agent", "label": "通过 Windows 电脑打印"}],
            "help": "默认直接连接网络打印机。打印机接入家里网络且支持 IPP 时选第一项；只有电脑能使用打印机时选第二项，需要运行配套电脑端程序。",
        },
        "ipp_url": {
            "type": "string", "default": "", "label": "打印机访问地址（直连时必填）", "section": "连接打印机", "order": 2, "cols": 12,
            "show_if": {"print_mode": "ipp"},
            "help": "填写平台所在机器能访问的打印地址，不是打印机管理网页。例如 http://192.168.1.50:631/ipp/print，请换成自己的打印机 IP。同一局域网不用 FRP；远程穿透填写实际映射地址和端口。地址因人而异，默认留空。",
        },
        "test_ipp": {
            "type": "action", "label": "检查能否连接打印机（不打印）", "action": "test_ipp", "section": "连接打印机", "order": 3,
            "show_if": {"print_mode": "ipp"}, "help": "先保存上面的地址，再点击检查。只读取打印机状态和支持格式，不会消耗纸张。",
        },
        "device_id": {
            "type": "string", "default": "home-printer", "label": "电脑端设备名称", "section": "连接打印机", "order": 4, "cols": 12,
            "show_if": {"print_mode": "agent"}, "help": "默认 home-printer，通常不用改。将相同名称填入电脑端的 device_id，让平台认出这台电脑。",
        },
        "device_token": {
            "type": "password", "secret": True, "default": "", "label": "电脑端连接密钥", "section": "连接打印机", "order": 5, "cols": 12,
            "show_if": {"print_mode": "agent"}, "help": "首次使用默认留空，请点击下方生成密钥，重新打开配置后点眼睛查看，再复制到电脑端的 device_token。不要填写平台登录密码，也不要把密钥发给别人。",
        },
        "generate_device_token": {
            "type": "action", "label": "生成电脑端连接密钥", "action": "generate_device_token", "danger": True, "section": "连接打印机", "order": 6,
            "show_if": {"print_mode": "agent"}, "help": "已有密钥时点击会更换密钥，旧电脑端将无法连接，必须同步更新电脑端配置。",
        },
        "printer_name": {
            "type": "string", "default": "", "label": "电脑上使用哪台打印机（可留空）", "section": "连接打印机", "order": 7, "cols": 12,
            "show_if": {"print_mode": "agent"}, "help": "默认留空，使用电脑端选定的系统默认打印机。需要指定时，填写 Windows 显示的完整打印机名称，并在电脑端允许列表中添加同名打印机。",
        },
        "channels_usage": {
            "type": "info", "label": "机器人与家人名单", "section": "允许谁打印", "order": 1,
            "text": "Telegram 机器人、企业微信应用和回调密钥都从平台读取，不用在这里重复填写。\n只填你准备使用的名单：只用 Telegram 可以不填企微名单，只用企微可以不填 Telegram 名单。名单留空表示该渠道不允许任何人打印，不是允许所有人。",
        },
        "telegram_users": {
            "type": "text", "default": "", "label": "允许打印的 Telegram 用户 ID", "section": "允许谁打印", "order": 2,
            "help": "填写家人的数字用户 ID，例如 123456789；每行一个，也可用逗号分隔。不是用户名、手机号或群 ID。默认留空，拒绝所有人。只接收与平台机器人的私聊文件；可用“Telegram 助手”查询用户 ID。",
        },
        "wecom_users": {
            "type": "text", "default": "", "label": "允许打印的企业微信成员账号", "section": "允许谁打印", "order": 3,
            "help": "填写企业微信通讯录中的成员账号（UserID），例如 zhangsan，不是姓名或手机号；每行一个或用逗号分隔，不区分大小写。同一成员也必须在平台应用的消息回调名单中授权。默认留空，拒绝所有人。",
        },
        "public_base_url": {
            "type": "string", "default": "", "label": "平台访问地址（企微或电脑端使用）", "section": "允许谁打印", "order": 4, "cols": 12,
            "help": "使用企微或 Windows 电脑端时填写平台的 HTTPS 地址，例如 https://bot.example.com；有部署子路径也要带上。不要填写打印机地址、/api 路径或密码。只用 Telegram 直连打印机时可留空。",
        },
        "show_wecom_setup": {
            "type": "action", "label": "查看要填到企微后台的接收地址", "action": "show_wecom_setup", "section": "允许谁打印", "order": 5,
            "help": "先保存平台访问地址，再点击查看。把打印接收地址填入企微自建应用的“接收消息”设置；Token 和 EncodingAESKey 复制平台渠道中的值。必须使用自建应用，群机器人不能接收打印文件。",
        },
        "enabled": {
            "type": "boolean", "default": False, "label": "接收打印文件", "section": "开始接收", "order": 1, "cols": 12,
            "help": "默认关闭。完成打印机和家人名单配置后再开启；关闭后不接受新的文件和打印操作。保存后生效。",
        },
        "auto_print": {
            "type": "boolean", "default": False, "label": "收到文件直接打印（不需要确认）", "section": "开始接收", "order": 2, "cols": 12,
            "help": "默认关闭，推荐保持关闭：家人发文件后点“打印一份”才打印，避免误发文件浪费纸。开启后，名单内用户的文件会直接进入打印队列。",
        },
        "show_advanced": {
            "type": "boolean", "default": False, "label": "显示高级设置", "section": "高级设置", "order": 1, "cols": 12,
            "help": "默认关闭。通常不用改；打开后可以调整份数、文件限制、保留时间和特殊连接参数。收起不会删除已保存的高级设置。",
        },
        "advanced_usage": {
            "type": "info", "label": "推荐默认值与后台检查", "section": "高级设置", "order": 2, "show_if": {"show_advanced": True},
            "text": "推荐默认值：每次 1 份、最多 3 份；每个文件最多 20 MB、50 页；最多 30 个未结束任务，缓存最多 200 MB，保留 24 小时。\n网络直连模式每 3 秒查看已确认任务；电脑模式由电脑端领取任务，默认每 5 秒一次。两种模式均每 10 秒检查机器人连接，每 1 分钟清理到期文件；没有任务不会打印，轮询不会重复打印同一任务。",
        },
        "ipp_printer_uri": {
            "type": "string", "default": "", "label": "打印机内部地址（通常留空）", "section": "高级设置", "order": 3, "cols": 12,
            "show_if": {"show_advanced": True, "print_mode": "ipp"}, "help": "默认留空，自动读取打印机报告的地址。只有穿透连接需要指定时才填，例如 ipp://192.168.1.50:631/ipp/print；这不是上面的 HTTP 访问地址。",
        },
        "ipp_timeout_seconds": {
            "type": "number", "default": 30, "min": 5, "max": 120, "label": "连接打印机最多等待多少秒", "section": "高级设置", "order": 4, "cols": 12,
            "show_if": {"show_advanced": True, "print_mode": "ipp"}, "help": "默认 30 秒，可填 5～120 秒。网络较慢时可适当增加；超时且结果不确定时不会自动重打。",
        },
        "default_copies": {
            "type": "number", "default": 1, "min": 1, "max": 5, "label": "默认打印几份", "section": "高级设置", "order": 5, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认 1 份。用于自动打印或未指定份数的高级命令；点“打印一份”或回复“打印”仍然只打印 1 份，实际份数不会超过下面的上限。",
        },
        "max_copies": {
            "type": "number", "default": 3, "min": 1, "max": 5, "label": "一份文件最多允许打印几份", "section": "高级设置", "order": 6, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认最多 3 份，可填 1～5。设为 1 时不显示“打印两份”按钮；打印机不支持所选份数时会拒绝提交。",
        },
        "max_pages": {
            "type": "number", "default": 50, "min": 1, "max": 50, "label": "一份文件最多允许多少页", "section": "高级设置", "order": 7, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认最多 50 页，可填 1～50。超过上限会拒绝整份文件，不会只打印前面几页；单张图片按 1 页计算。",
        },
        "max_file_mb": {
            "type": "number", "default": 20, "min": 1, "max": 25, "label": "一份文件最大多大（MB）", "section": "高级设置", "order": 8, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认 20 MB，可填 1～25。超过上限会拒绝收取，较大的文档请先压缩或分成多个 PDF。",
        },
        "max_queue": {
            "type": "number", "default": 30, "min": 1, "max": 100, "label": "最多保留多少个未结束任务", "section": "高级设置", "order": 9, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认 30 个，可填 1～100。包括待确认、排队、正在打印和结果待核查的任务；满额后拒绝新文件，不删除现有任务。",
        },
        "max_storage_mb": {
            "type": "number", "default": 200, "min": 25, "max": 1000, "label": "打印缓存最多占用多少空间（MB）", "section": "高级设置", "order": 10, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认 200 MB，可填 25～1000。包括待打印和暂存的已结束文件；达到上限拒绝新文件，不删除正在打印的文件。",
        },
        "retention_hours": {
            "type": "number", "default": 24, "min": 1, "max": 168, "label": "打印文件保留多久（小时）", "section": "高级设置", "order": 11, "cols": 12,
            "show_if": {"show_advanced": True}, "help": "默认 24 小时，可填 1～168。超时未打印的任务取消，已结束任务的文件到期删除；正在提交或结果待核查的任务不自动重打。",
        },
        "cleanup_files": {
            "type": "action", "label": "清理已结束任务的缓存文件", "action": "cleanup_files", "danger": True, "section": "高级设置", "order": 12,
            "show_if": {"show_advanced": True}, "help": "立即清理已提交、失败、取消等已结束任务的缓存，保留最近的任务记录。结果待核查的文件仅到保留期限后清理；正在提交的文件不立即删除。此操作不取消打印机队列，也不会重新打印。",
        },
        "archive_unknown": {
            "type": "action", "label": "已人工核查的任务归档（不重打）", "action": "archive_unknown", "danger": True, "section": "高级设置", "order": 13,
            "show_if": {"show_advanced": True}, "help": "只有确认过打印机队列和实际出纸后才点击。将全部“结果待核查”任务归档、解除队列占用，不会重新打印，也不会取消打印机中的任务。",
        },
        "show_connection": {
            "type": "action", "label": "查看打印机与接收地址", "action": "show_connection", "section": "查看打印状态", "order": 1,
            "help": "查看当前连接方式、打印机状态和企微接收地址，不会发送打印任务。",
        },
        "show_jobs": {
            "type": "action", "label": "查看最近的打印任务", "action": "show_jobs", "section": "查看打印状态", "order": 2,
            "help": "查看文件是否待确认、正在排队或已提交。“已提交”只表示打印机接收了任务，是否出纸请到打印机旁确认。",
        },
    },
}


async def setup(ctx):
    from .core import setup as start
    await start(ctx)


async def teardown(ctx):
    from .core import teardown as stop
    await stop(ctx)
