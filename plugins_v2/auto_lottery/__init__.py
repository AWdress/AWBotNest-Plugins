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

__plugin__ = {'name': '小菜抽奖',
 'id': 'auto_lottery',
 'version': '1.0.24',
 'author': 'AWdress',
 'scope': 'user',
 'description': '自动识别小菜抽奖机器人的抽奖消息并参与，中奖记录与可选自动发奖。自带 Vue 配置界面 + 待发奖管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/auto_lottery.jpg',
 'changelog': 'v1.0.24 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.23 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.22 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.21 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.19 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.12 合并参与群组选择器\n'
              '- 「预定义/自定义抽奖群组」合并为单个「参与抽奖群组」\n'
              '- 不选 = 全部群组都参与（原为不参与任何群）；旧自定义群组自动并入\n'
              '\n'
              'v1.0.11 修正奖品匹配语义\n'
              '- 默认除陷阱外全部参与，不再按奖品名过滤\n'
              '- 「单独匹配」改为自定义奖品名白名单：勾选后只抽命中列表的，且忽略群组列（跨群匹配）\n'
              '- 奖品列表支持裸关键词行（无需再写 群组ID|），兼容旧写法\n'
              '\n'
              'v1.0.10 调整奖品匹配默认行为\n'
              '- 奖品匹配默认匹配所有群的奖品名（无需再勾选通用匹配）\n'
              '- 「通用奖品匹配」改为「单独奖品匹配」：勾选后每个群才只匹配自己配置的奖品名\n'
              '\n'
              'v1.0.9 修复金额与时间窗\n'
              '- 修复中文单位（万/千/百）奖品金额未换算导致发奖严重偏少\n'
              '- 修复跨零点抽奖时间窗（如 22:00-06:00）被误判为不在窗口\n'
              '\n'
              'v1.0.8 更新插件 Logo\n'
              '- 使用小菜抽奖专属图片作为插件卡片与市场图标',
 'config_schema': {},
 'v1_compatible_version': '1.0.13',
 'v2_adapter': 'telethon',
 'tags': ['自动抽奖', '中奖统计', '奖品发放'],
 'render_mode': 'vue'}
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
