"""VPS-Widget for AWBotNest V2; original platform-native implementation."""

__plugin__ = {
    "id": "vps_widget", "name": "VPS-Widget", "version": "0.0.1", "author": "AWdress",
    "scope": "standalone", "instance_mode": "shared", "plugin_api_version": 2,
    "render_mode": "vue", "webhook": True,
    "description": "聚合十类影视榜单、匹配 TMDB 并生成 Forward 格式 Widget；使用平台网络、存储与定时任务，不需要额外 Node 服务。",
    "changelog": "v0.0.1 首次发布\n- 十类影视榜单采集与 TMDB 匹配，失败保留旧缓存\n- 中文 Vue 配置页：榜单状态、配置、Widget 地址\n- 自动更新默认关闭，每天北京时间 17:00；公开只读服务与通知默认关闭\n- Widget 地址使用独立只读密钥，支持缓存与分页，不公开管理接口或 TMDB 密钥",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins_v2/vps_widget/icon.svg",
    "tags": ["影视榜单", "Widget", "TMDB"], "requirements": ["starlette>=0.40,<2"],
    "resources": {"timeout_seconds": 120, "max_concurrency": 8, "max_background_tasks": 2},
    "config_schema": {
        "tmdb_key": {"type": "password", "secret": True, "default": "", "label": "TMDB 密钥",
                     "help": "生成榜单必填，支持 v3 API Key 或 v4 API Read Access Token。仅用于平台访问 TMDB，不写入 Widget。"},
        "trakt_client_id": {"type": "password", "secret": True, "default": "", "label": "Trakt Client ID",
                            "help": "选用 Trakt 时填写应用的 Client ID，不是 OAuth Access Token；留空跳过 Trakt，其余来源照常更新。"},
        "sources": {"type": "multiselect", "default": ["guduo", "douban", "mgtv", "theater", "bangumi", "tmdb", "bili", "mal", "anilist", "trakt"],
                    "label": "采集哪些榜单", "options": [
                        {"value": "guduo", "label": "骨朵"}, {"value": "douban", "label": "豆瓣"},
                        {"value": "mgtv", "label": "芒果 TV"}, {"value": "theater", "label": "剧场片单"},
                        {"value": "bangumi", "label": "Bangumi"}, {"value": "tmdb", "label": "TMDB"},
                        {"value": "bili", "label": "B站"}, {"value": "mal", "label": "MyAnimeList"},
                        {"value": "anilist", "label": "AniList"}, {"value": "trakt", "label": "Trakt"}]},
        "category_limit": {"type": "number", "default": 30, "min": 10, "max": 100, "label": "每个分类最多采集多少条",
                           "help": "默认 30 条，范围 10～100；数量越多，TMDB 请求与更新时间越多。不是整个来源的总条数。"},
        "auto_update": {"type": "boolean", "default": False, "label": "每天自动更新"},
        "update_time": {"type": "string", "default": "17:00", "label": "每天几点更新（北京时间）",
                        "help": "默认 17:00，填写 00:00～23:59。不开启自动更新时只手动更新，不轮询空跑。"},
        "notify_results": {"type": "boolean", "default": False, "label": "更新完成后通知", "help": "使用平台关联的通知渠道，不在插件重复填写机器人。"},
        "public_enabled": {"type": "boolean", "default": False, "label": "允许客户端读取 Widget",
                           "help": "默认关闭；开启后，持有只读地址的人能读取影视榜单，不能更新榜单或读取 TMDB 密钥。"},
        "public_base_url": {"type": "string", "default": "", "label": "平台访问地址",
                            "help": "例如 https://bot.example.com；填写平台地址，不含 /api 路径。若有部署子路径需带上。客户端必须能访问此地址。"},
    },
}

_service = None


async def setup(ctx):
    global _service
    from .core import Service
    _service = Service(ctx)
    await _service.setup()


async def teardown(ctx):
    global _service
    if _service is not None:
        await _service.stop()
        _service = None
