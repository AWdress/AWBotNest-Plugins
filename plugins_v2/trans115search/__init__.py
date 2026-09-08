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

__plugin__ = {'name': '115搜索结果转发',
 'id': 'trans115search',
 'version': '1.0.12',
 'author': 'AWdress',
 'description': '监听来源会话里机器人发的「列表」消息，自动转发到你指定的目标会话。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cloud_media.png',
 'changelog': 'v1.0.12 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.11 修复 V1 默认配置恢复\n- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n\nv1.0.10 适配平台原生富文本通知\n- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n- 原生富文本不可用时保留可读的文本降级\n\nv1.0.8 AWBotNest 2 规范复核\n- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n- 通过全量元数据、语法和发布清单检查\n\nAWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.5 显示会话名称\n'
              '- 保存 UID 后在设置顶部显示来源和目标会话名称\n'
              '- 转发日志显示群组/频道名称并保留 UID\n'
              '\n'
              'v1.0.4 优化配置界面布局\n'
              '- 开关字段统一置顶，采用推荐的栅格布局\n'
              '- 参数字段添加 order 排序，提升扫描性\n'
              '- 符合 AWBotNest 插件开发规范\n'
              '\n'
              'v1.0.3 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'config_schema': {'resolved_chat_names': {'type': 'info', 'label': '已识别会话名称', 'order': 9, 'section': '基本配置'},
                   'source_chat_id': {'type': 'chat',
                                      'default': -1002466900287,
                                      'label': '来源会话ID',
                                      'section': '基本配置',
                                      'help': '监听哪个会话里机器人发的列表消息。',
                                      'order': 10,
                                      'cols': 6,
                                      'chat_types': ['group', 'channel'],
                                      'multi': False},
                   'target_chat_id': {'type': 'chat',
                                      'default': 0,
                                      'label': '转发到会话ID',
                                      'section': '基本配置',
                                      'help': '把列表消息转发到这个会话（群/频道ID或@用户名）。留空则不转发。',
                                      'order': 11,
                                      'cols': 6,
                                      'chat_types': ['group', 'channel'],
                                      'multi': False},
                   'keyword': {'type': 'string',
                               'default': '列表',
                               'label': '触发关键词',
                               'section': '基本配置',
                               'help': '消息含此关键词才转发。',
                               'order': 12,
                               'cols': 6}},
 'v1_compatible_version': '1.0.5',
 'v2_adapter': 'telethon',
 'tags': ['115资源搜索', '网盘检索', '磁链转换']}
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
