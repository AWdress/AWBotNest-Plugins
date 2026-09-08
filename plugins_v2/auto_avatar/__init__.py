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

__plugin__ = {'name': '自动换头像',
 'id': 'auto_avatar',
 'version': '1.0.12',
 'author': 'AWdress',
 'description': '定时把账号头像换成图片池里随机一张。回复图片发 .avataradd 加入池子，.avatarlist/.avatarclear 管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_media.png',
 'changelog': 'v1.0.12 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.11 修复数值配置显示\n- 将滑块字段改为精确数值输入，确保当前值始终可见\n- 保留原有默认值、范围和步长校验\n\nv1.0.10 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.9 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.7 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.4 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              'v1.0.3 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'delete_old': {'type': 'boolean',
                                  'default': True,
                                  'label': '删除旧头像',
                                  'cols': 3,
                                  'order': 1,
                                  'section': '功能开关',
                                  'help': '换新头像后删掉本插件上次设的那张（不动你原有的真实头像）。'},
                   'interval_min': {'type': 'number',
                                    'default': 60,
                                    'label': '换头像间隔(分钟)',
                                    'min': 10,
                                    'max': 1440,
                                    'step': 10,
                                    'order': 10,
                                    'section': '头像轮换',
                                    'help': '每隔多少分钟随机换一次。最小 10 分钟，防 Telegram 限流。改这个值后需「重载」插件生效。'},
                   'add_command': {'type': 'string',
                                   'default': '.avataradd',
                                   'label': '加图命令',
                                   'order': 20,
                                   'section': '图片池命令',
                                   'help': '回复图片或发图带此说明，把图存入池子。'},
                   'list_command': {'type': 'string',
                                    'default': '.avatarlist',
                                    'label': '查看命令',
                                    'order': 21,
                                    'section': '图片池命令'},
                   'clear_command': {'type': 'string',
                                     'default': '.avatarclear',
                                     'label': '清空命令',
                                     'order': 22,
                                     'section': '图片池命令'}},
 'v1_compatible_version': '1.0.4',
 'v2_adapter': 'telethon',
 'tags': ['头像轮换', '图片池', '定时任务']}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults, __plugin__.get('config_schema'))
    await _active_context.initialize()
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
