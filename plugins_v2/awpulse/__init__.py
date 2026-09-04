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

__plugin__ = {'name': 'AWPulse 色花堂助手',
 'id': 'awpulse',
 $11.2.4',
 'author': 'AWdress',
 'description': '色花堂论坛自动化：登录/每日签到/智能回复/平台AI回复与帖子过滤/自动发帖/消息统计。基于平台内置浏览器(headless)，定时运行+结果推送，自带 Vue 管理界面。',
 'changelog': 'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.0 修复定时任务结束后仍显示运行中\n'
              '- 定时触发只负责投递平台托管后台任务，计划任务状态会立即正常结束\n'
              '- 通知增加 30 秒超时，任务取消时强制复位 Vue 运行状态\n'
              '\n'
              'v1.1.9 优化计划任务名称\n'
              '- 计划任务明确显示“色花堂自动化”，便于在平台任务列表中辨认\n'
              '\n'
              'v1.1.8 修复 Docker 定时任务时区\n'
              '- Cron 与每日时刻统一绑定平台的 Asia/Shanghai 时区，不再随容器 UTC 时区偏移 8 小时\n'
              '- 过滤重复时刻并严格校验小时、分钟，注册日志输出实际下次运行时间\n'
              '\n'
              'v1.1.7 提升点选验证码识别率\n'
              '- 连续中文提示按实际点击顺序拆分，不再把整句误当成一个目标\n'
              '- DOM 取不到提示时自动 OCR 验证码提示小图\n'
              '- 任一目标无法可靠匹配时放弃本轮等待新题，不再乱点全部候选消耗次数\n'
              '\n'
              'v1.1.6 加固验证码成功判定\n'
              '- 监听验证码 XHR/fetch 响应，优先采用服务端明确的验证成功或失败结果\n'
              '- 不再仅凭验证码弹窗消失判定通过，未知结果交由签到页最终状态确认\n'
              '- 验证窗口关闭但响应不可读时使用中性日志，避免误报识别成功\n'
              '\n'
              'v1.1.5 修复签到结果确认\n'
              '- 验证码通过后使用退避轮询刷新签到状态，不再盲目重复点击触发频率限制\n'
              '- 签到失败会正确向上返回，整轮运行和通知不再误报成功\n'
              '- 修复签到失败调试文件目录未定义的问题',
 'scope': 'standalone',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/awpulse/logo.png',
 'requirements': ['cloakbrowser>=0.4.9', 'requests>=2.32.0', 'opencv-python-headless>=4.8', 'numpy>=1.24', 'Pillow>=10.0'],
 'resources': {'timeout_seconds': 7200,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'v2_compat_notice': {'type': 'info',
                                        'title': 'AWBotNest 2 兼容模式',
                                        'text': 'V2 当前使用平台原生表单；V1 Vue 管理页仍保留在 V1 版本。',
                                        'section': '兼容性',
                                        'order': -100},
                   'base_url': {'title': 'base url',
                                'section': 'V2 配置',
                                'order': 1,
                                'type': 'string',
                                'default': 'https://sehuatang.org/'},
                   'username': {'title': 'username',
                                'section': 'V2 配置',
                                'order': 2,
                                'type': 'string',
                                'default': ''},
                   'password': {'title': 'password',
                                'section': 'V2 配置',
                                'order': 3,
                                'type': 'password',
                                'default': ''},
                   'security_question_id': {'title': 'security question id',
                                            'section': 'V2 配置',
                                            'order': 4,
                                            'type': 'string',
                                            'default': '0'},
                   'security_answer': {'title': 'security answer',
                                       'section': 'V2 配置',
                                       'order': 5,
                                       'type': 'string',
                                       'default': ''},
                   'headless': {'title': 'headless',
                                'section': 'V2 配置',
                                'order': 6,
                                'type': 'boolean',
                                'default': True},
                   'enable_auto_reply': {'title': 'enable auto reply',
                                         'section': 'V2 配置',
                                         'order': 7,
                                         'type': 'boolean',
                                         'default': True},
                   'enable_daily_checkin': {'title': 'enable daily checkin',
                                            'section': 'V2 配置',
                                            'order': 8,
                                            'type': 'boolean',
                                            'default': True},
                   'enable_smart_reply': {'title': 'enable smart reply',
                                          'section': 'V2 配置',
                                          'order': 9,
                                          'type': 'boolean',
                                          'default': True},
                   'enable_ai_reply': {'title': 'enable ai reply',
                                       'section': 'V2 配置',
                                       'order': 10,
                                       'type': 'boolean',
                                       'default': False},
                   'enable_ai_post_filter': {'title': 'enable ai post filter',
                                             'section': 'V2 配置',
                                             'order': 11,
                                             'type': 'boolean',
                                             'default': True},
                   'enable_auto_post': {'title': 'enable auto post',
                                        'section': 'V2 配置',
                                        'order': 12,
                                        'type': 'boolean',
                                        'default': False},
                   'enable_random_delay': {'title': 'enable random delay',
                                           'section': 'V2 配置',
                                           'order': 13,
                                           'type': 'boolean',
                                           'default': False},
                   'enable_test_mode': {'title': 'enable test mode',
                                        'section': 'V2 配置',
                                        'order': 14,
                                        'type': 'boolean',
                                        'default': False},
                   'enable_test_checkin': {'title': 'enable test checkin',
                                           'section': 'V2 配置',
                                           'order': 15,
                                           'type': 'boolean',
                                           'default': False},
                   'enable_test_reply': {'title': 'enable test reply',
                                         'section': 'V2 配置',
                                         'order': 16,
                                         'type': 'boolean',
                                         'default': False},
                   'enable_test_post': {'title': 'enable test post',
                                        'section': 'V2 配置',
                                        'order': 17,
                                        'type': 'boolean',
                                        'default': False},
                   'skip_admin_posts': {'title': 'skip admin posts',
                                        'section': 'V2 配置',
                                        'order': 18,
                                        'type': 'boolean',
                                        'default': True},
                   'max_replies_per_day': {'title': 'max replies per day',
                                           'section': 'V2 配置',
                                           'order': 19,
                                           'type': 'number',
                                           'default': 3},
                   'reply_interval': {'title': 'reply interval',
                                      'section': 'V2 配置',
                                      'order': 20,
                                      'type': 'text',
                                      'default': '60\n120',
                                      'help': '每行一项'},
                   'schedule_cron': {'title': 'schedule cron',
                                     'section': 'V2 配置',
                                     'order': 21,
                                     'type': 'string',
                                     'default': ''},
                   'schedule_times': {'title': 'schedule times',
                                      'section': 'V2 配置',
                                      'order': 22,
                                      'type': 'text',
                                      'default': '03:00\n09:00\n15:00\n21:00',
                                      'help': '每行一项'},
                   'schedule_time': {'title': 'schedule time',
                                     'section': 'V2 配置',
                                     'order': 23,
                                     'type': 'string',
                                     'default': '03:00'},
                   'notify': {'title': 'notify',
                              'section': 'V2 配置',
                              'order': 24,
                              'type': 'boolean',
                              'default': True},
                   'target_forums': {'title': 'target forums',
                                     'section': 'V2 配置',
                                     'order': 25,
                                     'type': 'text',
                                     'default': 'fid=141',
                                     'help': '每行一项'},
                   'forum_names': {'title': 'forum names',
                                   'section': 'V2 配置',
                                   'order': 26,
                                   'type': 'text',
                                   'default': '{\n'
                                              '  "fid=141": "网友原创区",\n'
                                              '  "fid=2": "亚洲无码原创区",\n'
                                              '  "fid=36": "亚洲有码原创区",\n'
                                              '  "fid=37": "中字原创区",\n'
                                              '  "fid=103": "国产原创区",\n'
                                              '  "fid=139": "色花文学"\n'
                                              '}'},
                   'auto_post': {'title': 'auto post',
                                 'section': 'V2 配置',
                                 'order': 27,
                                 'type': 'text',
                                 'default': '{\n'
                                            '  "enabled": false,\n'
                                            '  "target_fid": 139,\n'
                                            '  "category_id": null,\n'
                                            '  "post_folder": "novels",\n'
                                            '  "posted_folder": "posted",\n'
                                            '  "post_interval": 300,\n'
                                            '  "max_posts_per_day": 5,\n'
                                            '  "content_preview_length": 500,\n'
                                            '  "move_after_post": true,\n'
                                            '  "skip_posted_files": true\n'
                                            '}'},
                   'skip_keywords': {'title': 'skip keywords',
                                     'section': 'V2 配置',
                                     'order': 28,
                                     'type': 'text',
                                     'default': '公告\n'
                                                '通知\n'
                                                '规则\n'
                                                '版规\n'
                                                '置顶\n'
                                                '热门\n'
                                                '2024年永久访问本站方法\n'
                                                'APP下载\n'
                                                '白名单\n'
                                                '邀请码\n'
                                                '访问方法\n'
                                                '屏蔽\n'
                                                '封禁\n'
                                                '违规\n'
                                                '删除\n'
                                                '警告\n'
                                                '发布器\n'
                                                '最新方法\n'
                                                '申诉\n'
                                                '二次验证\n'
                                                '禁止申诉\n'
                                                '高薪\n'
                                                '招聘',
                                     'help': '每行一项'},
                   'skip_prefixes': {'title': 'skip prefixes',
                                     'section': 'V2 配置',
                                     'order': 29,
                                     'type': 'text',
                                     'default': '【公告】\n【通知】\n【规则】\n【版规】\n公告:\n通知:\n规则:\n版规:',
                                     'help': '每行一项'},
                   'admin_usernames': {'title': 'admin usernames',
                                       'section': 'V2 配置',
                                       'order': 30,
                                       'type': 'text',
                                       'default': 'admin\n管理员\n版主',
                                       'help': '每行一项'},
                   'reply_templates': {'title': 'reply templates',
                                       'section': 'V2 配置',
                                       'order': 31,
                                       'type': 'text',
                                       'default': '谢谢楼主分享！\n'
                                                  '感谢分享，收藏了！\n'
                                                  '好资源，支持一下！\n'
                                                  '楼主辛苦了，谢谢分享！\n'
                                                  '不错的内容，学习了！\n'
                                                  '感谢楼主的无私分享！\n'
                                                  '收藏了，慢慢看！\n'
                                                  '好东西，必须支持！',
                                       'help': '每行一项'},
                   'smart_reply_templates': {'title': 'smart reply templates',
                                             'section': 'V2 配置',
                                             'order': 32,
                                             'type': 'text',
                                             'default': '{\n'
                                                        '  "general": [\n'
                                                        '    "内容很不错！",\n'
                                                        '    "楼主辛苦了！",\n'
                                                        '    "感谢分享！",\n'
                                                        '    "支持原创！",\n'
                                                        '    "很有意思！"\n'
                                                        '  ],\n'
                                                        '  "resource": [\n'
                                                        '    "资源很棒，感谢分享！",\n'
                                                        '    "好东西，必须收藏！",\n'
                                                        '    "链接有效，谢谢楼主！",\n'
                                                        '    "资源质量很高！"\n'
                                                        '  ],\n'
                                                        '  "photo": [\n'
                                                        '    "照片拍得真不错！",\n'
                                                        '    "颜值很高啊，赞！",\n'
                                                        '    "摄影技术很棒！",\n'
                                                        '    "拍摄角度很好，学习了！"\n'
                                                        '  ],\n'
                                                        '  "video": [\n'
                                                        '    "视频质量不错！",\n'
                                                        '    "内容很精彩，感谢分享！",\n'
                                                        '    "画质清晰，很棒！",\n'
                                                        '    "剪辑得很好，专业！"\n'
                                                        '  ],\n'
                                                        '  "story": [\n'
                                                        '    "好精彩的故事！情节很吸引人！",\n'
                                                        '    "写得真好，很有代入感！",\n'
                                                        '    "故事很棒，期待后续！"\n'
                                                        '  ]\n'
                                                        '}'},
                   'reply_rules': {'title': 'reply rules',
                                   'section': 'V2 配置',
                                   'order': 33,
                                   'type': 'string',
                                   'default': ''},
                   'ai_system_prompt': {'title': 'ai system prompt',
                                        'section': 'V2 配置',
                                        'order': 34,
                                        'type': 'string',
                                        'default': '你是一个论坛用户，需要根据帖子标题和内容生成简短的回复。回复要自然、简洁，不超过50字。'},
                   'ai_reply_reject_markers': {'title': 'ai reply reject markers',
                                               'section': 'V2 配置',
                                               'order': 35,
                                               'type': 'string',
                                               'default': ''},
                   'proxy': {'title': 'proxy',
                             'section': 'V2 配置',
                             'order': 36,
                             'type': 'text',
                             'default': '{\n'
                                        '  "enabled": false,\n'
                                        '  "http_proxy": "",\n'
                                        '  "https_proxy": "",\n'
                                        '  "no_proxy": "localhost,127.0.0.1",\n'
                                        '  "use_for_browser": false\n'
                                        '}'},
                   'browser_headers': {'title': 'browser headers',
                                       'section': 'V2 配置',
                                       'order': 37,
                                       'type': 'text',
                                       'default': '{\n'
                                                  '  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; '
                                                  'x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                                  'Chrome/143.0.0.0 Safari/537.36",\n'
                                                  '  "accept_language": "zh-CN,zh;q=0.9,en;q=0.8"\n'
                                                  '}'},
                   'log_level': {'title': 'log level',
                                 'section': 'V2 配置',
                                 'order': 38,
                                 'type': 'string',
                                 'default': 'INFO'},
                   'last_run': {'type': 'string',
                                'default': '',
                                'title': 'last run',
                                'section': 'V2 兼容字段',
                                'order': 9000}},
 'v1_compatible_version': '1.2.0',
 'v2_adapter': 'telethon',
 'tags': ['色花堂助手', '自动签到', '自动发帖'],
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


