"""pt_multi_checkin AWBotNest V2 原生插件入口。"""
from __future__ import annotations

from .core import setup as _core_setup, teardown as _core_teardown

__plugin__ = {'name': 'PT站自动签到',
 'id': 'pt_multi_checkin',
 'version': '2.0.11',
 'author': 'AWdress',
 'description': '多 PT 站自动签到中心，统一使用平台 Cookie 与 CloakBrowser，提供 Vue 管理界面。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/pt_checkin_v2.svg',
 'changelog': 'v2.0.11 对齐 CloakBrowser 官方 Turnstile 流程\n'
              '- Audiences 与 OurBits 使用 Preview 持久会话、代理 GeoIP 和原生验证流程\n'
              '- 移除固定语言与代理出口不一致、显式重建控件和高频 CDP 等待\n'
              '- 清理 V2 前端隐藏文件，修复插件路径安全检查失败\n'
              '\n'
              'v2.0.10 修复签到参数显示不完整\n'
              '- 数字输入框保留稳定宽度，避免浏览器步进控件遮挡数值\n'
              '- 重试间隔单位改为独立布局，窄窗口自动换行且不再与数值重叠\n'
              '\n'
              'v2.0.9 修复 Audiences Docker 自动验证\n'
              '- 改用真正的 CloakBrowser 持久 profile 与固定指纹，避免 Cloudflare Cookie 和随机指纹错配\n'
              '- Audiences 只等待托管验证自动签发令牌，不再误点空的 Turnstile 外层容器\n'
              '- 控件未初始化时重新加载官方 API 并显式渲染，超时日志补充脚本、指纹和控件状态\n'
              '\n'
              'v2.0.8 修复 OurBits 与 TJUPT CloakBrowser 签到\n'
              '- OurBits 适配新的 form#attendance Turnstile，并只接受真实提交回执\n'
              '- TJUPT 保留 CloakBrowser 会话，改由已解析 DOM 元素提交表单，避免拟人层重复解析链式选择器\n'
              '\n'
              'v2.0.7 修复 OurBits、U2 与 Audiences 实际签到\n'
              '- OurBits 删除普通首页导航的成功推断，只接受站点明确签到状态或回执\n'
              '- U2 不再调用 AI 识图，直接任选一项提交；答错获得 1 UCoin 仍计为签到成功\n'
              '- Audiences 浏览器整轮限制为 30 秒，无结果立即跳过并关闭当前上下文\n'
              '\n'
              'v2.0.6 修复 Audiences 与 U2 签到\n'
              '- Audiences 改用真实 CloakBrowser 指纹与持久 storage_state，复用 Cloudflare 验证会话\n'
              '- CookieCloud 最新 Cookie 覆盖同名旧值，未同步的 Cloudflare 通行状态由持久上下文保留\n'
              '- U2 正确识别“回答错误但获得 1 UCoin”为已完成签到，不再误报失败\n'
              '\n'
              'v2.0.5 恢复 OurBits 首页签到确认\n'
              '- 将 V1 已验证的首页回执判定迁入原生 V2 核心\n'
              '- 签到后跳回站点根页且签到入口消失时确认已完成\n'
              '- HTTP、CloakBrowser 和结果回查使用同一严格条件，不把登录页或未签到首页误报成功\n'
              '\n'
              'v2.0.4 TJUPT AI 完全自动化\n'
              '- 启用 tjupt_ai_assist 时，AI 识别后直接自动提交答案\n'
              '- AI 识别失败时自动回退到 Telegram 手动选择模式\n'
              '- 优化 AI prompt，要求直接返回选项序号\n'
              '- 增强日志输出，记录 AI 识别过程和结果\n'
              '\n'
              'v2.0.3 修复 U2 签到提交\n'
              '- U2 跳过会被安全策略拒绝的轻量 HTTP 提交，直接使用 CloakBrowser\n'
              '- 改用真实浏览器表单按钮提交验证答案，并绕过缓存回查首页状态\n'
              '- 补充错误答案与过期验证识别，避免未确认状态重复误报\n'
              '\n'
              'v2.0.2 增强 Audiences Turnstile 诊断\n'
              '- 兼容 Cloudflare turnstile.getResponse 令牌读取方式\n'
              '- 记录令牌来源与超时页面、表单、组件和 iframe 信息\n'
              '- 验证失败仍保持失败，不会误报签到成功\n'
              '\n'
              'v2.0.1 修复 OurBits 首页误判已签到\n'
              '- 普通登录首页不再被当作已签到凭据\n'
              '- HTTP 与浏览器流程均只接受明确签到状态或签到回执\n'
              '- 未确认状态继续进入 attendance.php，不再误报成功\n'
              '\n'
              'v2.0.0 原生 AWBotNest V2 迁移\n'
              '- 使用 Telethon 原生事件、调度、存储与生命周期接口\n'
              '- 保留原有功能、配置项和运行数据\n'
              '- 移除 V1 兼容运行层\n'
              '\n'
              'v2.5.51 修复 OurBits 新版签到回执识别\n'
              '- 兼容签到后跳转首页且不再显示文字回执的新页面流程\n'
              '- 仅在同域登录态首页且签到入口消失时确认完成，避免普通页面误报成功\n'
              '- 浏览器确认与轻量 HTTP 签到统一使用相同的严格判定\n'
              '\n'
              'v2.5.50 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v2.5.49 适配新版 Vue 配置校验\n'
              '- Vue 页面业务字段按新规范由自定义配置页保存\n'
              '- schema 仅保留密码等敏感字段，避免数组或对象被旧类型声明拒绝\n'
              '\n'
              'v2.5.48 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v2.5.47 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v2.5.45 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'v2.5.40 修复 V2 配置项声明\n'
              '- 补齐自动签到、重试、无头浏览器、结果通知与站点选择字段\n'
              '- 修复平台保存配置时报“包含未声明的配置项”\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v2.5.35 修复 Audiences Turnstile 点击可能落在外层容器的问题\n'
              '- 优先按 Cloudflare iframe 的真实边界点击复选框区域\n'
              '- 日志记录点击方式与 iframe 尺寸，便于确认真实交互\n'
              '\n'
              'v2.5.34 Docker 缺少 DISPLAY 时自动启动 Xvfb',
 'scope': 'standalone',
 'requirements': ['httpx>=0.27',
                  'beautifulsoup4>=4.12',
                  'cloakbrowser>=0.5.10',
                  'geoip2>=4.8'],
 'cookie_domains': ['audiences.me',
                    '*.audiences.me',
                    'ourbits.club',
                    '*.ourbits.club',
                    'hhanclub.net',
                    '*.hhanclub.net',
                    'piggo.me',
                    '*.piggo.me',
                    'tjupt.org',
                    '*.tjupt.org',
                    '52pt.site',
                    '*.52pt.site',
                    'pt.btschool.club',
                    '*.pt.btschool.club',
                    'ptchdbits.co',
                    '*.ptchdbits.co',
                    'haidan.video',
                    '*.haidan.video',
                    'club.hares.top',
                    '*.club.hares.top',
                    'hdarea.club',
                    '*.hdarea.club',
                    'hdchina.org',
                    '*.hdchina.org',
                    'hdcity.city',
                    '*.hdcity.city',
                    'hdsky.me',
                    '*.hdsky.me',
                    'pt.hdupt.com',
                    '*.pt.hdupt.com',
                    'm-team.cc',
                    '*.m-team.cc',
                    'v6.nexushd.org',
                    '*.v6.nexushd.org',
                    'open.cd',
                    '*.open.cd',
                    'pterclub.net',
                    '*.pterclub.net',
                    'pttime.org',
                    '*.pttime.org',
                    'totheglory.im',
                    '*.totheglory.im',
                    'u2.dmhy.org',
                    '*.u2.dmhy.org',
                    'yemapt.org',
                    '*.yemapt.org',
                    'zhuque.in',
                    '*.zhuque.in'],
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 8,
               'max_background_tasks': 3,
               'failure_threshold': 3,
               'recovery_seconds': 120},
 'config_schema': {},
 'tags': ['PT站签到', '多站点', 'Cloudflare', 'Cookie'],
 'render_mode': 'vue',
 'plugin_api_version': 2}

async def setup(ctx):
    await _core_setup(ctx)

async def teardown(ctx):
    await _core_teardown(ctx)

__plugin__["name"] = 'PT站自动签到'
