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

__plugin__ = {'name': 'U2送糖',
 'id': 'u2_dmhy',
 $11.0.11',
 'requirements': ['httpx>=0.27'],
 'author': 'AWdress',
 'description': '用 /u2 或 /u2s 带 cookie 给 u2.dmhy.org 用户赠送 UCoin。单人/批量，自带站点限频冷却。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/u2_dmhy.png',
 'changelog': 'AWBotNest 2 兼容发布\n'
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
                   'cooldown_seconds': {'type': 'slider',
                                        'default': 300,
                                        'label': '赠送冷却(秒)',
                                        'min': 0,
                                        'max': 1200,
                                        'step': 10,
                                        'section': '限频与清理',
                                        'order': 30,
                                        'help': '两次赠送的最小间隔（u2 站限频，建议 ≥300）。批量时每个之间也按此间隔。'},
                   'result_delete': {'type': 'slider',
                                     'default': 90,
                                     'label': '结果自动删除(秒)',
                                     'min': 0,
                                     'max': 300,
                                     'step': 10,
                                     'section': '限频与清理',
                                     'order': 31}},
 'v1_compatible_version': '1.0.7',
 'v2_adapter': 'telethon',
 'tags': ['U2赠魔', '魔力转赠', '站点Cookie']}
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


