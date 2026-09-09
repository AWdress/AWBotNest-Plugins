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

__plugin__ = {'name': '多站点转账',
 'id': 'transfer',
 'version': '1.1.11',
 'author': 'AWdress',
 'scope': 'user',
 'requirements': ['Pillow>=10.0', 'imgkit>=1.2'],
 'description': '监听多个PT站群的转账bot，记录转入/转出并生成排行榜。站点群组/bot内置，用户只开关每站点功能。自带 Vue 配置界面 + 排行榜管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/transfer.png',
 'changelog': 'v1.1.11 优化 V2 排行榜响应速度\n'
              '- 同一 Telegram 事件的两层回复链只读取一次，供多个监听器共享\n'
              '- 将入站与出站条件下推到平台事件过滤，避免唤醒无关监听器\n'
              '- 降低 SpringSunday 等回复链转账的重复网络请求与响应等待\n'
              '\n'
              'v1.1.10 修复 V2 站点群消息未触发\n'
              '- 使用 Telethon 事件的完整会话 ID 匹配内置站点群\n'
              '- 修复频道实体正数 ID 无法匹配 -100 群 ID，导致消息被静默忽略的问题\n'
              '- 按真实 Telethon 群实体与事件 ID 差异重新验证转账入榜链路\n'
              '\n'
              'v1.1.9 修复 V2 转账排行榜无数据\n'
              '- 完整读取转账确认消息的两层回复链与每层发送者\n'
              '- 修复 V2 下转入、转出方向无法识别，导致记录未进入排行榜的问题\n'
              '- 增加回复链、聚合榜单及管理接口回归验证\n'
              '\n'
              'v1.1.8 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.1.7 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.1.6 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.1.5 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.1.3 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.30 美化 Premium 富文本排行榜\n'
              '- 表格启用 Telegram 原生边框与斑马纹\n'
              '- 排名、用户、次数和累计金额按内容统一对齐\n'
              '- 前三名用户与名次加粗突出，累计金额右对齐显示\n'
              '\n'
              'v1.0.29 修复 Premium 富文本发送参数\n'
              '- 移除 Kurigram 2.2.24 不支持的 reply_to_message_id 参数\n'
              '- 富文本排行榜改为独立消息发送，确保原生表格正常显示\n'
              '- 文本回退仍保持回复原消息的行为\n'
              '\n'
              'v1.0.28 接入平台原生 Rich Message\n'
              '- 使用 ctx.user.send_rich() 发送 Premium 富文本表格\n'
              '- 发送前通过 supports_native_rich() 检查当前用户账号能力\n'
              '- 排行榜命令成功发送富文本后自动删除原命令消息\n'
              '- 普通账号或发送失败时继续回退排版文本榜\n'
              '\n'
              'v1.0.27 修复富文本表格被静默降级\n'
              '- 不再把 Rich Message HTML 误发到普通消息接口\n'
              '- 当前 Kurigram 未提供用户账号 Rich Message 接口时直接回退正常文本榜\n'
              '- 配置页补充 Premium 与平台能力要求\n'
              '\n'
              'v1.0.26 新增 Premium 富文本表格\n'
              '- 排行榜输出新增 Kurigram HTML 富文本表格模式\n'
              '- 自动致谢榜与排行榜命令均支持表格输出\n'
              '- 表格发送失败时自动回退文本榜\n'
              '- 配置页明确标注仅 Telegram Premium 会员可用\n'
              '\n'
              'v1.0.25 修复文本排行榜不发送\n'
              '- 群内致谢与打赏榜/赏赐榜改为独立开关，单独开启排行榜也会正常发送\n'
              '- 文本模式可仅发送排行榜，不再依赖群内致谢开关\n'
              '- 图片模式与图片失败回退文本同样支持仅排行榜输出\n'
              '\n'
              'v1.0.24 修复 hdsky 转账解析\n'
              '- 修复无条件取发送者导致对手方识别错误，改为仅在缺对手方时回退取发送者\n'
              '\n'
              'v1.0.23 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示\n'
              '\n'
              'v1.0.22 修复用户名前导空白占位\n'
              '- 排行榜、通知、致谢和日志展示用户名时先移除首尾空白，再执行长度截断\n'
              '- 全空白用户名统一显示为未知用户\n'
              '\n'
              'v1.0.21 移除 Telegram 原生表格\n'
              '- 原生表格只能通过 Bot API 发送，无法使用监听账号在站点群输出，因此移除该选项及相关发送逻辑\n'
              '- 已保存原生表格选项的旧配置自动回退为文本排行榜\n'
              '\n'
              'v1.0.20 优化超长用户名显示\n'
              '- 日志、通知、致谢和各类排行榜中的超长用户名统一截断并以 ... 省略\n'
              '- 完整用户名仍保留在内部记录中，不影响用户聚合\n'
              '\n'
              'v1.0.19 优化原生表格不可用时的回退\n'
              '- 修复分配 Bot 不在目标群时反复请求并刷出 chat not found 警告\n'
              '- 首次失败明确提示 Bot 入群要求，后续直接回退文本\n'
              '\n'
              'v1.0.18 新增 Telegram 原生表格输出\n'
              '- 排行榜输出形式新增 Bot API Rich Message 原生表格\n'
              '- 原生表格使用边框和斑马纹，支持群内致谢榜及排行榜命令\n'
              '- Bot 不在目标群、无权限或服务端不支持时自动回退文本\n'
              '\n'
              'v1.0.17 完善多站点转账与排行榜\n'
              '- 修复站点转账识别、排行榜渲染与管理面板兼容问题',
 'config_schema': {},
 'v1_compatible_version': '1.1.0',
 'v2_adapter': 'telethon',
 'tags': ['站点转赠', '魔力转移', '排行榜'],
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
