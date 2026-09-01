"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from ._compat import adapt
from ._legacy import setup as _legacy_setup
try:
    from ._legacy import DEFAULTS as _legacy_defaults
except ImportError:
    _legacy_defaults = {}
try:
    from ._legacy import teardown as _legacy_teardown
except ImportError:
    _legacy_teardown = None

__plugin__ = {'name': 'AWRelay',
 'id': 'awrelay',
 'version': '1.2.10',
 'author': 'AWdress',
 'description': '轻量自托管的 Telegram 私聊消息中转机器人。访客私聊转发到群组论坛话题，管理员在对应话题内回复用户。内置人机验证、广告过滤、黑名单。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/awrelay/logo.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.8 修复话题匹配\n'
              '- 修复 General 话题（thread_id=0）误命中无 topic_id 的待处理记录\n'
              '\n'
              'v1.2.7 新增启动通知开关\n'
              '- 配置页新增「启动时在中转群发通知」开关，可关闭插件启用时向中转群发送的 AWRelay 已启动通知\n'
              '- 默认开启，保持原有行为\n'
              '\n'
              'v1.2.6 移除 Bot 私聊话题模式\n'
              '- 移除不稳定的 Bot 私聊话题创建、核验和消息路由功能\n'
              '- 配置界面恢复为仅支持群组论坛话题\n'
              '- 已保存的 topic_mode 配置将被忽略，群组转发继续使用话题群组 ID\n'
              '\n'
              'v1.2.5 修复 Bot 私聊消息未进入对应话题\n'
              '- Bot 模式改用 message.copy 并传入 message_thread_id，由 Pyrogram 正确构造私聊话题路由\n'
              '- 文本、图片、文件及其他媒体统一投递到用户对应话题\n'
              '- 群组模式继续使用原有服务端无署名复制，不改变现有行为\n'
              '\n'
              'v1.2.4 恢复 Bot 私聊话题删除检测\n'
              '- 每次转发前按用户标题查询并核验已保存的私聊话题 ID\n'
              '- 话题被删除或关闭后清除旧映射并自动新建，与群组模式一致\n'
              '- 存在同用户有效话题时优先复用，查询失败时停止操作以避免重复创建\n'
              '\n'
              'v1.2.3 修复 Bot 私聊话题投递协议\n'
              '- 私聊话题改用 InputReplyToMessage 路由，不再使用群组专用 top_msg_id\n'
              '- Bot 模式不再用群组标题结构误判话题已删除\n'
              '- 私聊响应缺少 reply_to_top_id 或消息 ID 时按成功处理，避免误报和反复重建\n'
              '\n'
              'v1.2.2 修复 Bot 私聊重复创建话题\n'
              '- 使用 Pyrogram 官方话题创建接口直接解析私聊话题 ID\n'
              '- 创建响应异常时先回查实际话题，不再立即重复创建\n'
              '- 无法确认话题 ID 时停止转发并给出明确错误，防止连续生成重复话题\n'
              '\n'
              'v1.2.1 复用管理员 ID 作为私聊目标\n'
              '- Bot 私聊话题模式直接使用管理员用户 ID 中的第一个 ID\n'
              '- 私聊模式不再显示重复的管理员私聊 ID 输入框\n'
              '- 群组模式继续独立保留话题群组 ID 配置\n'
              '\n'
              'v1.2.0 支持 Bot 私聊话题模式\n'
              '- 新增群组论坛话题与 Bot 私聊话题两种中转模式\n'
              '- Bot 模式使用 Telegram 私聊话题接口创建、核验和投递用户消息\n'
              '- 保留原有群组配置兼容性，并避免管理员私聊消息被当成访客消息转发\n'
              '\n'
              'v1.1.16 修复并发消息重复创建话题\n'
              '- 为每个私聊用户增加独立异步锁，串行执行话题核验、创建和消息发送\n'
              '- 同一用户短时间连续发送只会创建一个话题，不同用户仍可并发\n'
              '- 媒体组复用相同串行转发路径，避免与普通消息并发重复建话题\n'
              '\n'
              'v1.1.15 校验实际投递话题并自动纠正\n'
              '- 检查 Telegram 发送响应中的真实话题 ID，不再只相信发送参数\n'
              '- 发现消息降级到全部时立即撤回误投消息、清除映射并新建话题\n'
              '- 强制重建时跳过旧话题扫描缓存，确保不会再次复用已删除话题\n'
              '\n'
              'v1.1.14 修复已删除话题仍投递到全部\n'
              '- 每次转发前向 Telegram 核验本地话题 ID，不再永久信任已校验标记\n'
              '- 发现话题已删除、关闭或标题不匹配时立即清除映射并新建话题\n'
              '- 消息只在取得有效话题后发送，避免失效 ID 降级进入全部\n'
              '\n'
              'v1.1.13 对齐 AWRelay 原项目消息复制逻辑\n'
              '- 所有消息统一逐条执行 Telegram 服务端 copy，不再区分文本和媒体发送\n'
              '- 相册恢复原项目的逐条复制方式，避免批量 RPC 对转发媒体的兼容问题\n'
              '- 保留原消息实体、网页预览、说明文字和媒体属性\n'
              '\n'
              'v1.1.12 修复图片和文件无法转发\n'
              '- 非文本消息改由 Telegram 服务器端无署名复制，不再依赖 file_id 二次发送\n'
              '- 支持别人转发来的图片、文件、视频、贴纸及其他媒体\n'
              '- 媒体组按原顺序批量复制到对应话题并保存回复映射\n'
              '\n'
              'v1.1.11 修复转发消息丢失与话题误判\n'
              '- 优先使用 GetForumTopicsByID 直接核验本地话题，避免数字搜索漏报\n'
              '- 旧 v3 映射强制重新核验，确认标题归属后才允许复用\n'
              '- 保留文本网页预览，补充动画和特殊转发消息兜底\n'
              '\n'
              'v1.1.10 修复话题列表拉黑操作\n'
              '- 按平台请求规范读取 req.json 属性，修复 /ban API 异常\n'
              '- 拉黑与解除统一写入持久化 KV，并返回实际状态\n'
              '- 前端校验后端确认结果并同步刷新黑名单计数\n'
              '\n'
              'v1.1.9 修复私聊投递到错误话题\n'
              '- 使用 Telegram 原始 GetForumTopics 按用户 ID 核验真实话题\n'
              '- 废弃旧 reconciled_v2 映射并重新校验标题与话题 ID\n'
              '- 查询失败时停止转发，避免盲用错误映射或创建重复话题\n'
              '\n'
              'v1.1.8 修复 Pyrogram 发送结果解析缺陷\n'
              '- 文本转发改走底层 Telegram RPC，绕过 Bot Updates 缺少 users 导致的空结果\n'
              '- 从原始响应提取已发送消息 ID，恢复消息映射并验证真实送达\n'
              '- 媒体空返回降为调试信息，不再产生误导性警告\n'
              '\n'
              'v1.1.7 修复发送成功误报失败\n'
              '- 避开 Message.copy 空返回，改为按内容类型显式发送一次\n'
              '- Telegram 不返回消息对象时不再误报失败或重复转发\n'
              '\n'
              'v1.1.6 修复 Bot 兼容性异常\n'
              '- 改从群历史服务消息识别旧话题，绕过 get_forum_topics 解析错误\n'
              '- 全部 HTML 消息改用平台当前 Pyrogram 支持的 ParseMode 枚举\n'
              '- 话题创建或消息复制返回空值时自动恢复并显式重发\n'
              '\n'
              'v1.1.5 修复消息落入全部并恢复启动通知\n'
              '- 话题发送同时携带 thread 与 top message 参数，确保消息进入对应话题\n'
              '- 插件启用时向中转群发送 AWRelay 已启动通知\n'
              '\n'
              'v1.1.4 修复话题复用与消息转发\n'
              '- 使用 message_thread_id 正确投递到论坛话题\n'
              '- 自动认领独立版已有话题，重复话题优先复用最早的有效话题\n'
              '- 收紧失效话题重建条件，避免转发异常时误建重复话题\n'
              '\n'
              'v1.1.3 改为按钮式人机验证\n'
              '- 随机生成四个答案选项，用户点击即可验证\n'
              '- 答错后自动更换题目，并阻止他人代点验证\n'
              '\n'
              'v1.1.2 补充插件 Logo\n'
              '- 迁移 AWRelay 原项目 Logo，并同步插件卡片与市场图标\n'
              '\n'
              'v1.1.1 修正定时任务显示\n'
              '- 旧消息映射清理改为每天凌晨 04:00 执行，避免状态页误显示每 0 秒\n'
              '\n'
              'v1.1.0 完成核心功能迁移并适配新版平台\n'
              '- 修复 Vue 配置保存时报 post 未定义的问题\n'
              '- 话题、消息映射、验证状态和黑名单改为持久化存储\n'
              '- 修复管理员消息监听与普通话题消息双向路由\n'
              '- 增加媒体组聚合、失效话题重建、转发失败提示及黑名单管理\n'
              '- 全部运行接口改用 ctx 平台能力\n'
              '\n'
              'v1.0.3 改为随机人机验证题\n'
              '- 每位待验证用户随机生成加减乘算术题\n'
              '- 配置页不再要求填写固定问题和答案\n'
              '\n'
              'v1.0.2 重新发布完整前端构建产物\n'
              '- 使用新版本号触发平台重新下载 frontend/dist\n'
              '\n'
              'v1.0.1 补充插件版本日志与前端构建产物\n'
              '- 确保配置界面可由平台正常加载\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 支持话题式私聊中转、人机验证、广告过滤、黑名单与限流',
 'scope': 'bot',
 'requirements': [],
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'enabled': {'title': 'enabled',
                               'section': 'V2 配置',
                               'order': 1,
                               'type': 'boolean',
                               'default': False},
                   'group_id': {'title': 'group id',
                                'section': 'V2 配置',
                                'order': 2,
                                'type': 'chat',
                                'default': '',
                                'chat_types': ['group', 'channel'],
                                'session': True},
                   'admin_ids': {'title': 'admin ids',
                                 'section': 'V2 配置',
                                 'order': 3,
                                 'type': 'string',
                                 'default': ''},
                   'captcha_enabled': {'title': 'captcha enabled',
                                       'section': 'V2 配置',
                                       'order': 4,
                                       'type': 'boolean',
                                       'default': True},
                   'spam_enabled': {'title': 'spam enabled',
                                    'section': 'V2 配置',
                                    'order': 5,
                                    'type': 'boolean',
                                    'default': True},
                   'spam_keywords': {'title': 'spam keywords',
                                     'section': 'V2 配置',
                                     'order': 6,
                                     'type': 'string',
                                     'default': 'USDT,博彩,兼职,t.me/,http://,https://'},
                   'rate_limit_window': {'title': 'rate limit window',
                                         'section': 'V2 配置',
                                         'order': 7,
                                         'type': 'number',
                                         'default': 10},
                   'rate_limit_count': {'title': 'rate limit count',
                                        'section': 'V2 配置',
                                        'order': 8,
                                        'type': 'number',
                                        'default': 5},
                   'media_group_delay': {'title': 'media group delay',
                                         'section': 'V2 配置',
                                         'order': 9,
                                         'type': 'chat',
                                         'default': 2.0,
                                         'chat_types': ['group', 'channel'],
                                         'session': True},
                   'startup_notify': {'title': 'startup notify',
                                      'section': 'V2 配置',
                                      'order': 10,
                                      'type': 'boolean',
                                      'default': True}},
 'v1_compatible_version': '1.2.9',
 'v2_adapter': 'telethon',
 'tags': ['工具'],
 'render_mode': 'vue'}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults)
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
