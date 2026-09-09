"""AWBotNest V2 原生 U2 送糖插件。"""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': 'U2送糖',
 'id': 'u2_dmhy',
 'version': '2.0.0',
 'plugin_api_version': 2,
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12'],
 'author': 'AWdress',
 'description': '用 /u2 或 /u2s 带 cookie 给 u2.dmhy.org 用户赠送 UCoin。单人/批量，自带站点限频冷却。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/u2_dmhy.png',
 'changelog': 'v1.0.15 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.14 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.0.13 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.12 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.10 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.7 修复 U2 站内跳转\n'
              '- 正确处理赠送后的 HTTP 302 站内跳转，不再直接判定失败\n'
              '- 识别 Cookie 失效登录页、Cloudflare 验证和异常跨站跳转\n'
              '- 记录跳转目标日志，便于区分正常提交与登录失效\n'
              '\n'
              'v1.0.6 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              '\n'
              'v1.0.5 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'cookie': {'type': 'password',
 'secret': True,
                              'default': '',
                              'label': 'u2 Cookie',
                              'section': '凭据',
                              'order': 10,
                              'help': '浏览器 F12 复制 u2.dmhy.org 的整条 Cookie 头。'},
                   'u2_command': {'type': 'string',
                                  'default': '.u2',
                                  'label': '单人命令',
                                  'section': '命令',
                                  'order': 20,
                                  'help': '单人赠送命令。/u2 与 .u2 等价。'},
                   'u2s_command': {'type': 'string',
                                   'default': '.u2s',
                                   'label': '批量命令',
                                   'section': '命令',
                                   'order': 21},
                   'cooldown_seconds': {'type': 'number',
                                        'default': 300,
                                        'label': '赠送冷却(秒)',
                                        'min': 0,
                                        'max': 1200,
                                        'step': 10,
                                        'section': '限频与清理',
                                        'order': 30,
                                        'help': '两次赠送的最小间隔（u2 站限频，建议 ≥300）。批量时每个之间也按此间隔。'},
                   'result_delete': {'type': 'number',
                                     'default': 90,
                                     'label': '结果自动删除(秒)',
                                     'min': 0,
                                     'max': 300,
                                     'step': 10,
                                     'section': '限频与清理',
                                     'order': 31}},
 'tags': ['U2赠魔', '魔力转赠', '站点Cookie']}
_active_context = None


async def setup(ctx):
    global _active_context
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
