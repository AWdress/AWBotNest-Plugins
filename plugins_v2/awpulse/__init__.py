"""awpulse AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': 'AWPulse 色花堂助手',
 'id': 'awpulse',
 'version': '2.0.8',
 'author': 'AWdress',
 'description': '色花堂论坛自动化：登录/每日签到/智能回复/平台AI回复与帖子过滤/自动发帖/消息统计。基于平台内置浏览器(headless)，定时运行+结果推送，自带 Vue 管理界面。',
 'changelog': 'v2.0.8 适配最新平台插件规范\n- 定时配置接入统一 Cron 编辑器并改用 schedule_cron 正式接口\n- 补齐直接使用的 Playwright 与 lxml 依赖声明，不再依赖环境偶然安装\n\nv2.0.7 适配平台 CloakBrowser 统一治理\n- 浏览器代理、License Key 和内核选择改由平台统一管理\n- 浏览器指纹通过 GeoIP 跟随实际网络出口\n- 启动中途失败或部分资源关闭异常时仍确保释放浏览器会话\n\n'
              'v2.0.6 补齐密码显示按钮\n- 登录密码默认隐藏，点击眼睛后显示平台受控读取的真实值\n- 保存时兼容平台脱敏占位值，避免覆盖已保存密码\n\n'
              'v2.0.5 修复多行通知显示\n- 运行摘要按状态、详情拆分为独立表格行\n- 避免完整正文挤入单个单元格导致裁切或显示不全\n\n'
              'v2.0.4 补齐高级配置显示\n- 配置页面新增智能回复模板、自定义特征规则和日志级别\n- JSON 规则保存前执行格式校验，避免无效配置进入运行流程\n\n'
              'v2.0.3 统一富文本表格通知\n- 运行结果、跳过和异常通知改为平台结构化表格\n\n'
              'v2.0.2 修复验证码结束后未提交签到\n'
              '- 签到状态只读取真实按钮，避免页面统计文字干扰判断\n'
              '- 状态确认加入防缓存参数，确保读取服务端最新结果\n'
              '- 验证结束后仍明确未签到时仅受控重试一次\n'
              '\n'
              'v2.0.1 修复用户资料页 URL\n'
              '- 移除空的 uid 参数，兼容 Discuz 站点当前用户资料页路由\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v1.2.8 适配新版异步存储接口\n'
              '- 兼容新版异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.2.7 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v1.2.6 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.2.5 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.2.3 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.2.0 修复定时任务结束后仍显示运行中\n'
              '- 定时触发只负责投递平台托管后台任务，计划任务状态会立即正常结束\n'
              '- 通知增加 30 秒超时，任务取消时强制复位 Vue 运行状态\n'
              '\n'
              'v1.1.9 优化计划任务名称\n'
              '- 计划任务明确显示“色花堂自动化”，便于在平台任务列表中辨认\n'
              '\n'
              'v1.1.8 修复 Docker 定时任务时区\n'
              '- Cron 与每日时刻统一绑定平台的 Asia/Shanghai 时区，不再随容器 UTC 时区偏移 8 小时\n'
              '- 过滤重复时刻并严格校验小时、分钟，注册日志输出实际下次运行时间\n'
              '\n'
              'v1.1.7 提升点选验证码识别率\n'
              '- 连续中文提示按实际点击顺序拆分，不再把整句误当成一个目标\n'
              '- DOM 取不到提示时自动 OCR 验证码提示小图\n'
              '- 任一目标无法可靠匹配时放弃本轮等待新题，不再乱点全部候选消耗次数\n'
              '\n'
              'v1.1.6 加固验证码成功判定\n'
              '- 监听验证码 XHR/fetch 响应，优先采用服务端明确的验证成功或失败结果\n'
              '- 不再仅凭验证码弹窗消失判定通过，未知结果交由签到页最终状态确认\n'
              '- 验证窗口关闭但响应不可读时使用中性日志，避免误报识别成功\n'
              '\n'
              'v1.1.5 修复签到结果确认\n'
              '- 验证码通过后使用退避轮询刷新签到状态，不再盲目重复点击触发频率限制\n'
              '- 签到失败会正确向上返回，整轮运行和通知不再误报成功\n'
              '- 修复签到失败调试文件目录未定义的问题',
 'scope': 'standalone',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/awpulse/logo.png',
 'requirements': ['cloakbrowser>=0.5.10',
                  'playwright>=1.55',
                  'opencv-python-headless>=4.8',
                  'numpy>=1.24',
                  'Pillow>=10.0',
                  'beautifulsoup4>=4.12',
                  'lxml>=5.0',
                  'ddddocr>=1.5'],
 'resources': {'timeout_seconds': 7200,
               'max_concurrency': 1,
               'max_background_tasks': 2,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {'password': {'title': 'password',
                                'section': 'V2 配置',
                                'order': 3,
                                'type': 'password',
                                'secret': True,
                                'default': ''},
                   'schedule_cron': {'type': 'string',
                                     'format': 'cron',
                                     'default': '',
                                     'label': 'Cron',
                                     'section': '定时与通知',
                                     'order': 20}},
 'tags': ['色花堂助手', '自动签到', '自动发帖'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = 'AWPulse 色花堂助手'
