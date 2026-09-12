"""red_packet_send AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': '发红包',
 'id': 'red_packet_send',
 'version': '2.0.2',
 'author': 'AWdress',
 'scope': 'user',
 'requirements': ['Pillow>=10.0'],
 'description': '用你的账号在群里发拼手气红包：口令（可自定义前缀）+随机防挂码渲染成验证码图片，群友识别并输入完整字符才算参与（防脚本）；可选每抢一个换码，命令消息秒删，按拼手气随机分配并自动发放魔力，每个红包带递增编号便于对照。自带 '
                'Vue 配置界面 + 红包监控。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_redpacket.png',
 'changelog': 'v2.0.2 修复 Telegram 用户资料链接\n'
              '- 公开用户名优先使用通用 t.me 链接，无用户名时使用 openmessage 数字 ID 深链\n'
              '- 红包结束消息显式启用 Markdown 解析，确保链接生成可点击实体\n'
              '- 没有公开用户名的用户也能直接打开资料\n\n'
              'v2.0.1 清理发送者字段迁移残留\n'
              '- 活动创建、参与和手动结束统一读取 Telethon sender\n'
              '- 移除 Pyrogram from_user 兼容分支\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.0.22 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.21 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.20 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.19 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.17 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.13 重复参与反馈\n'
              '- 用户再次发送当前有效参与口令时，回复重复参与无效提示\n'
              '- 提示 8 秒后自动删除，普通聊天不会被误判为重复参与\n'
              '\n'
              'v1.0.12 显示群组名称\n'
              '- 红包监控和历史记录显示群组名称并保留 UID\n'
              '- 创建、超时和结算日志显示群组名称\n'
              '\n'
              'v1.0.11 修复红包金额\n'
              '- 统一用整数魔力分配，避免按分切再取整导致小份额打成 0 或扣发不符\n'
              '- 总额不足以每个红包至少 1 魔力时拒绝创建',
 'config_schema': {},
 'tags': ['红包发送', '定时发包', '活动管理'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = '发红包'
