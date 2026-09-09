"""AWBotNest V2 原生插件开发调试工具。"""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': '插件开发调试',
 'id': 'custom_plugin',
 'version': '2.0.0',
 'author': 'AWdress',
 'scope': 'both',
 'description': '在管理员配置页编辑、检查并运行 Python 插件源码，显示运行状态与错误堆栈，适合开发和调试单文件插件。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/custom_plugin.svg',
 'changelog': 'v2.0.0 完成原生 V2 迁移\n'
              '- 使用原生事件、内部 API、调度与生命周期接口\n'
              '- 修复 API 路径、Webhook 注册和重载残留问题\n'
              '- 默认示例改为 Telethon 单参数事件写法\n\n'
              'v1.0.12 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.0.11 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.0.10 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.0.9 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.0.7 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.3 支持独立运行插件\n'
              '- 源码检查可以识别 standalone 范围\n'
              '- 独立运行插件不会自动挂载用户账号或机器人消息处理器\n'
              '\n'
              'v1.0.2 修复调试生命周期缺陷\n'
              '- 源码检查改用 AST 静态分析，不再执行顶层代码导致保存时重复副作用\n'
              '- 关闭运行开关时允许保存尚未完成或存在语法错误的草稿\n'
              '- 自定义 setup 完整成功前暂存消息、编辑、回调、API、Webhook、定时任务与清理注册\n'
              '- setup 失败时执行自定义清理并丢弃暂存注册，避免半成品监听器继续运行\n'
              '- 定时任务返回延迟绑定代理，兼容源码保存任务对象并读取运行状态\n'
              '- 按源码 __plugin__.scope 保持 user、bot、both 默认监听范围\n'
              '- 新增独立 JSON 运行配置并合并 config_schema 默认值，支持 ctx.config 与 ctx.update_config\n'
              '- 保留 /status 与 /validate 调试接口，防止自定义 API 覆盖后配置页失效\n'
              '\n'
              'v1.0.1 更名为插件开发调试\n'
              '- 展示名称调整为“插件开发调试”，更准确体现源码编辑、检查、运行和错误排查用途\n'
              '- 保留 custom_plugin 内部 ID，已安装用户可直接更新\n'
              '\n'
              'v1.0.0 初始版本\n'
              '- Vue 配置页内置 Python 源码编辑器与示例模板\n'
              '- 保存配置后编译并运行自定义 setup(ctx)\n'
              '- 停用或重载时调用自定义 teardown(ctx)\n'
              '- 编译或运行失败时保留容器插件，便于直接修正源码\n'
              '- 仅管理员配置页可修改，不开放 Telegram 远程写代码',
 'config_schema': {},
 'plugin_api_version': 2,
 'v1_compatible_version': '1.0.3',
 'v2_adapter': 'telethon',
 'tags': ['自定义插件', '脚本执行', '扩展开发'],
 'render_mode': 'vue'}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
