"""Immortal source-embedded integration for AWBotNest V2."""

__plugin__ = {
    "id": "immortal", "name": "Immortal", "version": "0.0.2", "author": "AWdress",
    "scope": "standalone", "instance_mode": "shared", "plugin_api_version": 2,
    "render_mode": "vue", "webhook": False,
    "description": "内置 Immortal 资源、影片、演员、订阅和下载管理；无需另行运行 Immortal 服务。",
    "changelog": "v0.0.2\n- 修复配置页开关行与平台全局样式冲突导致的文字挤压、重叠\n- 改善窄屏帮助文字换行，保留原配置和默认关闭状态\nv0.0.1 首次发布\n- 内置业务源码与管理界面，默认独立 SQLite，安装无需另配数据库\n- 平台管理员接口、平台任务与通知\n- 自动任务及下载默认关闭，不启动独立机器人或 HTTP 服务",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/immortal/icon.svg",
    "tags": ["资源管理", "订阅", "下载"],
    "requirements": ["SQLAlchemy>=2.0,<2.2", "pyquery>=2,<3", "requests>=2.32,<3",
                     "bencoder>=0.2,<1", "jinja2>=3.1,<4", "croniter>=3,<7",
                     "pandas>=2.2,<3", "openpyxl>=3.1,<4", "xlrd>=2,<3",
                     "PySocks>=1.7,<2", "python-multipart>=0.0.20,<1"],
    "resources": {"timeout_seconds": 7200, "max_concurrency": 8, "max_background_tasks": 36},
    "config_schema": {
        "auto_tasks": {"type": "boolean", "default": False, "label": "启用定时任务",
                       "help": "默认关闭。开启后只运行管理界面中已启用的任务；使用北京时间。"},
        "allow_downloads": {"type": "boolean", "default": False, "label": "允许提交下载",
                            "help": "默认关闭。开启并保存后，手动下载或订阅任务才会向已配置的下载器提交文件。"},
        "notify_results": {"type": "boolean", "default": False, "label": "发送任务通知",
                           "help": "使用平台的通知渠道，不在插件重复配置 Telegram 或企业微信凭证。"},
        "database_url": {"type": "password", "secret": True, "default": "", "label": "外部数据库地址（可留空）",
                         "help": "留空使用插件独立 SQLite 数据库；已有 PostgreSQL 可填写连接地址并安装 psycopg2-binary。更换地址不会迁移旧数据。不要填写平台数据库。"},
    },
}

_service = None


async def setup(ctx):
    global _service
    from .core import Service
    if _service is not None:
        raise RuntimeError("Immortal 已在运行，请先停用旧实例")
    candidate = Service(ctx)
    try:
        await candidate.setup()
    except BaseException:
        await candidate.stop()
        raise
    _service = candidate


async def teardown(ctx):
    global _service
    if _service is not None:
        await _service.stop()
        _service = None
