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

__plugin__ = {'name': 'AWPulse 色花堂助手',
 'id': 'awpulse',
 'version': '1.2.7',
 'author': 'AWdress',
 'description': '色花堂论坛自动化：登录/每日签到/智能回复/平台AI回复与帖子过滤/自动发帖/消息统计。基于平台内置浏览器(headless)，定时运行+结果推送，自带 Vue 管理界面。',
 'changelog': 'v1.2.7 适配新版 Vue 配置校验\n'
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
 'requirements': ['cloakbrowser>=0.4.9',
                  'requests>=2.32.0',
                  'opencv-python-headless>=4.8',
                  'numpy>=1.24',
                  'Pillow>=10.0',
                  'beautifulsoup4>=4.12',
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
                                'default': ''}},
 'v1_compatible_version': '1.2.0',
 'v2_adapter': 'telethon',
 'tags': ['色花堂助手', '自动签到', '自动发帖'],
 'render_mode': 'vue'}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults, __plugin__.get('config_schema'))
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
