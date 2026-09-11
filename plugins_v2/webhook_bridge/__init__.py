"""AWBotNest V2 原生 Webhook 通知桥。"""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': 'Webhook 通知桥',
 'id': 'webhook_bridge',
 'version': '2.0.2',
 'author': 'AWdress',
 'description': '接收 NAS、下载器、监控、CI 等外部 Webhook，自动提取内容并通过平台统一通知渠道推送。',
 'changelog': 'v2.0.2 修复多行通知显示\n- 外部事件标题、正文和元数据拆分为独立表格行\n- 避免完整正文挤入单个单元格导致裁切或显示不全\n\n'
              'v2.0.1 统一富文本表格通知\n- 外部事件与测试通知改为平台结构化表格\n\n'
              'v2.0.0 完成原生 V2 迁移\n'
              '- 使用原生公开 Webhook、异步存储与动作接口\n'
              '- 修复重载后的路由注册、去重、限流和统计持久化\n\n'
              'v1.0.10 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.9 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.8 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.6 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.1 加固首次加载配置兜底\n'
              '- 配置尚未持久化时仍使用内置字段提取与敏感字段过滤默认值\n'
              '- 防止完整载荷兜底通知意外包含令牌、密码等敏感字段\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 支持 GET、JSON、表单与纯文本事件\n'
              '- 支持自动字段提取、模板、去重和限流\n'
              '- 提供测试通知、统计查看与状态清理动作',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_relay.png',
 'scope': 'standalone',
 'webhook': True,
 'plugin_api_version': 2,
 'config_schema': {'enabled': {'type': 'boolean',
                               'default': True,
                               'label': '接收并转发',
                               'section': '基本设置',
                               'cols': 4,
                               'order': 1},
                   'category': {'type': 'string',
                                'default': '外部事件',
                                'label': '通知分类',
                                'section': '基本设置',
                                'cols': 4,
                                'order': 2},
                   'default_level': {'type': 'select',
                                     'default': 'info',
                                     'label': '默认级别',
                                     'options': [{'value': 'info', 'label': '信息'},
                                                 {'value': 'success', 'label': '成功'},
                                                 {'value': 'warning', 'label': '警告'},
                                                 {'value': 'error', 'label': '错误'}],
                                     'section': '基本设置',
                                     'cols': 4,
                                     'order': 3},
                   'title_fields': {'type': 'string',
                                    'default': 'title,subject,name,event,event_type,status',
                                    'label': '标题字段',
                                    'section': '内容提取',
                                    'cols': 6,
                                    'order': 10,
                                    'help': '按顺序查找，支持点路径，如 project.name。用英文逗号分隔。'},
                   'message_fields': {'type': 'string',
                                      'default': 'message,text,content,description,body,summary',
                                      'label': '正文字段',
                                      'section': '内容提取',
                                      'cols': 6,
                                      'order': 11,
                                      'help': '找不到正文时会发送过滤后的完整结构化数据。'},
                   'level_field': {'type': 'string',
                                   'default': 'level,severity,priority,status',
                                   'label': '级别字段',
                                   'section': '内容提取',
                                   'cols': 6,
                                   'order': 12},
                   'source_field': {'type': 'string',
                                    'default': 'source,service,app,application,repository.name',
                                    'label': '来源字段',
                                    'section': '内容提取',
                                    'cols': 6,
                                    'order': 13},
                   'title_template': {'type': 'string',
                                      'default': '{source}{title}',
                                      'label': '标题模板',
                                      'section': '内容提取',
                                      'cols': 12,
                                      'order': 14,
                                      'help': '可用 {source}、{title}、{event}、{method}；来源会自动加“ · ”。留空不显示标题。'},
                   'include_metadata': {'type': 'boolean',
                                        'default': True,
                                        'label': '附加来源与事件信息',
                                        'section': '内容提取',
                                        'cols': 4,
                                        'order': 15},
                   'max_chars': {'type': 'number',
                                 'default': 3500,
                                 'label': '最大正文字符数',
                                 'min': 200,
                                 'max': 12000,
                                 'step': 100,
                                 'section': '安全控制',
                                 'cols': 4,
                                 'order': 20},
                   'dedupe_seconds': {'type': 'number',
                                      'default': 60,
                                      'label': '重复事件忽略秒数',
                                      'min': 0,
                                      'max': 86400,
                                      'step': 10,
                                      'section': '安全控制',
                                      'cols': 4,
                                      'order': 21,
                                      'help': '按请求内容去重，0 表示关闭。'},
                   'rate_limit': {'type': 'number',
                                  'default': 30,
                                  'label': '每分钟最大通知数',
                                  'min': 1,
                                  'max': 1000,
                                  'step': 1,
                                  'section': '安全控制',
                                  'cols': 4,
                                  'order': 22},
                   'ignored_fields': {'type': 'string',
                                      'default': 'token,apikey,api_key,password,secret,authorization,cookie',
                                      'label': '敏感字段过滤',
                                      'section': '安全控制',
                                      'cols': 8,
                                      'order': 23,
                                      'help': '字段名不区分大小写；输出完整载荷时递归移除。'},
                   'test_notify': {'type': 'action',
                                   'label': '发送测试通知',
                                   'action': 'test_notify',
                                   'section': '维护',
                                   'cols': 4,
                                   'order': 30},
                   'show_stats': {'type': 'action',
                                  'label': '查看接收统计',
                                  'action': 'show_stats',
                                  'section': '维护',
                                  'cols': 4,
                                  'order': 31},
                   'clear_state': {'type': 'action',
                                   'label': '清空统计和去重状态',
                                   'action': 'clear_state',
                                   'danger': True,
                                   'section': '维护',
                                   'cols': 4,
                                   'order': 32},
                   'runtime_status': {'type': 'info',
                                      'default': '等待接收事件',
                                      'label': '运行状态',
                                      'section': '维护',
                                      'cols': 12,
                                      'order': 33}},
 'tags': ['Webhook桥接', '外部通知', '签名校验']}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
