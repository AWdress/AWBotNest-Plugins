"""emby_toolbox AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': 'Emby 工具箱',
 'id': 'emby_toolbox',
 'version': '2.0.5',
 'author': 'AWdress',
 'description': '集成 Emby 剧集校验、Genre 清理/映射、季名刮削、国家语言 Tag、别名写入、STRM 刷新、元数据缺失检查等维护功能。支持定时执行与完整日志。',
 'icon': 'https://cdn.simpleicons.org/emby',
 'changelog': 'v2.0.5 适配平台敏感配置读取规范\n- Emby 与 TMDB API Key 均声明为敏感字段，配置接口统一返回掩码\n- 配置页显示按钮改用平台 revealSecret 接口，管理员确认后才读取真实密钥\n\nv2.0.4 优化 Genre 扫描速度与进度日志\n- 先使用媒体库批量结果筛选候选条目，仅对确需修改的条目读取完整详情\n- 增加扫描数量、更新数量和每 50 条进度日志，避免长时间无反馈\n\nv2.0.3 增强别名缓存与 Genre 中文化\n- 别名写入成功后持久化记录，后续扫描命中缓存直接跳过，避免重复请求和更新\n- Genre 映射内置常见英文到中文映射，同时保留自定义 JSON 覆盖\n- 增加 Genre 中文化命中、跳过和更新日志，更新 GenreItems 名称并保留已有 ID\n\n'
              'v2.0.2 统一富文本表格通知\n- 定时维护和任务结果改为平台结构化表格\n\n'
              'v2.0.1 修复 Emby API 客户端逻辑\n'
              '- 使用 VirtualFolders 正确解析媒体库 ID，并兼容旧版 Views 接口\n'
              '- 递归展开媒体库文件夹，补齐维护功能所需的元数据字段\n'
              '- 统一更新与 PlaybackInfo 请求路径，修复多项功能失败\n'
              '- 图标替换为 Emby Logo\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.4.9 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.4.8 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.4.7 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.4.6 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.4.4 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.4.1 重做 Vue 界面配色\n'
              '- 去除大面积墨绿色背景，改为与平台一致的深海军蓝中性层次\n'
              '- Emby 青蓝仅用于开关、主按钮和选中状态\n'
              '- 重新校正卡片、输入框、次要文字与边框对比度\n'
              '\n'
              'v1.4.0 迁移 Vue 媒体维护控制台\n'
              '- 新增实时任务状态、历史记录和后台 API',
 'scope': 'standalone',
 'requirements': ['requests>=2.28'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'api_key': {'title': 'api key',
                               'section': 'V2 配置',
                               'order': 2,
                               'type': 'password',
                               'secret': True,
                               'default': ''},
                   'tmdb_key': {'title': 'TMDB API Key',
                                'section': 'V2 配置',
                                'order': 3,
                                'type': 'password',
                                'secret': True,
                                'default': ''}},
 'tags': ['Emby维护', '媒体库清理', '元数据管理'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = 'Emby 工具箱'
