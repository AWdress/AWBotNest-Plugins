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

__plugin__ = {'name': '数字炸弹',
 'id': 'bomb_game',
 'version': '1.0.13',
 'author': 'AWdress',
 'description': '群内数字炸弹竞猜：开启后群友回复+金额参与组奖池，轮流猜数字，猜中/范围耗尽即爆炸，中奖者按比例分奖池。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/bomb_game.png',
 'changelog': 'v1.0.13 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.12 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.11 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.9 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.6 修复 Vue 配置保存\n'
              '- 配置读取和保存迁移到新版平台 host 接口\n'
              '- 群组名称和游戏记录改用 host.callApi 读取\n'
              '- 重新构建并发布前端产物\n'
              '\n'
              'v1.0.4 修复核心接线错误\n'
              '- 修复处理函数调用了不存在的旧版 API 导致插件无法运行\n'
              '- 按真实游戏引擎接口重接开局/参与/猜数字/转账确认\n'
              '- 转账确认改为失败安全：无法唯一定位参与者时跳过，绝不错记金额\n'
              '\n'
              'v1.0.3 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n'
              '\n'
              'v1.0.2 修复配置界面缺失\n'
              '- 随插件发布 frontend/dist 前端构建产物',
 'scope': 'both',
 'config_schema': {},
 'v1_compatible_version': '1.0.6',
 'v2_adapter': 'telethon',
 'tags': ['炸弹游戏', '群组娱乐', '互动玩法'],
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
