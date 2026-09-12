"""red_packet_grab AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown
try:
    from .core import DEFAULTS as _defaults
except ImportError:
    _defaults = {}

__plugin__ = {'name': '自动抢红包',
 'id': 'red_packet_grab',
 'version': '2.0.4',
 'author': 'AWdress',
 'scope': 'user',
 'requirements': ['Pillow>=10.0', 'ddddocr>=1.5'],
 'description': '自动参与口令红包：支持正文直接口令、图片财富密码、OCR 验证码识别及中奖确认复制兜底。可按发包人/群组限制范围，自带 Vue 配置界面与抢包记录。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png',
 'changelog': 'v2.0.4 新增消息链接\n- 抢包和中奖通知增加对应红包消息链接\n- 消息链接移到通知表格外，方便手机直接点击打开\n\nv2.0.3 修复多行通知显示\n- 抢包结果按状态、详情拆分为独立表格行\n- 避免完整正文挤入单个单元格导致裁切或显示不全\n\n'
              'v2.0.2 统一富文本表格通知\n- 抢包结果改为平台结构化表格\n\n'
              'v2.0.1 修复会话名称实体解析\n'
              '- 管理接口改用 Telethon get_entity，保留失败时的 ID 回退\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.2.12 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.2.11 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.2.10 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.2.9 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.2.7 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.4 支持正文动态财富密码红包\n'
              '- 识别“财富密码：内容”并直接发送完整密码参与\n'
              '- 密码可包含中文、英文、数字、标点和空格\n'
              '- 红包剩余数量为 0 时自动跳过，避免发送失效密码\n'
              '\n'
              'v1.2.2 修复复制兜底漏响应\n'
              '- 支持群友回复红包消息发送口令，不再仅缓存独立文本\n'
              '- 缓存漏记时直接读取中奖确认所回复的原消息，必要时从 Telegram 回查\n'
              '- 同时监听新发与编辑后的中奖确认，兼容机器人编辑原消息返回结果\n'
              '- 扩展领取成功、获得、到账及内嵌金额确认识别\n'
              '- 记录候选口令所属红包，多红包并存时优先精确匹配并增加诊断日志\n'
              '\n'
              'v1.2.1 支持图片财富密码红包\n'
              '- 自动识别“财富密码见图片、发送财富密码即可领取”的拼手气红包\n'
              '- 监听红包图片编辑，前一次 OCR 未参与成功时会识别更新后的动态口令\n'
              '- 剩余数量为 0 时停止识别，避免红包结束后发送无效口令\n'
              '\n'
              'v1.2.0 支持正文拼手气红包\n'
              '- 自动识别“发送下方口令领取”后的完整口令并立即参与\n'
              '- 同时监听新消息与编辑消息，避免后补口令时漏抢\n'
              '- 按账号、群组和红包消息去重，结束状态不会重复发送\n'
              '\n'
              'v1.1.2 修复复制兜底选包\n'
              '- 修复多红包并存时按过期时间选包导致口令记错包，改为按确认者匹配对应红包\n'
              '\n'
              'v1.1.1 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'config_schema': {},
 'tags': ['红包监控', '自动抢包', '群组通知'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

_active_context = None

async def setup(ctx):
    global _active_context
    await _core_setup(ctx)

async def teardown(ctx):
    global _active_context
    await _core_teardown(ctx)

__plugin__["name"] = '自动抢红包'
