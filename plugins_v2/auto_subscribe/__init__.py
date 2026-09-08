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

__plugin__ = {'name': 'NextFind 助手',
 'id': 'auto_subscribe',
 'version': '1.4.4',
 'requirements': ['httpx>=0.27', 'beautifulsoup4>=4.12', 'lxml>=5.0'],
 'author': 'AWdress',
 'description': 'NextFind 资源订阅与本地媒体库联动，支持榜单订阅、缺集补全、缺集自动订阅、资源查询和管理。',
 'icon': 'https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/auto_subscribe.png',
 'changelog': 'v1.4.4 适配新版异步存储接口\n'
              '- 兼容新版平台异步 KV 与原有同步 KV\n'
              '- 启用时预载数据，按顺序托管写入并在停用时等待完成\n'
              '\n'
              'v1.4.3 同步 V1 新功能并适配新版 Vue 配置校验\n'
              '- 新增本地库缺集接口不可用时通过订阅进度接口降级查询\n'
              '- 同步 NextFind 扩展 OpenAPI 管理界面与完整 Vue 源码\n'
              '- Vue 业务字段改由自定义页面管理，仅保留敏感字段脱敏声明\n'
              '\n'
              'v1.3.9 修复 V1 默认配置恢复\n'
              '- 插件启用时恢复被旧版 V2 表单错误保存为空的默认值\n'
              '- 保留已有非空配置、关闭状态、零值和空列表，不覆盖用户有效设置\n'
              '\n'
              'v1.3.8 适配平台原生富文本通知\n'
              '- 将 notify_table 和 send_rich 交由 AWBotNest 2 平台原生服务处理\n'
              '- 原生富文本不可用时保留可读的文本降级\n'
              '\n'
              'v1.3.6 AWBotNest 2 规范复核\n'
              '- 修复 V2 实体、生命周期、配置安全和依赖兼容问题\n'
              '- 通过全量元数据、语法和发布清单检查\n'
              '\n'
              'AWBotNest 2 兼容发布\n'
              '- 使用 Telethon 原生事件、调度和生命周期托管\n'
              '- 保留 AWBotNest 1 版本与原有数据\n'
              '\n'
              'v1.3.3 适配平台后台任务治理\n'
              '- 手动运行改由 ctx.create_task 托管，停用或重载插件时可由平台安全回收\n'
              '- 声明长任务超时、并发与后台任务配额，避免重复任务失控\n'
              '\n'
              'v1.3.2 标明独立运行\n'
              '- 插件不依赖用户账号或机器人，安装后会显示“独立运行”\n'
              '- 定时订阅、平台 AI 和通知功能保持不变\n'
              '\n'
              'v1.3.1 增强蜜柑番剧识别\n'
              '- 自动拆分蜜柑中英、中日混合标题及常见分隔符标题，逐个交给 NextFind 核验\n'
              '- 原标题仍搜不到时，根据蜜柑详情页的 Bangumi ID 获取中文名、原名和别名继续搜索\n'
              '- 无需额外服务、Endpoint 或 Token；全部候选仍须取得有效 TMDB 结果才会订阅\n'
              '\n'
              'v1.2.0 新增平台 AI 辅助识别\n'
              '- 可选在常规搜索无结果时调用平台 AI 提取标准电影/剧集名、类型与季号\n'
              '- AI 结果必须经 NextFind 再次搜索并取得有效 TMDB 结果后才会订阅\n'
              '- 默认关闭，平台 AI 不可用或识别失败时安全降级为原有未识别流程\n'
              '\n'
              'v1.1.0 新增自动补缺集\n'
              '- 接入 NextFind /subscriptions/info 批量查询活跃剧集的入库进度\n'
              '- 仅对明确存在缺集的订阅调用 /media/fill_missing，并支持配置每轮处理上限\n'
              '- 可在不启用榜单源时独立执行补缺，运行通知会显示检查与触发数量\n'
              '\n'
              'v1.0.6 修复并发运行\n'
              '- 新增整轮运行互斥锁，手动与定时并发时跳过重复轮次，避免去重历史互相覆盖',
 'scope': 'standalone',
 'resources': {'timeout_seconds': 1800,
               'max_concurrency': 2,
               'max_background_tasks': 4,
               'failure_threshold': 5,
               'recovery_seconds': 60},
 'config_schema': {'api_key': {'title': 'api key',
                               'section': 'V2 配置',
                               'order': 2,
                               'type': 'password',
                               'secret': True,
                               'default': ''}},
 'v1_compatible_version': '1.4.2',
 'v2_adapter': 'telethon',
 'tags': ['自动订阅', '影视搜索', '订阅管理'],
 'render_mode': 'vue'}
_active_context = None


async def setup(ctx):
    global _active_context
    _active_context = adapt(ctx, _legacy_defaults, __plugin__.get('config_schema'))
    await _active_context.initialize()
    await _legacy_setup(_active_context)


async def teardown(ctx):
    global _active_context
    adapted = _active_context
    _active_context = None
    if adapted is not None and _legacy_teardown is not None:
        await _legacy_teardown(adapted)
    if adapted is not None:
        await adapted.close()
