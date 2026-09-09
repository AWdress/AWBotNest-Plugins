"""zhuque_lottery AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown
try:
    from .core import DEFAULTS as _defaults
except ImportError:
    _defaults = {}

__plugin__ = {'name': '朱雀',
 'id': 'zhuque_lottery',
 'version': '2.0.1',
 'requirements': ['httpx>=0.27', 'numpy>=1.24', 'pandas>=2.0'],
 'author': 'AWdress',
 'scope': 'user',
 'description': '朱雀PT站自动化：个人查询、大劫反击、红包雨、大转盘、转账、鳄鱼丼投注、魔法卡定时、道具卡回收、倍投计算。自带 Vue 配置界面 + 战绩/记录管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/zhuque_lottery.png',
 'changelog': 'v2.0.1 修复 Telethon 原生事件与异步存储\n'
              '- 修复 V1 filters、旧消息字段和回调接口导致的启用及事件失败\n'
              '- 修复朱雀转账、红包雨、YDX 和管理接口的数据读写\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.0.17 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.16 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.15 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.14 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.12 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.8 接入平台结构化通知表格\n'
              '- 灵石转账排行榜改用 ctx.notify_table()\n'
              '- Telegram Bot 与 Premium 账号显示原生边框斑马纹表格\n'
              '- 普通账号、企业微信和 Bark 由平台自动回退分组文本\n'
              '\n'
              'v1.0.7 修复抽奖次数校验\n'
              '- 修复转盘抽奖未校验次数为正整数，非法次数现在会提示并拦截\n'
              '\n'
              'v1.0.6 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'config_schema': {'cookie': {'title': 'cookie',
                              'section': 'V2 配置',
                              'order': 1,
                              'type': 'password',
                              'secret': True,
                              'default': ''}},
 'tags': ['朱雀抽奖', '魔力抽取', '转盘任务'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

_active_context = None

async def setup(ctx):
    global _active_context
    await _core_setup(ctx)

async def teardown(ctx):
    global _active_context
    await _core_teardown(ctx)

__plugin__["name"] = '朱雀'
