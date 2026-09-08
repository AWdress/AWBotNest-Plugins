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

__plugin__ = {'name': '幸运抽奖',
 'id': 'human_lottery',
 'version': '1.1.9',
 'author': 'AWdress',
 'scope': 'user',
 'description': '用用户账号在群里像真人一样发起抽奖：群友发送关键词参与，到时随机开奖，支持状态、提前开奖、取消和历史记录。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/lucky_lottery.svg',
 'changelog': 'v1.1.9 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.1.8 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.1.7 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.1.5 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.1.1 简化创建格式\n'
              '- 删除重复的“每人奖励”参数，奖品即为每位中奖者获得的奖励\n'
              '- 自动发奖金额统一从奖品名称中提取\n'
              '\n'
              'v1.1.0 优化抽奖交互与清理\n'
              '- 支持按时间或人数开奖、参与提示、昵称链接、原消息链接和结束清理\n'
              '\n'
              'v1.0.2 更名并启用原创 Logo\n'
              '- 插件名称调整为「幸运抽奖」并使用原创 Logo\n'
              '\n'
              'v1.0.1 新增自动发奖\n'
              '- 开奖后回复中奖者参与消息发送奖励命令\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- 支持用户账号发起、参与、开奖、取消和历史记录',
 'config_schema': {},
 'v1_compatible_version': '1.1.2',
 'v2_adapter': 'telethon',
 'tags': ['人工抽奖', '抽奖活动', '中奖记录'],
 'render_mode': 'vue'}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults, __plugin__.get('config_schema'))
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
