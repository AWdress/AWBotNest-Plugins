"""awembypush AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': 'AWEmbyPush',
 'id': 'awembypush',
 'version': '2.0.0',
 'scope': 'standalone',
 'author': 'AWdress',
 'description': '监听 Emby/Jellyfin 入库 Webhook，经 TMDB 增强/剧集合并/去重后，通过 Telegram/企业微信/Bark 推送精美媒体通知。（自 MoviePilot 插件移植）自带 '
                'Vue 配置界面 + 最近推送/测试推送。',
 'changelog': 'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.5.19 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.5.18 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.5.17 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.5.16 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.5.14 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.5.8 标明独立运行\n'
              '- 插件不依赖用户账号或机器人，安装后会显示“独立运行”\n'
              '- Webhook 和原有通知功能保持不变\n'
              '\n'
              'v1.5.7 修复去重记录竞态\n'
              '- 发送去重记录的读写加锁，避免多线程并发读写竞态\n'
              '\n'
              'v1.5.6 移植到 AWBotNest 平台\n'
              '- 自 MoviePilot 插件 AWEmbyPush v1.5.5 移植\n'
              '- 使用平台 Webhook 机制和 Vue 配置界面\n'
              '- 支持 Telegram/企业微信/Bark 三种推送渠道\n'
              '- 自动走平台代理，支持 TMDB 元数据增强\n'
              '- 剧集合并、去重、测试推送功能完整保留',
 'icon': 'https://raw.githubusercontent.com/AWdress/MoviePilot-Plugins/main/plugins/awembypush/logo.png',
 'webhook': True,
 'requirements': ['requests>=2.28'],
 'config_schema': {'tmdb_api_key': {'title': 'tmdb api key',
                                    'section': 'V2 配置',
                                    'order': 2,
                                    'type': 'password',
                                    'secret': True,
                                    'default': ''},
                   'tg_bot_token': {'title': 'tg bot token',
                                    'section': 'V2 配置',
                                    'order': 11,
                                    'type': 'password',
                                    'secret': True,
                                    'default': ''},
                   'wx_corp_secret': {'title': 'wx corp secret',
                                      'section': 'V2 配置',
                                      'order': 15,
                                      'type': 'password',
                                      'secret': True,
                                      'default': ''}},
 'tags': ['Emby推送', '媒体通知', 'TMDB匹配'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = 'AWEmbyPush'
