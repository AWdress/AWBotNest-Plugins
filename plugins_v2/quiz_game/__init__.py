"""quiz_game AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': '趣味答题',
 'id': 'quiz_game',
 'version': '2.0.2',
 'author': 'AWdress',
 'description': '群内答题游戏：发「开启答题」出题，群友抢答，答对自动发魔力奖励，支持连胜加成。AI或天行出题。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/quiz_game.png',
 'changelog': 'v2.0.2 统一使用平台 AI 接口\n'
              '- 移除未使用的 OpenAI 依赖和遗留 AI 密钥配置\n'
              '- AI 出题继续由 AWBotNest 平台统一能力提供\n\n'
              'v2.0.1 补齐密钥显示按钮\n'
              '- 天行数据 Key 默认隐藏并提供眼睛按钮\n'
              '- 点击显示时使用平台受控接口读取真实值\n\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.1.10 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.1.9 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.1.8 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.1.7 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.1.5 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.0.10 修复 Vue 配置保存\n'
              '- 保存配置改用新版平台 host.saveConfig，修复读取 undefined.post 失败\n'
              '- 答题记录和群组名称改用 host.callApi 读取\n'
              '- 读取、保存成功与失败统一使用平台提示\n'
              '\n'
              'v1.0.9 限制开局与答题消息来源\n'
              '- 只有插件所用的本人账号发送‘开启答题’或‘开始答题’才会开局\n'
              '- 结束命令同样只接受本人账号发送\n'
              '- 答案只接收其他群友的入站消息，开局账号不会参与抢答\n'
              '\n'
              'v1.0.7 前端移除自带 API 配置字段\n'
              '- 移除 AI 出题源的 ai_api_key/ai_base_url/ai_model 配置界面\n'
              '\n'
              'v1.0.6 改为仅使用平台统一 AI\n'
              '- 移除插件自带配置回退逻辑，仅调用平台统一 AI\n'
              '- 不再需要配置 ai_api_key/ai_base_url/ai_model\n'
              '\n'
              'v1.0.5 接入平台统一 AI 能力\n'
              '- AI 出题优先使用平台统一 AI（管理员在「系统设置→AI 服务」配置）\n'
              '- 平台 AI 不可用时自动回退到插件自带的 OpenAI 配置或天行数据\n'
              '\n'
              'v1.0.4 更新插件 Logo\n'
              '- 增加与插件功能匹配的酷炫专属图标，并同步插件卡片与市场展示',
 'scope': 'user',
 'requirements': ['httpx>=0.27'],
 'config_schema': {'tianapi_key': {'title': 'tianapi key',
                                   'section': 'V2 配置',
                                   'order': 7,
                                   'type': 'password',
                                   'secret': True,
                                   'default': ''}},
 'tags': ['群组答题', 'AI出题', '积分排行'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = '趣味答题'
