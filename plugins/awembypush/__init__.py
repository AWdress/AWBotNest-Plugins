# =============================================================================
# AWBotNest 插件：AWEmbyPush（awembypush）
#
# 从 MoviePilot 插件 AWEmbyPush(v1.5.5) 移植而来。
# 监听 Emby/Jellyfin 的入库 Webhook，经 TMDB 元数据增强、剧集合并、去重后，
# 通过 Telegram / 企业微信 / Bark 三个渠道推送精美媒体通知。
#
# 入站地址（在插件「配置」里生成密钥后得到）：
#   http(s)://<平台地址>/api/v1/plugin/awembypush/webhook?apikey=<密钥>
# 在 Emby/Jellyfin 的 Webhook 里填此地址，内容类型选 application/json。
#
# 移植说明（相对 MoviePilot 版）：
#   - get_api(Starlette) → @ctx.on_webhook；get_form(Vuetify) → config_schema
#   - self.save_data/get_data → ctx.kv；logger → ctx.log
#   - settings.PROXY → 出站自动走平台代理（企微「免代理」用 trust_env=False）
#   - settings.TMDB_* → 配置项（平台无全局 TMDB 配置，需自行填写）
#   - 复用 MP 内置通知中心(use_mp_tg/use_mp_wx) → 去除，仅保留直填凭据
#   - get_page 详情页(MP 前端专属) → 去除，最近推送记录仍存于 ctx.kv
# =============================================================================

import asyncio
import html
import json
import re
import threading
import time
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

__plugin__ = {
    "name": "AWEmbyPush",
    "id": "awembypush",
    "version": "1.5.6",
    "scope": "bot",
    "author": "AWdress",
    "description": "监听 Emby/Jellyfin 入库 Webhook，经 TMDB 增强/剧集合并/去重后，通过 Telegram/企业微信/Bark 推送精美媒体通知。（自 MoviePilot 插件移植）自带 Vue 配置界面 + 最近推送/测试推送。",
    "icon": "https://raw.githubusercontent.com/AWdress/MoviePilot-Plugins/main/plugins/awembypush/logo.png",
    "default_enabled": False,
    "webhook": True,
    "render_mode": "vue",
    "requirements": ["requests>=2.28"],
}

# vue 模式无 config_schema：配置默认值集中此处备查（后端 _load_config 里 c.get(k, 默认) 已带默认，
# 前端 Config.vue 用同一套默认初始化表单）。
DEFAULTS = {
    "enable_tmdb": True, "tmdb_api_key": "", "tmdb_api_domain": "api.themoviedb.org",
    "tmdb_image_domain": "image.tmdb.org", "emby_server_url": "",
    "dedup_window": 60, "episode_cache_timeout": 30,
    "enable_watch_link": False, "watch_link_type": "server", "link_redirect_prefix": "",
    "tg_bot_token": "", "tg_chat_id": "", "tg_api_host": "",
    "wx_corp_id": "", "wx_corp_secret": "", "wx_agent_id": "", "wx_user_id": "@all",
    "wx_msg_type": "news_notice", "wx_proxy_url": "", "wx_no_proxy": True,
    "bark_server": "https://api.day.app", "bark_keys": "",
    "enable_custom_template": False, "tg_template": "", "wx_title_template": "",
    "wx_body_template": "", "bark_title_template": "", "bark_body_template": "",
}


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    return text[:limit] + "..." if len(text) > limit else text


GENRE_MAP = {
    "Action": "动作", "Adventure": "冒险", "Animation": "动画",
    "Comedy": "喜剧", "Crime": "犯罪", "Documentary": "纪录",
    "Drama": "剧情", "Family": "家庭", "Fantasy": "奇幻",
    "History": "历史", "Horror": "恐怖", "Music": "音乐",
    "Mystery": "悬疑", "Romance": "爱情", "Science Fiction": "科幻",
    "TV Movie": "电视电影", "Thriller": "惊悚", "War": "战争",
    "Western": "西部", "Action & Adventure": "动作冒险",
    "Kids": "儿童", "News": "新闻", "Reality": "真人秀",
    "Sci-Fi & Fantasy": "科幻奇幻", "Soap": "肥皂剧",
    "Talk": "脱口秀", "War & Politics": "战争政治",
}


class _EventInfo:
    """替代 MoviePilot 的 WebhookEventInfo：一个简单的属性容器。"""

    def __init__(self, event: str = "", channel: str = ""):
        self.event = event
        self.channel = channel
        self.item_type: Optional[str] = None
        self.item_name: Optional[str] = None
        self.item_id = None
        self.season_id: Optional[str] = None
        self.episode_id: Optional[str] = None
        self.item_path = None
        self.tmdb_id: Optional[str] = None
        self.overview: str = ""
        self.ip = None
        self.device_name = None
        self.client = None
        self.user_name = None
        self.image_url: str = ""


class _EpisodeCache:
    CACHE_TIMEOUT = 30
    SEND_DEDUP_WINDOW = 300

    def __init__(self, send_callback, log):
        self.cache: Dict[str, List[dict]] = {}
        self.timers: Dict[str, threading.Timer] = {}
        self.lock = threading.Lock()
        self._sent_records: Dict[str, float] = {}
        self._send = send_callback
        self._log = log

    def _cache_key(self, media: dict) -> Optional[str]:
        if not media.get("is_ep"):
            return None
        tmdb_id = media.get("tmdb_id") or media.get("item_name", "")
        return f"{tmdb_id}_{media.get('season_id', '')}"

    def _send_key(self, media: dict) -> str:
        if media.get("is_ep"):
            return f"ep_{media.get('tmdb_id', '')}_{media.get('season_id', '')}_{media.get('episode_id', '')}"
        return f"mov_{media.get('tmdb_id', '')}"

    def _is_recently_sent(self, key: str) -> bool:
        now = time.time()
        expired = [k for k, v in self._sent_records.items() if now - v > self.SEND_DEDUP_WINDOW]
        for k in expired:
            del self._sent_records[k]
        return key in self._sent_records

    def _record_sent(self, key: str):
        self._sent_records[key] = time.time()

    def add(self, media: dict):
        if not media.get("is_ep"):
            sk = self._send_key(media)
            if self._is_recently_sent(sk):
                self._log.info(f"AWEmbyPush 发送层拦截重复推送（电影）：{media.get('item_name')}")
                return
            self._send(media)
            self._record_sent(sk)
            return
        ck = self._cache_key(media)
        if not ck:
            self._send(media)
            return
        with self.lock:
            if ck in self.timers:
                self.timers[ck].cancel()
            if ck not in self.cache:
                self.cache[ck] = []
            existing_eps = [ep.get("episode_id") for ep in self.cache[ck]]
            if media.get("episode_id") in existing_eps:
                self._log.info(
                    f"AWEmbyPush 剧集已在缓存中：{media.get('item_name')} "
                    f"{media.get('episode_text') or ''}"
                )
            else:
                self.cache[ck].append(media)
                self._log.info(
                    f"AWEmbyPush 缓存剧集：{media.get('item_name')} "
                    f"{media.get('episode_text') or ''} "
                    f"(当前缓存 {len(self.cache[ck])} 集)"
                )
            timer = threading.Timer(self.CACHE_TIMEOUT, self._flush, args=[ck])
            timer.daemon = True
            timer.start()
            self.timers[ck] = timer

    def _flush(self, ck: str):
        with self.lock:
            episodes = self.cache.pop(ck, [])
            self.timers.pop(ck, None)
        if not episodes:
            return
        unique = {}
        for ep in episodes:
            ep_id = ep.get("episode_id")
            if ep_id not in unique:
                unique[ep_id] = ep
        episodes = sorted(unique.values(), key=lambda x: int(x.get("episode_id") or 0))
        if len(episodes) == 1:
            sk = self._send_key(episodes[0])
            if self._is_recently_sent(sk):
                self._log.info(f"AWEmbyPush 发送层拦截重复推送：{episodes[0].get('item_name')}")
                return
            self._send(episodes[0])
            self._record_sent(sk)
            return
        ep_ids = [int(ep.get("episode_id") or 0) for ep in episodes]
        is_continuous = all(ep_ids[i] + 1 == ep_ids[i + 1] for i in range(len(ep_ids) - 1))
        if is_continuous:
            ep_range = f"{ep_ids[0]}-{ep_ids[-1]}" if ep_ids[0] != ep_ids[-1] else str(ep_ids[0])
        else:
            ep_range = ",".join(str(e) for e in ep_ids)
        merged = episodes[0].copy()
        merged["episode_merged"] = True
        merged["episode_range"] = ep_range
        merged["episode_count"] = len(episodes)
        s = merged.get("season_id", "")
        merged["episode_text"] = f"第{s}季：第{ep_range}集（共{len(episodes)}集）"
        unsent = [ep for ep in episodes if not self._is_recently_sent(self._send_key(ep))]
        if not unsent:
            self._log.info(f"AWEmbyPush 发送层拦截重复推送：{merged.get('item_name')} 第{s}季：第{ep_range}集（全部已发送过）")
            return
        self._log.info(f"AWEmbyPush 合并发送 {len(episodes)} 集：{merged.get('item_name')} 第{s}季：第{ep_range}集")
        self._send(merged)
        for ep in episodes:
            self._record_sent(self._send_key(ep))

    def cancel_all(self):
        with self.lock:
            for t in self.timers.values():
                try:
                    t.cancel()
                except Exception:
                    pass
            self.timers.clear()
            self.cache.clear()


class AWEmbyPush:
    """核心推送逻辑（移植自 MoviePilot 插件类，去掉 _PluginBase，改用 ctx）。"""

    def __init__(self, ctx):
        self.ctx = ctx
        self._fingerprint_lock = threading.Lock()
        self._message_fingerprints: Dict[str, float] = {}
        self._episode_cache = _EpisodeCache(self._send_all_channels, ctx.log)
        self._load_config()

    # --------------------------- 配置读取 --------------------------- #
    def _load_config(self):
        c = self.ctx.config
        self._tg_bot_token = c.get("tg_bot_token", "") or ""
        self._tg_chat_id = c.get("tg_chat_id", "") or ""
        self._tg_api_host = (c.get("tg_api_host", "") or "").rstrip("/")
        self._wx_corp_id = c.get("wx_corp_id", "") or ""
        self._wx_corp_secret = c.get("wx_corp_secret", "") or ""
        self._wx_agent_id = c.get("wx_agent_id", "") or ""
        self._wx_user_id = c.get("wx_user_id", "@all") or "@all"
        self._wx_proxy_url = (c.get("wx_proxy_url", "") or "").rstrip("/")
        self._wx_no_proxy = c.get("wx_no_proxy", True)
        self._wx_msg_type = c.get("wx_msg_type", "news_notice") or "news_notice"
        self._bark_server = (c.get("bark_server", "https://api.day.app") or "https://api.day.app").rstrip("/")
        self._bark_keys = c.get("bark_keys", "") or ""
        self._enable_watch_link = c.get("enable_watch_link", False)
        self._watch_link_type = c.get("watch_link_type", "server") or "server"
        self._link_redirect_prefix = (c.get("link_redirect_prefix", "") or "").strip()
        self._emby_server_url = (c.get("emby_server_url", "") or "").rstrip("/")
        self._enable_tmdb = c.get("enable_tmdb", True)
        self._dedup_window = int(c.get("dedup_window") or 60)
        self._episode_cache_timeout = int(c.get("episode_cache_timeout") or 30)
        self._enable_custom_template = c.get("enable_custom_template", False)
        self._tg_template = c.get("tg_template") or self._default_tg_template()
        self._wx_title_template = c.get("wx_title_template") or self._default_wx_title_template()
        self._wx_body_template = c.get("wx_body_template") or self._default_wx_body_template()
        self._bark_title_template = c.get("bark_title_template") or self._default_bark_title_template()
        self._bark_body_template = c.get("bark_body_template") or self._default_bark_body_template()
        self._tmdb_api_key = c.get("tmdb_api_key", "") or ""
        self._tmdb_api_domain = c.get("tmdb_api_domain") or "api.themoviedb.org"
        self._tmdb_image_domain = c.get("tmdb_image_domain") or "image.tmdb.org"
        self._episode_cache.CACHE_TIMEOUT = self._episode_cache_timeout

    @property
    def _effective_tg_api_host(self) -> str:
        return self._tg_api_host or "https://api.telegram.org"

    @property
    def _effective_wx_proxy_url(self) -> str:
        return self._wx_proxy_url or "https://qyapi.weixin.qq.com"

    @property
    def _effective_wx_user_id(self) -> str:
        return self._wx_user_id or "@all"

    # --------------------------- HTTP（代理策略） --------------------------- #
    # TMDB / Telegram / Bark：默认 requests（trust_env=True），自动走平台注入的代理环境变量。
    # 企业微信：wx_no_proxy=True 时用 trust_env=False 的会话绕过代理（对应原 _wx_proxies=None）。
    def _wx_request(self, method: str, url: str, **kwargs):
        if self._wx_no_proxy:
            sess = requests.Session()
            sess.trust_env = False
            return sess.request(method, url, **kwargs)
        return requests.request(method, url, **kwargs)

    # --------------------------- 默认模板 --------------------------- #
    @staticmethod
    def _default_tg_template() -> str:
        return (
            "<b>{{server_name}} | {{status_text}}</b>\n\n"
            "<b>【{{item_name}}】</b>\n{{episode_text}}\n\n"
            "👥 主演：{{cast}}\n📺 类型：{{genres}}\n⭐ 评分：{{rating}}\n📅 日期：{{release_date}}\n\n"
            "📝 简介：\n<blockquote>{{overview}}</blockquote>\n\n"
            "▶️ 立即观看：{{play_url}}\nℹ️ 了解更多：{{tmdb_url}}"
        )

    @staticmethod
    def _default_wx_title_template() -> str:
        return "{{server_name}} | {{status_text}} | 【{{item_name}}】"

    @staticmethod
    def _default_wx_body_template() -> str:
        return (
            "{{episode_text}}\n"
            "👥 主演：{{cast}}\n📺 类型：{{genres}}\n⭐ 评分：{{rating}}\n📅 日期：{{release_date}}\n\n"
            "{{overview}}"
        )

    @staticmethod
    def _default_bark_title_template() -> str:
        return "{{server_name}} | {{status_text}}\n【{{item_name}}】"

    @staticmethod
    def _default_bark_body_template() -> str:
        return (
            "{{episode_text}}\n"
            "👥 {{cast}}\n📺 {{genres}}  ⭐ {{rating}}\n📅 {{release_date}}\n\n"
            "{{overview}}"
        )

    # --------------------------- Webhook 入口 --------------------------- #
    async def handle_webhook(self, req):
        """@ctx.on_webhook 处理器。快速取出 JSON 后把重活挪到线程，避免阻塞事件循环。"""
        message = None
        try:
            message = req.json
        except Exception:
            message = None
        if message is None:
            raw = getattr(req, "text", None) or getattr(req, "body", None)
            if raw:
                try:
                    message = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))
                except Exception as e:
                    self.ctx.log.warning(f"AWEmbyPush Webhook 解析请求体失败：{e}")
                    return {"success": False, "message": str(e)}
        if not message:
            return {"success": False, "message": "空请求或非 JSON"}
        try:
            await asyncio.to_thread(self.process, message)
        except Exception as e:  # noqa: BLE001
            self.ctx.log.error(f"AWEmbyPush 处理 webhook 异常：{e}\n{traceback.format_exc()}")
            return {"success": False, "message": str(e)}
        return {"success": True}

    def process(self, message: dict):
        """同步处理（跑在线程里）：解析 → 去重 → 分发。"""
        self._load_config()
        self.ctx.log.debug(f"AWEmbyPush 收到 webhook：{message.get('Event') or message.get('NotificationType')}")
        message = self._preprocess_jellyfin(message)
        if not message:
            return
        result = self._parse_emby_json(message)
        if not result:
            return
        event_info, server_name, premiere_year = result
        if event_info.event in ("system.webhooktest", "system.notificationtest"):
            self._send_test_notification(event_info, server_name=server_name)
        elif event_info.event in ("library.new", "ItemAdded"):
            if event_info.item_type in ("MOV", "TV", "SHOW", "Episode", "Movie"):
                if (event_info.item_type in ("TV", "SHOW", "Episode")
                        and not event_info.season_id and not event_info.episode_id):
                    self.ctx.log.debug(f"AWEmbyPush 跳过无季集信息的 TV 事件：{event_info.item_name}")
                    return
                if not self._check_dedup(event_info):
                    self._dispatch(event_info, server_name=server_name, premiere_year=premiere_year)

    def _preprocess_jellyfin(self, message: dict) -> dict:
        """将 Jellyfin Webhook 格式转换为 Emby 格式"""
        if "NotificationType" not in message:
            return message
        ntype = message.get("NotificationType", "")
        if ntype != "ItemAdded" or message.get("ItemType") not in ("Movie", "Episode"):
            if ntype == "NotificationTest":
                return {
                    "Event": "system.notificationtest",
                    "Server": {"Name": message.get("ServerName", ""), "Type": "Jellyfin"},
                }
            return {}
        result = {
            "Event": "library.new",
            "Item": {"ProviderIds": {}},
            "Server": {
                "Name": message.get("ServerName", ""),
                "Type": "Jellyfin",
                "Url": message.get("ServerUrl", ""),
            },
        }
        item = result["Item"]
        if message.get("ItemType") == "Movie":
            item["Type"] = "Movie"
            item["Name"] = message.get("Name", "")
        else:
            item["Type"] = "Episode"
            item["SeriesName"] = message.get("SeriesName", "")
            item["IndexNumber"] = message.get("EpisodeNumber")
            item["ParentIndexNumber"] = message.get("SeasonNumber")
        item["Id"] = message.get("ItemId", "")
        item["PremiereDate"] = str(message.get("Year", ""))
        if message.get("Provider_tmdb"):
            item["ProviderIds"]["Tmdb"] = message["Provider_tmdb"]
        if message.get("Provider_tvdb"):
            item["ProviderIds"]["Tvdb"] = message["Provider_tvdb"]
        return result

    def _parse_emby_json(self, message: dict) -> Optional[tuple]:
        """解析 Emby JSON 格式的 Webhook 报文，返回 (_EventInfo, server_name, premiere_year)"""
        event_type = message.get("Event")
        if not event_type:
            return None
        event_info = _EventInfo(event=event_type, channel="emby")
        server_name = ""
        server_obj = message.get("Server")
        if server_obj and isinstance(server_obj, dict):
            server_name = server_obj.get("Name") or ""
        premiere_year = ""
        item = message.get("Item")
        if item:
            item_type_raw = item.get("Type")
            if item_type_raw in ("Episode", "Series", "Season"):
                event_info.item_type = "TV"
                series_name = item.get("SeriesName") or item.get("Name") or ""
                s = item.get("ParentIndexNumber")
                e = item.get("IndexNumber")
                event_info.item_name = series_name
                event_info.item_id = item.get("SeriesId") or item.get("Id")
                event_info.season_id = str(s) if s else None
                event_info.episode_id = str(e) if e else None
            elif item_type_raw == "Audio":
                event_info.item_type = "AUD"
                event_info.item_name = item.get("Album") or item.get("Name")
                event_info.item_id = item.get("AlbumId") or item.get("Id")
            else:
                event_info.item_type = "MOV"
                event_info.item_name = item.get("Name", "")
                event_info.item_id = item.get("Id")
            event_info.item_path = item.get("Path")
            event_info.tmdb_id = item.get("ProviderIds", {}).get("Tmdb")
            event_info.overview = item.get("Overview") or ""
            premiere = item.get("PremiereDate") or ""
            if premiere:
                try:
                    if premiere.isdigit():
                        premiere_year = premiere
                    else:
                        premiere_year = str(datetime.fromisoformat(
                            premiere.replace("Z", "+00:00")
                        ).year)
                except Exception:
                    pass
        if message.get("Session"):
            event_info.ip = message["Session"].get("RemoteEndPoint")
            event_info.device_name = message["Session"].get("DeviceName")
            event_info.client = message["Session"].get("Client")
        if message.get("User"):
            event_info.user_name = message["User"].get("Name")
        return (event_info, server_name, premiere_year)

    # --------------------------- TMDB --------------------------- #
    def _tmdb_request(self, path: str) -> Optional[dict]:
        if not self._tmdb_api_key:
            return None
        try:
            url = f"https://{self._tmdb_api_domain}/3{path}"
            sep = "&" if "?" in path else "?"
            url += f"{sep}api_key={self._tmdb_api_key}&language=zh-CN"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            self.ctx.log.warning(f"AWEmbyPush TMDB API {path} 返回 {resp.status_code}")
        except Exception as e:
            self.ctx.log.warning(f"AWEmbyPush TMDB API 请求失败：{e}")
        return None

    def _tmdb_image_url(self, path: str, size: str = "w500") -> str:
        if not path:
            return ""
        return f"https://{self._tmdb_image_domain}/t/p/{size}{path}"

    def _search_tmdb_id(self, name: str, media_type: str, year: str = "") -> str:
        if not self._tmdb_api_key or not name:
            return ""
        search_type = "tv" if media_type in ("TV", "SHOW", "Episode") else "movie"
        path = f"/search/{search_type}?query={quote(name)}&page=1"
        if year:
            path += f"&year={year}"
        data = self._tmdb_request(path)
        if data and data.get("results"):
            first = data["results"][0]
            tmdb_id = str(first.get("id", ""))
            title = first.get("name") or first.get("title") or name
            self.ctx.log.info(f"AWEmbyPush TMDB 搜索到：{title} (ID: {tmdb_id})")
            return tmdb_id
        self.ctx.log.warning(f"AWEmbyPush TMDB 搜索无结果：{name} ({year})")
        return ""

    def _fetch_tmdb_metadata(self, tmdb_id: str, is_ep: bool,
                             season_id: Optional[str] = None,
                             episode_id: Optional[str] = None) -> dict:
        meta = {
            "genres": "", "cast": "", "rating": "",
            "release_date": "", "poster_url": "",
            "backdrop_url": "", "still_url": "", "overview_tmdb": "",
        }
        if not tmdb_id or not self._enable_tmdb or not self._tmdb_api_key:
            return meta
        try:
            if is_ep:
                self._fetch_tv_metadata(tmdb_id, season_id, episode_id, meta)
            else:
                self._fetch_movie_metadata(tmdb_id, meta)
        except Exception as e:
            self.ctx.log.warning(f"AWEmbyPush TMDB 元数据获取失败：{e}")
        has_fields = [k for k, v in meta.items() if v]
        self.ctx.log.info(f"AWEmbyPush TMDB 元数据 (ID={tmdb_id})：{', '.join(has_fields) if has_fields else '无数据'}")
        return meta

    def _fetch_movie_metadata(self, tmdb_id: str, meta: dict):
        data = self._tmdb_request(f"/movie/{tmdb_id}")
        if data:
            meta["rating"] = str(data.get("vote_average", ""))
            meta["release_date"] = data.get("release_date", "")
            meta["overview_tmdb"] = data.get("overview", "")
            genres = data.get("genres", [])
            if genres:
                meta["genres"] = ", ".join(GENRE_MAP.get(g["name"], g["name"]) for g in genres[:3])
            if data.get("poster_path"):
                meta["poster_url"] = self._tmdb_image_url(data["poster_path"])
            if data.get("backdrop_path"):
                meta["backdrop_url"] = self._tmdb_image_url(data["backdrop_path"])
        credits = self._tmdb_request(f"/movie/{tmdb_id}/credits")
        if credits and credits.get("cast"):
            meta["cast"] = ", ".join(a["name"] for a in credits["cast"][:5])

    def _fetch_tv_metadata(self, tmdb_id: str, season_id: Optional[str],
                           episode_id: Optional[str], meta: dict):
        tv = self._tmdb_request(f"/tv/{tmdb_id}")
        if tv:
            meta["rating"] = str(tv.get("vote_average", ""))
            meta["release_date"] = tv.get("first_air_date", "")
            if not meta.get("overview_tmdb"):
                meta["overview_tmdb"] = tv.get("overview", "")
            genres = tv.get("genres", [])
            if genres:
                meta["genres"] = ", ".join(GENRE_MAP.get(g["name"], g["name"]) for g in genres[:3])
            if tv.get("poster_path"):
                meta["poster_url"] = self._tmdb_image_url(tv["poster_path"])
            if tv.get("backdrop_path"):
                meta["backdrop_url"] = self._tmdb_image_url(tv["backdrop_path"])
        credits = self._tmdb_request(f"/tv/{tmdb_id}/credits")
        if credits and credits.get("cast"):
            meta["cast"] = ", ".join(a["name"] for a in credits["cast"][:5])
        if season_id:
            try:
                s = int(season_id)
                season_data = self._tmdb_request(f"/tv/{tmdb_id}/season/{s}")
                if season_data and season_data.get("poster_path"):
                    meta["poster_url"] = self._tmdb_image_url(season_data["poster_path"])
                if season_data and not meta.get("release_date") and season_data.get("air_date"):
                    meta["release_date"] = season_data["air_date"]
            except (ValueError, TypeError):
                pass
        if season_id and episode_id:
            try:
                s, e = int(season_id), int(episode_id)
                ep_data = self._tmdb_request(f"/tv/{tmdb_id}/season/{s}/episode/{e}")
                if ep_data:
                    if ep_data.get("air_date"):
                        meta["release_date"] = ep_data["air_date"]
                    if ep_data.get("overview"):
                        meta["overview_tmdb"] = ep_data["overview"]
                    if ep_data.get("still_path"):
                        meta["still_url"] = self._tmdb_image_url(ep_data["still_path"])
            except (ValueError, TypeError):
                pass

    # --------------------------- 去重 / 分发 --------------------------- #
    def _check_dedup(self, info: _EventInfo) -> bool:
        is_ep = info.item_type in ("TV", "SHOW", "Episode")
        tmdb_id = info.tmdb_id or ""
        if info.item_type in ("MOV", "Movie"):
            media_id = tmdb_id or info.item_name or ""
            fingerprint = f"movie_{media_id}"
        elif is_ep:
            series = info.item_name or ""
            fingerprint = f"episode_{series}_{info.season_id or ''}_{info.episode_id or ''}"
        else:
            fingerprint = f"other_{info.item_name or ''}_{info.item_id or ''}"
        now = time.time()
        with self._fingerprint_lock:
            expired = [k for k, v in self._message_fingerprints.items() if now - v > self._dedup_window]
            for k in expired:
                del self._message_fingerprints[k]
            if fingerprint in self._message_fingerprints:
                elapsed = now - self._message_fingerprints[fingerprint]
                self.ctx.log.info(f"AWEmbyPush 跳过重复消息（{elapsed:.1f}秒前已处理）：{info.item_name}")
                return True
            self._message_fingerprints[fingerprint] = now
        return False

    def _send_test_notification(self, info: _EventInfo, server_name: str = ""):
        display_name = server_name or (info.channel.upper() if info.channel else "MediaServer")
        media = {
            "item_name": "Webhook 连通性测试", "item_type": "MOV", "is_ep": False,
            "status_text": "测试通知", "episode_text": "",
            "overview": "这是一条来自 AWEmbyPush 的测试消息，说明 Webhook 通道已正常连通。",
            "image_url": "", "server_name": display_name, "channel": info.channel or "",
            "play_url": "", "tmdb_url": "", "tmdb_id": "",
            "season_id": None, "episode_id": None,
            "genres": "", "cast": "", "rating": "",
            "release_date": "", "poster_url": "", "backdrop_url": "", "still_url": "",
        }
        self._send_all_channels(media)
        self.ctx.log.info("AWEmbyPush 已响应 Webhook 测试通知")

    def _dispatch(self, info: _EventInfo, server_name: str = "", premiere_year: str = ""):
        is_ep = info.item_type in ("TV", "SHOW", "Episode")
        status_text = "新剧速递" if is_ep else "新片速递"
        episode_text = ""
        if is_ep:
            s = str(info.season_id) if info.season_id else ""
            e = str(info.episode_id) if info.episode_id else ""
            if s and e:
                episode_text = f"第{s}季：第{e}集"
            elif s:
                episode_text = f"第{s}季"
        display_name = server_name or (info.channel.upper() if info.channel else "MediaServer")
        if not info.tmdb_id and self._enable_tmdb:
            self.ctx.log.info(f"AWEmbyPush Emby 未提供 TMDB ID，搜索：{info.item_name}")
            info.tmdb_id = self._search_tmdb_id(info.item_name or "", info.item_type or "", premiere_year)
        elif info.tmdb_id:
            self.ctx.log.info(f"AWEmbyPush 使用 Emby 提供的 TMDB ID：{info.tmdb_id}（{info.item_name}）")
        play_url = self._build_play_url(info)
        tmdb_url = (
            f"https://www.themoviedb.org/{'tv' if is_ep else 'movie'}/{info.tmdb_id}?language=zh-CN"
            if info.tmdb_id else ""
        )
        tmdb_meta = self._fetch_tmdb_metadata(info.tmdb_id, is_ep, info.season_id, info.episode_id)
        overview = info.overview or tmdb_meta.get("overview_tmdb", "") or ""
        emby_image = ""
        if self._emby_server_url and info.item_id:
            emby_image = f"{self._emby_server_url}/Items/{info.item_id}/Images/Primary"
        if is_ep:
            image_url = (
                tmdb_meta.get("still_url") or tmdb_meta.get("backdrop_url")
                or tmdb_meta.get("poster_url") or emby_image or info.image_url or ""
            )
        else:
            image_url = (
                tmdb_meta.get("backdrop_url") or tmdb_meta.get("poster_url")
                or emby_image or info.image_url or ""
            )
        media = {
            "item_name": info.item_name or "", "item_type": info.item_type or "",
            "is_ep": is_ep, "status_text": status_text, "episode_text": episode_text,
            "overview": overview, "image_url": image_url, "server_name": display_name,
            "channel": info.channel or "", "play_url": play_url, "tmdb_url": tmdb_url,
            "tmdb_id": info.tmdb_id or "", "season_id": info.season_id, "episode_id": info.episode_id,
            "genres": tmdb_meta.get("genres", ""), "cast": tmdb_meta.get("cast", ""),
            "rating": tmdb_meta.get("rating", ""), "release_date": tmdb_meta.get("release_date", ""),
            "poster_url": tmdb_meta.get("poster_url", ""),
            "backdrop_url": tmdb_meta.get("backdrop_url", ""),
            "still_url": tmdb_meta.get("still_url", ""),
        }
        if self._episode_cache:
            self._episode_cache.add(media)
        else:
            self._send_all_channels(media)

    def _send_all_channels(self, media: dict):
        sent_channels = []
        if self._tg_bot_token and self._tg_chat_id:
            self._send_telegram(media)
            sent_channels.append("Telegram")
        if self._wx_corp_id and self._wx_corp_secret and self._wx_agent_id:
            self._send_wechat(media)
            sent_channels.append("微信")
        if self._bark_server and self._bark_keys:
            self._send_bark(media)
            sent_channels.append("Bark")
        if not sent_channels:
            self.ctx.log.warning(
                "AWEmbyPush 没有可用的通知渠道，请在插件配置中填写 Telegram / 企业微信 / Bark 任一配置。"
                f"（TG Token: {'有' if self._tg_bot_token else '无'}, "
                f"TG Chat ID: {'有' if self._tg_chat_id else '无'}, "
                f"微信 Corp ID: {'有' if self._wx_corp_id else '无'}, "
                f"Bark Keys: {'有' if self._bark_keys else '无'}）"
            )
        if media.get("status_text") == "测试通知":
            return
        cards = self._load_cards()
        cards.append({
            "time": datetime.now().strftime("%m-%d %H:%M"),
            "item_name": media["item_name"], "item_type": media["item_type"],
            "season_id": media.get("season_id"), "episode_id": media.get("episode_id"),
            "image_url": media.get("poster_url") or media.get("image_url", ""),
            "channel": media.get("channel", ""), "channels": " / ".join(sent_channels),
            "episode_text": media.get("episode_text", ""),
        })
        self._save_cards(cards)

    # --------------------------- 最近推送记录（ctx.kv）--------------------------- #
    def _load_cards(self) -> List[dict]:
        raw = self.ctx.kv.get("recent_cards")
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    def _save_cards(self, cards: List[dict]):
        try:
            self.ctx.kv.set("recent_cards", json.dumps(cards[-10:], ensure_ascii=False))
        except Exception as e:
            self.ctx.log.warning(f"AWEmbyPush 保存推送记录失败：{e}")

    # --------------------------- 链接构建 --------------------------- #
    def _build_play_url(self, info: _EventInfo) -> str:
        t = self._watch_link_type
        tmdb_id = info.tmdb_id or ""
        is_ep = info.item_type in ("TV", "SHOW", "Episode")
        if t == "forward":
            media_type = "tv" if is_ep else "movie"
            if tmdb_id:
                return f"forward://tmdb?id={tmdb_id}&type={media_type}"
            return f"forward://search?q={info.item_name or ''}"
        if t == "infuse" and tmdb_id:
            if is_ep:
                s = info.season_id or 1
                e = info.episode_id or 1
                return f"infuse://series/{tmdb_id}-{s}-{e}"
            return f"infuse://movie/{tmdb_id}"
        base = self._emby_server_url
        if base and info.item_id:
            return f"{base}/web/index.html#!/item?id={info.item_id}"
        return base or ""

    def _build_redirect_url(self, raw_url: str) -> str:
        prefix = (self._link_redirect_prefix or "").strip()
        if not prefix or not prefix.startswith(("http://", "https://")):
            return ""
        encoded = quote(raw_url, safe="")
        if "{url}" in prefix:
            return prefix.replace("{url}", encoded)
        sep = "&" if "?" in prefix else "?"
        return f"{prefix}{sep}url={encoded}"

    # --------------------------- 模板渲染 --------------------------- #
    def _template_context(self, media: dict) -> dict:
        return {
            "server_name": media.get("server_name", ""),
            "status_text": media.get("status_text", ""),
            "item_name": media.get("item_name", ""),
            "episode_text": media.get("episode_text", ""),
            "genres": media.get("genres", ""),
            "cast": media.get("cast", ""),
            "rating": media.get("rating", ""),
            "release_date": media.get("release_date", ""),
            "overview": media.get("overview", ""),
            "play_url": media.get("play_url", ""),
            "tmdb_url": media.get("tmdb_url", ""),
            "channel": media.get("channel", ""),
        }

    def _render_template(self, template: str, media: dict, escape_html: bool = False) -> str:
        if not template:
            return ""
        ctx = self._template_context(media)

        def _replace(match):
            key = match.group(1).strip()
            value = str(ctx.get(key, ""))
            return html.escape(value) if escape_html else value

        return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", _replace, template)

    # --------------------------- Telegram --------------------------- #
    def _send_telegram(self, media: dict):
        type_text = media.get("genres") or ("剧集" if media.get("is_ep") else "电影")
        date_label = "📺 首播" if media.get("is_ep") else "🎬 上映"
        release_date = media.get("release_date", "") or "Unknown"
        if self._enable_custom_template and self._tg_template:
            caption = self._render_template(self._tg_template, media, escape_html=True)
        else:
            caption = f"<b>{media['server_name']} | {media['status_text']}</b>\n\n"
            caption += "─────────────────────\n\n"
            caption += f"<b>【{media['item_name']}】</b>\n"
            if media["episode_text"]:
                caption += f"{media['episode_text']} | 新更上线\n\n"
            else:
                caption += "\n"
            if media.get("cast"):
                caption += f"👥 主演：{media['cast']}\n"
            caption += f"📺 类型：{type_text}\n"
            if media.get("rating"):
                caption += f"⭐ 评分：{media['rating']}\n"
            caption += f"{date_label}：{release_date}\n\n"
            if media.get("overview"):
                caption += f"📝 内容简介：\n<blockquote>{_truncate(media['overview'], 150)}</blockquote>\n\n"
            caption += "─────────────────────"
        buttons = []
        play_url = media.get("play_url", "")
        tmdb_url = media.get("tmdb_url", "")
        using_custom = bool(self._enable_custom_template and self._tg_template)
        if self._enable_watch_link and play_url:
            if play_url.startswith(("http://", "https://")):
                if not using_custom:
                    buttons.append({"text": "▶️ 立即观看", "url": play_url})
            else:
                redirect_url = self._build_redirect_url(play_url)
                if redirect_url:
                    if not using_custom:
                        buttons.append({"text": "▶️ 立即观看", "url": redirect_url})
                elif not using_custom:
                    caption += f"\n\n▶️ 立即观看：{html.escape(play_url)}"
        if tmdb_url and not using_custom:
            buttons.append({"text": "ℹ️ 了解更多", "url": tmdb_url})
        reply_markup = {"inline_keyboard": [buttons]} if buttons else None
        photo = media.get("image_url", "")
        try:
            api = self._effective_tg_api_host
            token = self._tg_bot_token
            chat_id = self._tg_chat_id
            payload = {"chat_id": chat_id, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            if photo:
                payload["photo"] = photo
                payload["caption"] = caption
                resp = requests.post(f"{api}/bot{token}/sendPhoto", json=payload, timeout=15)
            else:
                payload["text"] = caption
                resp = requests.post(f"{api}/bot{token}/sendMessage", json=payload, timeout=15)
            if resp.status_code != 200:
                self.ctx.log.error(f"AWEmbyPush Telegram HTTP {resp.status_code}：{resp.text[:500]}")
                return
            result = resp.json()
            if result.get("ok"):
                self.ctx.log.info(f"AWEmbyPush Telegram 发送成功：{media['item_name']}")
            else:
                self.ctx.log.error(f"AWEmbyPush Telegram 发送失败：{result}")
        except Exception as e:
            self.ctx.log.error(f"AWEmbyPush Telegram 发送失败：{e}")

    # --------------------------- 企业微信 --------------------------- #
    def _get_wx_token(self) -> Optional[str]:
        try:
            res = self._wx_request(
                "GET",
                f"{self._effective_wx_proxy_url}/cgi-bin/gettoken",
                params={"corpid": self._wx_corp_id, "corpsecret": self._wx_corp_secret},
                timeout=10,
            )
            data = res.json()
            if data.get("errcode", 0) == 0:
                return data["access_token"]
            self.ctx.log.error(f"获取企业微信 token 失败：{data}")
        except Exception as e:
            self.ctx.log.error(f"获取企业微信 token 异常：{e}")
        return None

    def _send_wechat(self, media: dict):
        token = self._get_wx_token()
        if not token:
            return
        image_url = media.get("image_url", "")
        play_url = media.get("play_url", "")
        tmdb_url = media.get("tmdb_url", "")
        if play_url.startswith(("http://", "https://")):
            safe_play_url = play_url
        else:
            safe_play_url = self._build_redirect_url(play_url) if play_url else ""
        safe_tmdb_url = tmdb_url if tmdb_url.startswith(("http://", "https://")) else ""
        jump_url = (safe_play_url if (self._enable_watch_link and safe_play_url)
                    else safe_tmdb_url or "https://www.themoviedb.org/")
        agent_id = self._wx_agent_id
        agent_id_val = int(agent_id) if str(agent_id).isdigit() else agent_id
        episode_text = media.get("episode_text", "") or "新更上线"
        type_text = media.get("genres") or ("剧集" if media.get("is_ep") else "电影")
        date_label = "📺 首播" if media.get("is_ep") else "🎬 上映"
        release_date = media.get("release_date", "") or "Unknown"
        server_icon = f"https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{(media.get('channel') or 'emby').lower()}.png"
        try:
            url = f"{self._effective_wx_proxy_url}/cgi-bin/message/send?access_token={token}"
            if self._wx_msg_type == "news_notice":
                vertical_content = []
                if media.get("cast"):
                    vertical_content.append({"title": "👥 主演", "desc": media["cast"]})
                vertical_content.append({"title": "📺 类型", "desc": type_text})
                if media.get("rating"):
                    vertical_content.append({"title": "⭐ 评分", "desc": media["rating"]})
                vertical_content.append({"title": date_label, "desc": release_date})
                if media.get("overview"):
                    vertical_content.append({"title": "📝 内容简介", "desc": _truncate(media["overview"], 120)})
                card = {
                    "card_type": "news_notice",
                    "source": {"icon_url": server_icon, "desc": f"{media['server_name']} | {media['status_text']}", "desc_color": 0},
                    "main_title": {"title": f"【{media['item_name']}】", "desc": episode_text},
                    "card_image": {"url": image_url, "aspect_ratio": 2.25},
                    "vertical_content_list": vertical_content,
                    "jump_list": (
                        [{"type": 1, "url": safe_play_url, "title": "▶️ 立即观看"},
                         {"type": 1, "url": safe_tmdb_url, "title": "ℹ️ 了解更多"}]
                        if (self._enable_watch_link and safe_play_url and safe_tmdb_url) else
                        [{"type": 1, "url": jump_url, "title": "ℹ️ 了解更多"}]
                    ),
                    "card_action": {"type": 1, "url": jump_url},
                }
                if self._enable_custom_template:
                    if self._wx_title_template:
                        card["main_title"]["title"] = self._render_template(self._wx_title_template, media)
                    if self._wx_body_template:
                        wx_desc = self._render_template(self._wx_body_template, media).replace("\r", "")
                        card["vertical_content_list"] = [{
                            "title": "📝 自定义内容",
                            "desc": _truncate(wx_desc, 300),
                        }]
                payload = {"touser": self._effective_wx_user_id, "msgtype": "template_card",
                           "agentid": agent_id_val, "template_card": card}
            else:
                title_text = f"{media['server_name']} | {media['status_text']} | 【{media['item_name']}】"
                if media.get("episode_text"):
                    title_text += f" | {media['episode_text']}"
                desc_parts = []
                if media.get("cast"):
                    desc_parts.append(f"👥 主演：{media['cast']}")
                desc_parts.append(f"📺 类型：{type_text}")
                if media.get("rating"):
                    desc_parts.append(f"⭐ 评分：{media['rating']}")
                desc_parts.append(f"{date_label}：{release_date}")
                if media.get("overview"):
                    desc_parts.append(f"\n📝 内容简介：{_truncate(media['overview'], 100)}")
                if self._enable_custom_template:
                    if self._wx_title_template:
                        title_text = self._render_template(self._wx_title_template, media)
                    if self._wx_body_template:
                        desc_parts = [_truncate(self._render_template(self._wx_body_template, media).replace("\r", ""), 500)]
                payload = {
                    "touser": self._effective_wx_user_id, "msgtype": "news", "agentid": agent_id_val,
                    "news": {"articles": [{"title": title_text, "description": "\n".join(desc_parts),
                                           "url": jump_url, "picurl": image_url}]},
                }
            res = self._wx_request("POST", url, json=payload, timeout=15)
            data = res.json()
            if data.get("errcode", 0) == 0:
                self.ctx.log.info(f"AWEmbyPush 企业微信发送成功：{media['item_name']}")
            else:
                self.ctx.log.error(f"AWEmbyPush 企业微信发送失败：{data}")
        except Exception as e:
            self.ctx.log.error(f"AWEmbyPush 企业微信发送异常：{e}")

    # --------------------------- Bark --------------------------- #
    def _send_bark(self, media: dict):
        type_text = media.get("genres") or ("剧集" if media.get("is_ep") else "电影")
        date_label = "📺 首播" if media.get("is_ep") else "🎬 上映"
        release_date = media.get("release_date", "") or "Unknown"
        play_url_raw = media.get("play_url", "")
        tmdb_url_raw = media.get("tmdb_url", "")
        if self._enable_custom_template and self._bark_body_template:
            body = self._render_template(self._bark_body_template, media)
        else:
            body = ""
            if media.get("cast"):
                body += f"👥 主演：{media['cast']}\n"
            body += f"📺 类型：{type_text}\n"
            if media.get("rating"):
                body += f"⭐ 评分：{media['rating']}\n"
            body += f"{date_label}：{release_date}"
            if media.get("overview"):
                body += f"\n\n📝 {_truncate(media['overview'], 80)}"
            link_lines = ""
            if self._enable_watch_link and play_url_raw:
                if play_url_raw.startswith(("http://", "https://")):
                    link_lines += f"\n▶️ 立即观看：{play_url_raw}"
            if tmdb_url_raw:
                link_lines += f"\nℹ️ 了解更多：{tmdb_url_raw}"
            if link_lines:
                body += f"\n{link_lines}"
        url_target = (play_url_raw if (self._enable_watch_link and play_url_raw)
                      else tmdb_url_raw)
        poster_icon = media.get("poster_url") or ""
        logo_icon = "https://raw.githubusercontent.com/AWdress/MoviePilot-Plugins/main/plugins/awembypush/logo.png"
        icon_url = poster_icon or logo_icon
        keys = [k.strip() for k in self._bark_keys.split(",") if k.strip()]
        image_url = media.get("image_url") or media.get("poster_url") or ""
        group = "新剧速递" if media.get("is_ep") else "新片速递"
        ep_text = media.get("episode_text") or ""
        subtitle = f"{ep_text} | 新更上线" if ep_text else (media.get("genres") or "")
        for key in keys:
            title = f"{media['server_name']} | {media['status_text']}\n\n【{media['item_name']}】"
            if self._enable_custom_template and self._bark_title_template:
                title = self._render_template(self._bark_title_template, media)
            payload = {
                "title": title,
                "body": body or "新内容已入库",
                "icon": icon_url, "url": url_target, "device_key": key,
                "group": group,
            }
            if subtitle:
                payload["subtitle"] = subtitle
            if image_url:
                payload["image"] = image_url
            try:
                res = requests.post(f"{self._bark_server}/push", json=payload, timeout=15)
                if res.status_code == 200:
                    self.ctx.log.info(f"AWEmbyPush Bark ({key[:8]}...) 发送成功：{media['item_name']}")
                else:
                    self.ctx.log.error(f"AWEmbyPush Bark ({key[:8]}...) 发送失败：{res.status_code} {res.text}")
            except Exception as e:
                self.ctx.log.error(f"AWEmbyPush Bark ({key[:8]}...) 发送异常：{e}")

    def shutdown(self):
        self._episode_cache.cancel_all()


async def setup(ctx):
    pusher = AWEmbyPush(ctx)

    @ctx.on_webhook
    async def on_hook(req):
        return await pusher.handle_webhook(req)

    # ── 前端(Config.vue)用的后端接口 ──
    @ctx.on_api("/recent", methods=["GET"])
    async def _api_recent(req):
        cards = pusher._load_cards()
        return {"items": list(reversed(cards))}

    @ctx.on_api("/clear", methods=["POST"])
    async def _api_clear(req):
        try:
            ctx.kv.delete("recent_cards")
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}

    @ctx.on_api("/test", methods=["POST"])
    async def _api_test(req):
        """发一条测试通知到已配置的渠道（验证 TG/企微/Bark 连通性，不依赖 Emby）。"""
        c = ctx.config
        channels = []
        if c.get("tg_bot_token") and c.get("tg_chat_id"):
            channels.append("Telegram")
        if c.get("wx_corp_id") and c.get("wx_corp_secret") and c.get("wx_agent_id"):
            channels.append("企业微信")
        if c.get("bark_server") and c.get("bark_keys"):
            channels.append("Bark")
        if not channels:
            return {"ok": False, "message": "没有已配置的推送渠道（TG/企微/Bark 至少填一个）"}

        def _do():
            pusher._load_config()
            info = _EventInfo(event="system.webhooktest", channel="emby")
            pusher._send_test_notification(info, server_name="AWEmbyPush 测试")
        try:
            await asyncio.to_thread(_do)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}
        return {"ok": True, "message": "已向 " + " / ".join(channels) + " 发送测试通知，请到对应客户端查看"}

    ctx.add_cleanup(pusher.shutdown)
    ctx.log.info("AWEmbyPush 已启用，等待 Emby/Jellyfin Webhook。到插件「配置」查看入站地址。")


async def teardown(ctx):
    pass
