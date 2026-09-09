"""AWBotNest 2 entry; generated from the maintained V1 plugin."""
from __future__ import annotations

from .core import setup as _native_setup, teardown as _native_teardown

__plugin__ = {'name': '115频道监控',
 'id': 'movie_monitor_115',
 'version': '2.0.1',
 'plugin_api_version': 2,
 'author': 'AWdress',
 'description': '通用监控频道里的 115 分享，读取/识别 TMDB 后查 Emby 媒体库，缺失的转发给 CMS 入库机器人。可选电影/电视剧，默认全部。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_cloud_media.png',
 'changelog': 'v2.0.1 修复 Telethon 实体解析与消息兼容\n'
              '- 管理接口改用 get_entity，监听日志使用 chat_id\n'
              '- 修复媒体消息无 caption 时的文本提取异常\n'
              '\n'
              'v1.0.24 适配新版异步存储接口\n'
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
              'v1.0.16 修复 Vue 配置与测试接口\n'
              '- 配置读取和保存迁移到新版平台 host 接口\n'
              '- 状态、日志、群组名称和连接测试改用 host.callApi\n'
              '- 保留旧配置的监控开关兼容性\n'
              '\n'
              'v1.0.14 修复识别与配置缺陷\n'
              '- 修复保存配置接口误用 await req.json() 导致配置无法保存\n'
              '- 修复 TMDB 搜索调用了不存在的 multi_search（改为 search_all）\n'
              '- 修复 Emby 查重缺少 media_type 参数导致去重失效、重复入库\n'
              '\n'
              'v1.0.13 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'requirements': ['httpx>=0.27'],
 'config_schema': {'tmdb_api_key': {'title': 'tmdb api key',
                                    'section': 'V2 配置',
                                    'order': 5,
                                    'type': 'password',
                                    'secret': True,
                                    'default': ''},
                   'emby_api_key': {'title': 'emby api key',
                                    'section': 'V2 配置',
                                    'order': 8,
                                    'type': 'password',
                                    'secret': True,
                                    'default': ''},
                   'pan115_cookie': {'title': 'pan115 cookie',
                                     'section': 'V2 配置',
                                     'order': 13,
                                     'type': 'password',
                                     'secret': True,
                                     'default': ''}},
 'tags': ['115影视监控', '资源订阅', '自动推送'],
 'render_mode': 'vue'}
async def setup(ctx):
    await _native_setup(ctx)


async def teardown(ctx):
    await _native_teardown(ctx)
