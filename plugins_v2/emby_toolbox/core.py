# =============================================================================
# AWBotNest 插件：Emby 工具箱（emby_toolbox）
#
# 集成 Emby 实用维护功能：
# 1. 剧集季集校验 / 按文件名修复
# 2. 删除单集 Genre
# 3. Genre 映射 / 删除
# 4. 季名刮削（TMDB）
# 5. 国家 / 语言转 Tag（TMDB）
# 6. 别名写入 SortName（TMDB）
# 7. STRM MediaInfo 刷新
# 8. 元数据缺失检查
#
# 说明：
# - 每个功能都有独立开关。
# - 每个功能也有独立 action 按钮。
# - 所有 Emby 写操作默认可选锁定数据，尽量减少后续被刮削覆盖。
# =============================================================================

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests

from .cover_templates import render_cover

__plugin__ = {
    "name": "Emby 工具箱",
    "id": "emby_toolbox",
    "version": "2.1.5",
    "author": "AWdress",
    "description": "集成 Emby 剧集校验、Genre 清理/映射、季名刮削、国家语言 Tag、别名写入、STRM 刷新、元数据缺失检查等维护功能。支持定时执行与完整日志。",
    "icon": "https://cdn.simpleicons.org/emby",
    "changelog": "v2.0.4 优化 Genre 扫描速度与进度日志\n- 先使用媒体库批量结果筛选候选条目，仅对确需修改的条目读取完整详情\n- 增加扫描数量、更新数量和每 50 条进度日志，避免长时间无反馈\n\nv2.0.3 增强别名缓存与 Genre 中文化\n- 别名写入成功后持久化记录，后续扫描命中缓存直接跳过，避免重复请求和更新\n- Genre 映射内置常见英文到中文映射，同时保留自定义 JSON 覆盖\n- 增加 Genre 中文化命中、跳过和更新日志，更新 GenreItems 名称并保留已有 ID\n\nv2.0.2 统一富文本表格通知\n- 定时维护和任务结果改为平台结构化表格\n\nv2.0.1 修复 Emby API 客户端逻辑\n- 使用 VirtualFolders 正确解析媒体库 ID，并兼容旧版 Views 接口\n- 递归展开媒体库文件夹，补齐维护功能所需的元数据字段\n- 统一更新与 PlaybackInfo 请求路径，修复多项功能失败\n- 图标替换为 Emby Logo\n\nv2.0.0 原生 AWBotNest V2 迁移\n- 使用 Telethon 原生事件、调度、存储与生命周期接口\n- 保留原有功能、配置项和运行数据\n- 移除 V1 兼容运行层",
    "scope": "standalone",
    "render_mode": "vue",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 2,
    "default_enabled": False,
    "requirements": ["requests>=2.28", "Pillow>=10.0"],
    "resources": {
        "timeout_seconds": 1800,
        "max_concurrency": 1,
        "max_background_tasks": 2,
        "failure_threshold": 3,
        "recovery_seconds": 120,
    },
}

EP_REGEX = re.compile(r"[Ss](\d{1,2})[\._\- ]?[Ee](\d+)")
EP_FIELDS = "Path,ProviderIds,ParentIndexNumber,IndexNumber,SeriesName,Name,SeasonName"
NON_TARGET_LANG_REGEX = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\u0E00-\u0E7F\u0590-\u05FF]')
INVALID_ALT_CHARS = ['ā', 'á', 'ǎ', 'à', 'ē', 'é', 'ě', 'è', 'ī', 'í', 'ǐ', 'ì', 'ō', 'ó', 'ǒ', 'ò', 'ū', 'ú', 'ǔ', 'ù', 'ǖ', 'ǘ', 'ǚ', 'ǜ', 'デ', 'ô', 'â', 'Ś', 'ü', 'É']
COUNTRY_DICT = {
    'KR': '韩国', 'CN': '中国', 'HK': '香港', 'TW': '台湾',
    'JP': '日本', 'US': '美国', 'GB': '英国', 'FR': '法国',
    'DE': '德国', 'IN': '印度', 'RU': '俄罗斯', 'CA': '加拿大',
}
LANGUAGE_DICT = {
    'cn': '粤语', 'zh': '国语', 'ja': '日语', 'en': '英语',
    'ko': '韩语', 'fr': '法语', 'de': '德语', 'ru': '俄语', 'es': '西班牙语',
}
DEFAULT_COUNTRY = '其他国家'
DEFAULT_LANGUAGE = '其他语种'

DEFAULTS: Dict[str, Any] = {
    'emby_server': '', 'api_key': '', 'user_id': '', 'tmdb_key': '',
    'library_names': '', 'fix_lock_data': True, 'max_output': 50,
    'genre_mapping_json': '{\n  "Sci-Fi & Fantasy": "科幻",\n  "War & Politics": "战争"\n}',
    'genre_remove_list': '', 'add_hant_title': True, 'strm_delay': 3,
    'enable_episode_fix': True, 'enable_delete_episode_genre': False,
    'enable_genre_mapper': False, 'enable_season_renamer': False,
    'enable_country_scraper': False, 'enable_alt_renamer': False,
    'enable_strm_mediainfo': False, 'enable_damaged_check': False,
    'enable_category_covers': False, 'category_cover_types': 'genre,tag',
    'enable_auto_schedule': False, 'schedule_cron': '0 3 * * *',
    'schedule_functions': [],
}

# Keep the module metadata and the marketplace manifest in sync without
# duplicating the historical release notes below.
__plugin__["changelog"] = (
    "v2.1.5 新增本地模板分类封面\n"
    "- 使用 Pillow 固定模板生成 Genre/Tag 封面，不调用 AI\n"
    "- 支持仅 Genre、仅 Tag 或两类一起生成，并通过原配置反代上传 Emby\n\n"
    "v2.1.4 补齐 Anime/Cartoon Genre 中文映射\n"
    "- Anime、Cartoon 统一映射为动画，避免中英文 Genre 混杂\n\n"
    "v2.1.3 修复条目路径 GET 404 导致写入校验失败\n"
    "- GET /Items/{id} 返回 404 时改用管理员 Items?Ids 查询回读\n"
    "- 更新失败不再误用用户接口，避免返回 200 但 Genre/别名未改变\n\n"
    "v2.1.2 优化媒体库读取与 Emby 兼容回读\n"
    "- 使用 Recursive 分页读取媒体库，避免逐文件夹请求导致数小时运行\n"
    "- 管理员条目接口返回 404 时兼容用户接口回读，并保留实际生效校验\n"
    "\n"
    "v2.1.1 修复 Emby Genre 更新 DTO\n"
    "- 仅提交官方支持的 Genres 字段，由 Emby 自动重建 Genre 关联\n"
    "- 补充常见 Genre 中文映射，并为季名、Tag、别名写入增加生效校验\n"
    "- 删除单集 Genre 改为递归分页查询，避免逐季逐集串行耗时\n\n"
    + __plugin__.get("changelog", "")
)

# Emby 的 Genre 通常来自 TMDB，返回值以英文为主。原项目提供了显式
# Genre 映射，这里保留自定义 JSON 的覆盖能力，并内置常用英文 Genre，
# 使开启“Genre 映射”后无需再手工填写每一项。
DEFAULT_GENRE_MAPPING: Dict[str, str] = {
    'Action': '动作', 'Adventure': '冒险', 'Animation': '动画',
    'Comedy': '喜剧', 'Crime': '犯罪', 'Documentary': '纪录',
    'Anime': '动画', 'Cartoon': '动画',
    'Drama': '剧情', 'Family': '家庭', 'Fantasy': '奇幻',
    'History': '历史', 'Horror': '恐怖', 'Music': '音乐',
    'Mystery': '悬疑', 'Romance': '爱情', 'Science Fiction': '科幻', 'Sci-Fi': '科幻',
    'Sci-Fi & Fantasy': '科幻', 'Thriller': '惊悚', 'War': '战争',
    'War & Politics': '战争', 'Western': '西部',
    'Action & Adventure': '动作冒险', 'Food': '美食',
    'Martial Arts': '武侠', 'Mini-Series': '迷你剧', 'Suspense': '悬疑',
    'Reality': '真人秀', 'Soap': '肥皂剧', 'Talk': '脱口秀',
    'Kids': '儿童', 'News': '新闻', 'TV Movie': '电视电影',
    'Biography': '传记', 'Sport': '运动', 'Musical': '音乐剧',
    'Short': '短片', 'Disaster': '灾难', 'Film-Noir': '黑色电影',
}

FEATURES = {
    'episode_fix': ('剧集季集修复', '_episode_fix', False),
    'delete_episode_genre': ('删除单集 Genre', '_delete_episode_genre', False),
    'genre_mapper': ('Genre 中文化/映射', '_genre_mapper', False),
    'season_renamer': ('季名刮削', '_season_renamer', True),
    'country_scraper': ('国家/语言标签', '_country_scraper', True),
    'alt_renamer': ('别名写入', '_alt_renamer', True),
    'strm_mediainfo': ('STRM 媒体信息', '_strm_mediainfo', False),
    'damaged_check': ('元数据缺失检查', '_damaged_check', False),
    'category_covers': ('分类封面生成', '_category_covers', False),
}

_RUNTIME: Dict[str, Any] = {
    'running': False, 'task': '', 'source': '', 'started_at': '',
    'finished_at': '', 'last_result': '', 'last_ok': None,
}
_RECENT = deque(maxlen=30)

# setup() 将平台异步存储的快照和线程安全写入函数注入这里。维护 worker
# 在 asyncio.to_thread 中运行，不能直接 await ctx.storage，因此通过
# setup 提供的 persist 回调把别名缓存写回平台存储。
_EMBY_STATE: Dict[str, Any] = {}
_EMBY_PERSIST = None
_ALT_CACHE_KEY = 'emby_toolbox.alt_renamer_cache.v1'


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _cfg(ctx) -> Dict[str, Any]:
    c = {**DEFAULTS, **dict(ctx.config or {})}
    return {
        'emby_server': str(c.get('emby_server', '') or '').strip(),
        'api_key': str(c.get('api_key', '') or '').strip(),
        'user_id': str(c.get('user_id', '') or '').strip(),
        'tmdb_key': str(c.get('tmdb_key', '') or '').strip(),
        'library_names': str(c.get('library_names', '') or ''),
        'fix_lock_data': bool(c.get('fix_lock_data', True)),
        'max_output': int(c.get('max_output', 50) or 50),
        'genre_mapping_json': str(c.get('genre_mapping_json', '') or ''),
        'genre_remove_list': str(c.get('genre_remove_list', '') or ''),
        'add_hant_title': bool(c.get('add_hant_title', True)),
        'strm_delay': int(c.get('strm_delay', 3) or 3),
        'enable_episode_fix': bool(c.get('enable_episode_fix', True)),
        'enable_delete_episode_genre': bool(c.get('enable_delete_episode_genre', False)),
        'enable_genre_mapper': bool(c.get('enable_genre_mapper', False)),
        'enable_season_renamer': bool(c.get('enable_season_renamer', False)),
        'enable_country_scraper': bool(c.get('enable_country_scraper', False)),
        'enable_alt_renamer': bool(c.get('enable_alt_renamer', False)),
        'enable_strm_mediainfo': bool(c.get('enable_strm_mediainfo', False)),
        'enable_damaged_check': bool(c.get('enable_damaged_check', False)),
        'enable_category_covers': bool(c.get('enable_category_covers', False)),
        'category_cover_types': str(c.get('category_cover_types', 'genre,tag') or 'genre,tag'),
        'enable_auto_schedule': bool(c.get('enable_auto_schedule', False)),
        'schedule_cron': str(c.get('schedule_cron', '0 3 * * *') or '0 3 * * *'),
        'schedule_functions': list(c.get('schedule_functions', []) or []),
    }


def _base_url(server: str) -> str:
    return server.rstrip('/')


def _server_candidates(cfg: Dict[str, Any]) -> List[str]:
    """Return the configured endpoint and a same-host HTTPS fallback."""
    values = [cfg.get('_active_server', ''), cfg.get('emby_server', '')]
    result: List[str] = []
    for value in values:
        base = _base_url(str(value or '').strip())
        if base and base not in result:
            result.append(base)
            parsed = urlsplit(base)
            if parsed.scheme == 'http' and parsed.netloc:
                https_base = urlunsplit(('https', parsed.netloc, parsed.path, '', '')).rstrip('/')
                if https_base not in result:
                    result.append(https_base)
    return result


def _headers(api_key: str) -> Dict[str, str]:
    return {'X-Emby-Token': api_key, 'Accept': 'application/json'}


def _post_headers(api_key: str) -> Dict[str, str]:
    return {'X-Emby-Token': api_key, 'Accept': 'application/json', 'Content-Type': 'application/json'}


def _validate_basic(cfg: Dict[str, Any], need_tmdb: bool = False) -> Tuple[bool, str]:
    if not cfg['emby_server']:
        return False, '未配置 Emby 地址'
    if not cfg['api_key']:
        return False, '未配置 Emby API Key'
    if need_tmdb and not cfg['tmdb_key']:
        return False, '该功能需要 TMDB API Key'
    return True, 'ok'


def _parse_libs(raw: str) -> List[str]:
    libs = []
    for part in str(raw or '').replace('\n', ',').split(','):
        part = part.strip()
        if part:
            libs.append(part)
    return libs


def _parse_genre_mapping(raw: str) -> Dict[str, Dict[str, Any]]:
    if not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
        out = {}
        for k, v in obj.items():
            if isinstance(v, dict):
                out[str(k).strip()] = v
            else:
                out[str(k).strip()] = {'Name': str(v).strip()}
        return out
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        raise ValueError(f'Genre 映射 JSON 格式错误：{e}')


def _parse_remove_list(raw: str) -> List[str]:
    return [x.strip() for x in str(raw or '').splitlines() if x.strip()]


def _items_from_response(response, *, endpoint: str, ctx=None) -> List[Dict[str, Any]]:
    """读取 Emby 列表响应，兼容空正文/反代错误页。"""
    try:
        response.raise_for_status()
        payload = response.json()
    except Exception:
        if ctx:
            status = getattr(response, 'status_code', '?')
            body = ''
            content = getattr(response, 'content', b'') or b''
            if isinstance(content, bytes):
                body = content.decode('utf-8', errors='replace')
            if not body:
                body = str(getattr(response, 'text', '') or '')
            body = re.sub(r'\s+', ' ', body).strip()[:160]
            detail = f'：{body}' if body else ''
            ctx.log.warning(
                f'[emby_toolbox] {endpoint} 请求失败（HTTP {status}），已跳过{detail}'
            )
        return []
    if isinstance(payload, dict) and isinstance(payload.get('Items'), list):
        return [x for x in payload['Items'] if isinstance(x, dict)]
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def _get_first_user_id(cfg: Dict[str, Any]) -> str:
    try:
        url = f"{_base_url(cfg['emby_server'])}/emby/Users"
        r = requests.get(url, params={'api_key': cfg['api_key']}, headers=_headers(cfg['api_key']), timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            uid = data[0].get('Id')
            if uid:
                return str(uid)
        raise RuntimeError('无法自动获取 Emby 用户 ID')
    except requests.RequestException as e:
        raise RuntimeError(f'连接 Emby 失败：{e}')


def _resolve_user_id(cfg: Dict[str, Any]) -> str:
    return cfg['user_id'] or _get_first_user_id(cfg)


def _get_user_item(cfg: Dict[str, Any], user_id: str, item_id: str, base: str = '') -> Dict[str, Any]:
    url = f"{_base_url(base or cfg['emby_server'])}/emby/Users/{user_id}/Items/{item_id}"
    r = requests.get(url, params={'api_key': cfg['api_key']}, headers=_headers(cfg['api_key']), timeout=30)
    r.raise_for_status()
    return r.json()


def _get_system_item(cfg: Dict[str, Any], item_id: str, user_id: str = "") -> Dict[str, Any]:
    """读取最新元数据，优先管理员接口并兼容仅开放用户接口的服务器。"""
    last_404: Optional[Exception] = None
    for base in _server_candidates(cfg):
        url = f"{base}/emby/Items/{item_id}"
        try:
            r = requests.get(url, params={'api_key': cfg['api_key']}, headers=_headers(cfg['api_key']), timeout=30)
            r.raise_for_status()
            cfg['_active_server'] = base
            return r.json()
        except requests.HTTPError as exc:
            if getattr(exc.response, 'status_code', None) == 404:
                last_404 = exc
                # Some Emby gateways expose the item collection endpoint but
                # not GET /Items/{id}.  Querying by Id returns the same
                # administrator metadata and is suitable for write
                # verification, unlike the user-scoped endpoint.
                collection_url = f"{base}/emby/Items"
                collection = requests.get(
                    collection_url,
                    params={'Ids': item_id, 'api_key': cfg['api_key'], 'Fields': 'Genres,GenreItems,Tags,SortName,SeasonName,Name'},
                    headers=_headers(cfg['api_key']),
                    timeout=30,
                )
                try:
                    collection.raise_for_status()
                    payload = collection.json()
                except (requests.HTTPError, ValueError, TypeError):
                    payload = None
                if isinstance(payload, dict) and isinstance(payload.get('Items'), list) and payload['Items']:
                    cfg['_active_server'] = base
                    return payload['Items'][0]
                continue
            raise
    # Some gateways expose only the user-scoped GET route. This is a read
    # fallback only; metadata writes never use that endpoint.
    fallback_user = str(user_id or cfg.get('user_id') or _resolve_user_id(cfg)).strip()
    if fallback_user:
        try:
            return _get_user_item(cfg, fallback_user, item_id)
        except requests.HTTPError:
            if last_404:
                raise last_404
            raise
    if last_404:
        raise last_404
    raise RuntimeError(f'无法读取 Emby 条目：{item_id}')


def _update_item(cfg: Dict[str, Any], item: Dict[str, Any]) -> None:
    item_id = str(item['Id'])
    # reqformat=json is required by some Emby versions/reverse proxies.  Keep
    # the token in both header and query for compatibility with older servers.
    params = {'api_key': cfg['api_key'], 'reqformat': 'json'}
    last_error: Optional[Exception] = None
    candidates = _server_candidates(cfg)
    for base in candidates:
        url = f"{base}/emby/Items/{item_id}"
        try:
            r = requests.post(url, params=params, headers=_post_headers(cfg['api_key']), json=item, timeout=60)
            r.raise_for_status()
            cfg['_active_server'] = base
            return
        except requests.HTTPError as exc:
            status = getattr(exc.response, 'status_code', None)
            body = str(getattr(exc.response, 'text', '') or '').casefold()
            if status in (400, 422) and 'source' in body:
                # Library scans intentionally request a small field set.  A
                # few Emby builds require the complete MediaSources/Path
                # payload for metadata writes; fetch the administrator item
                # through the same endpoint and merge only the requested
                # changes before retrying.
                user_id = str(cfg.get('user_id') or _resolve_user_id(cfg)).strip()
                full = _get_user_item(cfg, user_id, item_id, base)
                complete = dict(full)
                complete.update(item)
                retry = requests.post(url, params=params, headers=_post_headers(cfg['api_key']), json=complete, timeout=60)
                retry.raise_for_status()
                cfg['_active_server'] = base
                return
            # A gateway may expose reads but not administrator writes.  Do not
            # POST metadata through /Users/... (that endpoint is user state
            # only); surface the real write failure to the caller.
            if status in (404, 405):
                last_error = exc
                continue
            raise
    if last_error:
        raise RuntimeError(
            f'Emby 媒体更新接口不可用（已尝试 {len(candidates)} 个地址）；'
            '请检查当前 Emby 地址的 /emby/Items/{id} 写入路由'
        ) from last_error
    raise RuntimeError('未配置可用的 Emby 地址')


def _update_item_verified(
    cfg: Dict[str, Any],
    item: Dict[str, Any],
    expected: Dict[str, Any],
    user_id: str,
    *,
    unordered: Tuple[str, ...] = (),
) -> bool:
    """写入条目后回读确认，避免把 HTTP 200 当成“已生效”。

    Emby 的更新接口返回空响应，即使字段被服务器规范化、忽略或权限拦截，
    POST 仍可能是 200。维护任务必须以回读结果计数，尤其是 Genres/Tags 这类
    会被服务器重新建立关联实体的字段。
    """
    _update_item(cfg, item)
    verify = _get_system_item(cfg, str(item['Id']), user_id)
    for key, wanted in expected.items():
        got = verify.get(key)
        if key in unordered:
            got = {str(x).strip().casefold() for x in (got or []) if str(x).strip()}
            wanted = {str(x).strip().casefold() for x in (wanted or []) if str(x).strip()}
        elif key == 'GenreItems':
            got = {str(x.get('Name') or '').strip().casefold() for x in (got or []) if isinstance(x, dict) and str(x.get('Name') or '').strip()}
            wanted = {str(x.get('Name') or '').strip().casefold() for x in (wanted or []) if isinstance(x, dict) and str(x.get('Name') or '').strip()}
        elif isinstance(wanted, list):
            got = [str(x).strip() for x in (got or []) if str(x).strip()]
            wanted = [str(x).strip() for x in wanted if str(x).strip()]
        if got != wanted:
            return False
    return True


def _get_recursive_items(
    cfg: Dict[str, Any],
    parent_id: str,
    *,
    include_item_types: str,
    fields: str,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """分页读取一个媒体库下的指定类型，避免季→集 N+1 查询。"""
    url = f"{_base_url(cfg['emby_server'])}/emby/Items"
    result: List[Dict[str, Any]] = []
    seen_ids = set()
    start = 0
    while True:
        params = {
            'ParentId': str(parent_id), 'api_key': cfg['api_key'],
            'Recursive': 'true', 'IncludeItemTypes': include_item_types,
            'Fields': fields, 'StartIndex': start, 'Limit': limit,
            'SortBy': 'SortName', 'SortOrder': 'Ascending',
        }
        response = requests.get(url, headers=_headers(cfg['api_key']), params=params, timeout=60)
        response.raise_for_status()
        payload = response.json() if response.content else {}
        page = payload.get('Items', []) if isinstance(payload, dict) else []
        page = [x for x in page if isinstance(x, dict) and x.get('Id')]
        fresh = [x for x in page if str(x['Id']) not in seen_ids]
        if not fresh:
            break
        result.extend(fresh)
        seen_ids.update(str(x['Id']) for x in fresh)
        total = int(payload.get('TotalRecordCount') or 0) if isinstance(payload, dict) else 0
        if not page or len(page) < limit or (total and len(result) >= total):
            break
        start += len(page)
    return result


def _refresh_item(cfg: Dict[str, Any], item_id: str) -> None:
    url = f"{_base_url(cfg['emby_server'])}/emby/Items/{item_id}/Refresh"
    params = {
        'api_key': cfg['api_key'],
        'Recursive': 'false',
        'MetadataRefreshMode': 'FullRefresh',
        'ImageRefreshMode': 'Default',
        'ReplaceAllMetadata': 'false',
        'ReplaceAllImages': 'false',
    }
    r = requests.post(url, params=params, timeout=30)
    r.raise_for_status()


def _get_libraries(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return Emby virtual folders (the canonical media-library endpoint).

    ``/Users/{id}/Views`` is user-specific and may omit libraries for limited
    users or return collection views.  The original emby_scripts client uses
    ``/Library/VirtualFolders``; use it first and retain a Views fallback for
    older installations that disable the endpoint.
    """
    base = _base_url(cfg['emby_server'])
    headers = _headers(cfg['api_key'])
    params = {'api_key': cfg['api_key']}
    url = f"{base}/emby/Library/VirtualFolders"
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get('Items'), list):
            return data['Items']
    except requests.RequestException:
        # Fall through to the user Views endpoint for legacy/proxied servers.
        pass
    user_id = _resolve_user_id(cfg)
    r = requests.get(f"{base}/emby/Users/{user_id}/Views", params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get('Items', []) if isinstance(data, dict) else []


def _get_library_id(cfg: Dict[str, Any], lib_name: str) -> Optional[str]:
    for item in _get_libraries(cfg):
        if item.get('Name') == lib_name:
            # VirtualFolders returns ``ItemId``; the Views fallback returns
            # ``Id``.  Accept both so library matching works on every Emby
            # version and through reverse proxies.
            value = item.get('ItemId') or item.get('Id')
            return str(value) if value else None
    return None


def _get_lib_items(cfg: Dict[str, Any], parent_id: str) -> List[Dict[str, Any]]:
    """Collect all non-folder items below a library with bounded pagination.

    The old implementation walked every folder with a separate request.  A
    large movie library can contain thousands of folders, turning a single
    maintenance run into hours of serial network calls.  Emby's recursive
    Items endpoint returns the same hierarchy in pages, so use it first and
    retain a small non-recursive fallback for old reverse proxies.
    """
    url = f"{_base_url(cfg['emby_server'])}/emby/Items"
    fields = (
        'ProviderIds,SortName,Tags,TagItems,Genres,GenreItems,LockedFields,'
        'Name,Type,Path,ParentIndexNumber,IndexNumber,SeriesName,SeasonName,'
        'Overview,ProductionYear,PremiereDate,MediaStreams,LocationType'
    )

    def legacy_walk(first_page: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Fallback for proxies/old Emby versions without recursive paging."""
        pending = [str(parent_id)]
        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        first = first_page
        while pending:
            current = pending.pop(0)
            if not current or current in seen:
                continue
            seen.add(current)
            if first is not None and current == str(parent_id):
                items = first
                first = None
            else:
                params = {
                    'api_key': cfg['api_key'],
                    'ParentId': current,
                    'Recursive': 'false',
                    'Fields': fields,
                    'SortBy': 'SortName',
                    'SortOrder': 'Ascending',
                }
                r = requests.get(url, params=params, headers=_headers(cfg['api_key']), timeout=60)
                r.raise_for_status()
                data = r.json()
                items = data.get('Items', []) if isinstance(data, dict) else []
            for item in items:
                if not isinstance(item, dict) or not item.get('Id'):
                    continue
                if item.get('Type') == 'Folder':
                    pending.append(str(item['Id']))
                else:
                    result.append(item)
        return result

    # Emby returns folders and media together for Recursive=true.  Keep the
    # page size conservative because metadata fields (especially MediaStreams)
    # make each response sizeable.
    limit = 500
    start = 0
    result: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    probe_page: Optional[List[Dict[str, Any]]] = None
    # Keep a lightweight non-recursive probe for older Emby proxies and for
    # already-cached root media.  The real work still uses recursive pages.
    try:
        probe_params = {
            'api_key': cfg['api_key'],
            'ParentId': str(parent_id),
            'Recursive': 'false',
            'Fields': fields,
            'SortBy': 'SortName',
            'SortOrder': 'Ascending',
        }
        probe_response = requests.get(
            url, params=probe_params, headers=_headers(cfg['api_key']), timeout=60,
        )
        probe_response.raise_for_status()
        probe_data = probe_response.json()
        raw_probe = probe_data.get('Items', []) if isinstance(probe_data, dict) else []
        if isinstance(raw_probe, list):
            probe_page = raw_probe
            for item in probe_page:
                if not isinstance(item, dict) or not item.get('Id') or item.get('Type') == 'Folder':
                    continue
                item_id = str(item['Id'])
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    result.append(item)
    except (requests.RequestException, ValueError, TypeError):
        probe_page = None
    try:
        while True:
            params = {
                'api_key': cfg['api_key'],
                'ParentId': str(parent_id),
                'Recursive': 'true',
                'Fields': fields,
                'SortBy': 'SortName',
                'SortOrder': 'Ascending',
                'StartIndex': start,
                'Limit': limit,
            }
            r = requests.get(url, params=params, headers=_headers(cfg['api_key']), timeout=60)
            r.raise_for_status()
            data = r.json()
            page = data.get('Items', []) if isinstance(data, dict) else []
            if not isinstance(page, list):
                raise ValueError('递归条目响应格式不正确')
            for item in page:
                if not isinstance(item, dict) or not item.get('Id') or item.get('Type') == 'Folder':
                    continue
                item_id = str(item['Id'])
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    result.append(item)
            total = int(data.get('TotalRecordCount') or 0) if isinstance(data, dict) else 0
            if not page or (len(page) < limit and total == 0 and any(
                isinstance(item, dict) and item.get('Type') == 'Folder' for item in page
            )):
                # Older proxies may ignore Recursive=true and return only the
                # immediate children without a total count.  Seed the legacy
                # walk with this page so already-fetched media is not lost.
                if page and total == 0 and any(
                    isinstance(item, dict) and item.get('Type') == 'Folder' for item in page
                ):
                    return legacy_walk(probe_page or page)
                return result
            if len(page) < limit or (total and start + len(page) >= total):
                return result
            start += len(page)
    except (requests.HTTPError, ValueError, KeyError, TypeError):
        # Only fall back after the recursive request is rejected or malformed;
        # ordinary network errors should remain visible to the caller.
        if probe_page and any(
            isinstance(item, dict) and item.get('Type') == 'Folder' for item in probe_page
        ):
            return legacy_walk(probe_page)
        if result:
            return result
        return legacy_walk()


def _tmdb_fetch(cfg: Dict[str, Any], tmdb_id: str, is_movie: bool) -> Optional[Dict[str, Any]]:
    media_type = 'movie' if is_movie else 'tv'
    url = f'https://api.themoviedb.org/3/{media_type}/{tmdb_id}'
    params = {
        'api_key': cfg['tmdb_key'],
        'language': 'zh-CN',
        'append_to_response': 'alternative_titles',
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        # 再取繁中备选
        if not is_movie:
            try:
                r2 = requests.get(url, params={'api_key': cfg['tmdb_key'], 'language': 'zh-TW'}, timeout=10)
                if r2.status_code == 200:
                    d2 = r2.json()
                    name = (d2.get('name') or '').strip()
                    if name and name != data.get('name'):
                        data['hant_trans'] = [name]
            except Exception:
                pass
        return data
    except (requests.RequestException, requests.Timeout, ConnectionError) as e:
        # 网络错误静默返回 None，由调用方处理
        return None


def _invalid_alt_name(name: str) -> bool:
    if not name:
        return True
    if any(ch in name for ch in INVALID_ALT_CHARS):
        return True
    if NON_TARGET_LANG_REGEX.search(name):
        return True
    return False


def _set_last_summary(ctx, summary: str):
    try:
        ctx.update_config({'last_summary': summary})
    except Exception:
        pass


def _episode_collect(cfg: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    url = f"{_base_url(cfg['emby_server'])}/emby/Items"
    params = {
        'api_key': cfg['api_key'],
        'Recursive': 'true',
        'IncludeItemTypes': 'Episode',
        'Fields': EP_FIELDS,
    }
    r = requests.get(url, params=params, headers=_headers(cfg['api_key']), timeout=120)
    r.raise_for_status()
    items = r.json().get('Items', [])
    checked = 0
    mismatches = []
    for item in items:
        path = item.get('Path') or ''
        if not path:
            continue
        m = EP_REGEX.search(os.path.basename(path))
        if not m:
            continue
        checked += 1
        fs, fe = int(m.group(1)), int(m.group(2))
        es, ee = item.get('ParentIndexNumber'), item.get('IndexNumber')
        if es != fs or ee != fe:
            mismatches.append({
                'id': item.get('Id'),
                'series': item.get('SeriesName') or item.get('Name') or '未知剧集',
                'name': item.get('Name') or '',
                'path': path,
                'file_season': fs,
                'file_episode': fe,
                'emby_season': es,
                'emby_episode': ee,
            })
    return mismatches, checked


def _episode_summary(mismatches: List[Dict[str, Any]], checked: int, max_output: int) -> str:
    lines = [f'共检查到 {checked} 个带 SxxExx 标记的文件。', f'发现不匹配 {len(mismatches)} 个。']
    if not mismatches:
        lines.append('🎉 所有带 SxxExx 标记的文件与 Emby 识别完全一致！')
        return '\n'.join(lines)
    lines.append('')
    lines.append('前几条不匹配如下：')
    for row in mismatches[:max_output]:
        lines.append(f"- {row['series']}｜文件名 S{row['file_season']:02d}E{row['file_episode']}｜Emby S{row['emby_season']}E{row['emby_episode']}")
    if len(mismatches) > max_output:
        lines.append(f'……其余 {len(mismatches)-max_output} 条请看日志')
    return '\n'.join(lines)


def _episode_fix(cfg: Dict[str, Any], ctx=None) -> str:
    user_id = _resolve_user_id(cfg)
    mismatches, checked = _episode_collect(cfg)
    if not mismatches:
        return f'共检查到 {checked} 个带 SxxExx 标记的文件，当前没有不匹配项。'
    ok_count = 0
    fail_count = 0
    total = len(mismatches)
    for idx, row in enumerate(mismatches, 1):
        if ctx:
            ctx.log.info(f'[emby_toolbox] 修复进度 {idx}/{total}: {row["series"]}')
        try:
            item = _get_user_item(cfg, user_id, str(row['id']))
            item['ParentIndexNumber'] = row['file_season']
            item['IndexNumber'] = row['file_episode']
            if cfg['fix_lock_data']:
                item['LockData'] = True
            _update_item(cfg, item)
            verify = _get_user_item(cfg, user_id, str(row['id']))
            if verify.get('ParentIndexNumber') == row['file_season'] and verify.get('IndexNumber') == row['file_episode']:
                ok_count += 1
            else:
                fail_count += 1
        except Exception as e:
            if ctx:
                ctx.log.error(f'[emby_toolbox] 修复失败 {row["series"]}: {e}')
            fail_count += 1
    result = f'扫描到 {len(mismatches)} 条不匹配，已尝试按文件名修复。成功 {ok_count} 条，失败 {fail_count} 条。'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _delete_episode_genre(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    count = 0
    failed = 0
    scanned = 0
    candidates: List[Tuple[Dict[str, Any], str]] = []
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始删除单集 Genre，媒体库: {libs}')
    user_id = _resolve_user_id(cfg)
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        # 旧实现先读取每个剧集、每一季，再逐季读取单集，产生数千次串行请求。
        # Emby 支持按媒体库递归查询 Episode，一次分页拿到全部候选。
        episodes = _get_recursive_items(
            cfg, parent_id, include_item_types='Episode',
            fields='Genres,GenreItems,Name,SeriesName,LockedFields',
        )
        scanned += len(episodes)
        candidates.extend((episode, lib) for episode in episodes
                          if episode.get('Genres') or episode.get('GenreItems'))
        if ctx:
            ctx.log.info(
                f'[emby_toolbox] 处理媒体库 {lib}，扫描 {len(episodes)} 个单集，'
                f'待清理 {sum(1 for e in episodes if e.get("Genres") or e.get("GenreItems"))} 个'
            )

    def clear_one(pair: Tuple[Dict[str, Any], str]) -> Tuple[bool, str, str]:
        ep, lib = pair
        try:
            item = _get_user_item(cfg, user_id, str(ep['Id']))
            if not item.get('Genres') and not item.get('GenreItems'):
                return False, 'unchanged', str(ep['Id'])
            item['Genres'] = []
            # GenreItems 为服务端维护字段，不放入更新 DTO；清空 Genres 后由
            # Emby 自动移除对应关联，避免旧 ID 让英文 Genre 被重新挂回。
            item.pop('GenreItems', None)
            if cfg['fix_lock_data']:
                locked = item.get('LockedFields') or []
                if 'Genres' not in locked:
                    locked.append('Genres')
                item['LockedFields'] = locked
                item['LockData'] = True
            ok = _update_item_verified(
                cfg, item, {'Genres': []}, user_id, unordered=('Genres',)
            )
            return ok, 'updated' if ok else 'verify_failed', f'{lib}/{item.get("SeriesName") or item.get("Name") or ep["Id"]}'
        except Exception as exc:
            return False, f'failed:{exc}', f'{lib}/{ep.get("SeriesName") or ep.get("Name") or ep["Id"]}'

    # Emby 单条更新仍需逐项提交，但并行处理可避免一个条目阻塞整个媒体库。
    completed = 0
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix='emby-episode-genre') as pool:
        futures = [pool.submit(clear_one, pair) for pair in candidates]
        for future in as_completed(futures):
            ok, state, name = future.result()
            completed += 1
            if ok:
                count += 1
            elif state.startswith('failed:') or state == 'verify_failed':
                failed += 1
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 单集 Genre 清理失败 {name}: {state}')
            if ctx and completed % 50 == 0:
                ctx.log.info(f'[emby_toolbox] 单集 Genre 清理进度: {completed}/{len(candidates)}（已确认 {count}）')
    result = f'单集 Genre 清理完成：扫描 {scanned} 条，确认更新 {count} 条，失败 {failed} 条。'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _genre_mapper(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    # 内置常见英文 Genre 映射；用户 JSON 优先覆盖同名项。
    mapping: Dict[str, Dict[str, Any]] = {
        key.casefold(): {'Name': value} for key, value in DEFAULT_GENRE_MAPPING.items()
    }
    custom_mapping = _parse_genre_mapping(cfg['genre_mapping_json'])
    mapping.update({str(key).strip().casefold(): value for key, value in custom_mapping.items()})
    remove_list = _parse_remove_list(cfg['genre_remove_list'])
    remove_keys = {x.casefold() for x in remove_list}
    count = 0
    mapped_count = 0
    removed_count = 0
    chinese_skip = 0
    failed_count = 0
    scanned_count = 0
    user_id = _resolve_user_id(cfg)
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始 Genre 映射，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        lib_scanned = 0
        if ctx:
            ctx.log.info(f'[emby_toolbox] 处理媒体库 {lib}，共 {len(items)} 个条目')
        for item0 in items:
            scanned_count += 1
            lib_scanned += 1
            # _get_lib_items 已请求 Genre/GenreItems；先在批量结果中筛选，
            # 只有命中映射或删除规则的条目才读取完整详情，避免每个条目
            # 都额外发起一次 GET。
            raw_genres = item0.get('Genres', [])
            genres = [g.strip() for g in raw_genres if isinstance(g, str) and g.strip()]
            genre_items = [g for g in (item0.get('GenreItems', []) or []) if isinstance(g, dict)]
            need = any(g.casefold() in mapping or g.casefold() in remove_keys for g in genres) or any((g.get('Name') or '').strip().casefold() in mapping for g in genre_items)
            if not need:
                if ctx and lib_scanned % 50 == 0:
                    ctx.log.info(f'[emby_toolbox] Genre 扫描进度: {lib_scanned}/{len(items)}（累计扫描 {scanned_count}，已确认更新 {count}）')
                continue
            # 候选条目读取完整 DTO；批量列表只用于筛选，直接把精简列表 DTO
            # POST 回去会让部分 Emby 版本忽略 Genre 或清空未返回的元数据。
            try:
                item = _get_user_item(cfg, user_id, str(item0['Id']))
            except Exception as exc:
                failed_count += 1
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] Genre 中文化读取失败: {item0.get("Name", "未知")}: {exc}')
                continue
            # 详情接口可能返回比批量接口更完整的 GenreItems。
            raw_genres = item.get('Genres', raw_genres)
            genres = [g.strip() for g in raw_genres if isinstance(g, str) and g.strip()]
            genre_items = [g for g in (item.get('GenreItems', genre_items) or []) if isinstance(g, dict)]
            new_genres = []
            item_changed = False
            original_genres = list(genres)
            for genre in genres:
                key = genre.casefold()
                if key in remove_keys:
                    removed_count += 1
                    item_changed = True
                    continue
                target = mapping.get(key)
                if target and target.get('Name') and target['Name'] != genre:
                    new_name = str(target['Name']).strip()
                    if new_name and new_name != genre:
                        if any('\u4e00' <= ch <= '\u9fff' for ch in genre):
                            chinese_skip += 1
                        else:
                            genre = new_name
                            mapped_count += 1
                            item_changed = True
                if genre and genre not in new_genres:
                    new_genres.append(genre)
            # GenreItems 的 Id 属于旧英文实体。只改 Name、继续保留旧 Id 时，
            # Emby 会在保存/刷新时按 Id 重新归一化成英文，造成日志“更新”但界面
            # 仍是英文。按最终 Genres 重建名称关联；自定义映射提供 Id 时才使用。
            new_genre_items = []
            target_ids = {
                str(mapping[g.casefold()].get('Name')).strip(): mapping[g.casefold()].get('Id')
                for g in original_genres if g.casefold() in mapping and mapping[g.casefold()].get('Name')
            }
            for name in new_genres:
                row = {'Name': name}
                if target_ids.get(name) is not None:
                    row['Id'] = target_ids[name]
                new_genre_items.append(row)
            if new_genre_items != genre_items:
                item_changed = True
            if not item_changed and new_genres == genres:
                continue
            item['Genres'] = new_genres
            # GenreItems 是服务端维护的关联字段，并非 ItemUpdateDto 的可写字段。
            # 发送旧 ID 或无 ID 的关联对象会让部分 Emby 版本静默忽略整个 Genre
            # 更新；只提交官方支持的 Genres 字段，服务端会重建关联实体。
            item.pop('GenreItems', None)
            if cfg['fix_lock_data']:
                locked = item.get('LockedFields') or []
                if 'Genres' not in locked:
                    locked.append('Genres')
                item['LockedFields'] = locked
                item['LockData'] = True
            try:
                confirmed = _update_item_verified(
                    cfg, item, {'Genres': new_genres}, user_id,
                    unordered=('Genres',)
                )
            except Exception as exc:
                confirmed = False
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] Genre 中文化写入失败: {item0.get("Name", "未知")}: {exc}')
            if confirmed:
                count += 1
                if ctx:
                    ctx.log.info(f'[emby_toolbox] Genre 中文化已确认: {item0.get("Name", "未知")} -> {", ".join(new_genres) or "（已清空）"}')
            else:
                failed_count += 1
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] Genre 中文化回读未生效: {item0.get("Name", "未知")}')
            if ctx and lib_scanned % 50 == 0:
                ctx.log.info(f'[emby_toolbox] Genre 扫描进度: {lib_scanned}/{len(items)}（累计扫描 {scanned_count}，已确认更新 {count}）')
    result = f'Genre 中文化/映射完成，共扫描 {scanned_count} 条，确认更新 {count} 条（映射 {mapped_count}，删除 {removed_count}）。'
    if failed_count:
        result += f' 失败/未生效 {failed_count} 条。'
    if chinese_skip:
        result += f' 已是中文跳过 {chinese_skip} 项。'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _season_renamer(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    user_id = _resolve_user_id(cfg)
    count = 0
    skip_tmdb = 0
    scanned = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始季名刮削，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        media_items = _get_lib_items(cfg, parent_id)
        series_list = [item for item in media_items if item.get('Type') == 'Series']
        skipped_non_series = len(media_items) - len(series_list)
        if ctx:
            ctx.log.info(
                f'[emby_toolbox] 处理媒体库 {lib}，共 {len(series_list)} 个剧集'
                f'（忽略电影/非剧集 {skipped_non_series} 个）'
            )
        for serie in series_list:
            provider = (serie.get('ProviderIds') or {}).get('Tmdb')
            if not provider:
                continue
            tmdb = _tmdb_fetch(cfg, str(provider), is_movie=False)
            if not tmdb or 'seasons' not in tmdb:
                if not tmdb:
                    skip_tmdb += 1
                    if ctx:
                        ctx.log.warning(f'[emby_toolbox] 季名刮削跳过 {serie.get("Name", "未知")}: TMDB 不可达')
                continue
            url = f"{_base_url(cfg['emby_server'])}/emby/Items"
            seasons_response = requests.get(
                url,
                headers=_headers(cfg['api_key']),
                params={
                    'ParentId': serie['Id'],
                    'api_key': cfg['api_key'],
                    'Recursive': 'false',
                    'IncludeItemTypes': 'Season',
                    'Fields': 'Name,IndexNumber,LockedFields',
                },
                timeout=60,
            )
            seasons = _items_from_response(
                seasons_response,
                endpoint=f'{lib}/{serie.get("Name", serie["Id"])} 季列表',
                ctx=ctx,
            )
            # 提前过滤：只处理未锁定的季
            unlocked_seasons = [s for s in seasons if 'Name' not in (s.get('LockedFields') or [])]
            if not unlocked_seasons:
                continue
            for season in unlocked_seasons:
                idx = season.get('IndexNumber')
                if idx is None:
                    continue
                tmdb_season = next((s for s in tmdb.get('seasons', []) if s.get('season_number') == idx), None)
                if not tmdb_season:
                    continue
                new_name = (tmdb_season.get('name') or '').strip()
                current_name = (season.get('Name') or '').strip()
                if not new_name or new_name == current_name:
                    continue
                full = _get_user_item(cfg, user_id, str(season['Id']))
                full['Name'] = new_name
                lf = full.get('LockedFields') or []
                if 'Name' not in lf:
                    lf.append('Name')
                full['LockedFields'] = lf
                if cfg['fix_lock_data']:
                    full['LockData'] = True
                try:
                    confirmed = _update_item_verified(cfg, full, {'Name': new_name}, user_id)
                except Exception as exc:
                    confirmed = False
                    if ctx:
                        ctx.log.warning(f'[emby_toolbox] 季名刮削写入失败 {serie.get("Name", "未知")} S{idx}: {exc}')
                if confirmed:
                    count += 1
                    if ctx:
                        ctx.log.info(f'[emby_toolbox] 季名刮削已确认: {serie.get("Name", "未知")} S{idx} -> {new_name}')
                elif ctx:
                    ctx.log.warning(f'[emby_toolbox] 季名刮削回读未生效: {serie.get("Name", "未知")} S{idx}')
    result = f'季名刮削完成，共更新 {count} 条。'
    if skip_tmdb > 0:
        result += f'（跳过 {skip_tmdb} 条 TMDB 不可达）'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _country_scraper(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    user_id = _resolve_user_id(cfg)
    count = 0
    skip_tmdb = 0
    scanned = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始国家/语言 Tag 刮削，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            scanned += 1
            provider = (item0.get('ProviderIds') or {}).get('Tmdb')
            if not provider:
                continue
            is_movie = item0.get('Type') == 'Movie'
            tmdb = _tmdb_fetch(cfg, str(provider), is_movie=is_movie)
            if not tmdb:
                skip_tmdb += 1
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 国家/语言标签跳过 {item0.get("Name", "未知")}: TMDB 不可达')
                continue
            prod = tmdb.get('production_countries', []) or []
            langs = tmdb.get('spoken_languages', []) or []
            if not prod and not langs:
                continue
            item = item0
            old_tags = [t['Name'].strip() for t in item.get('TagItems', []) if isinstance(t, dict) and t.get('Name') and t.get('Name').strip()]
            if not old_tags and item.get('Tags'):
                old_tags = [t.strip() for t in item.get('Tags') if isinstance(t, str) and t.strip()]
            existing = {t.lower() for t in old_tags}
            new_tags = list(old_tags)
            changed = False
            countries = []
            for c in prod:
                tag = COUNTRY_DICT.get(c.get('iso_3166_1'), DEFAULT_COUNTRY)
                if tag not in countries:
                    countries.append(tag)
            for c in countries:
                if c.lower() not in existing and (c != DEFAULT_COUNTRY or len(countries) <= 2):
                    new_tags.append(c)
                    existing.add(c.lower())
                    changed = True
            langs_out = []
            for l in langs:
                tag = LANGUAGE_DICT.get(l.get('iso_639_1'), DEFAULT_LANGUAGE)
                if tag not in langs_out:
                    langs_out.append(tag)
            for l in langs_out:
                if l.lower() not in existing and (l != DEFAULT_LANGUAGE or len(langs_out) <= 2):
                    new_tags.append(l)
                    existing.add(l.lower())
                    changed = True
            if not changed:
                continue
            item['Tags'] = new_tags
            item['TagItems'] = [{'Name': t} for t in new_tags]
            lf = item.get('LockedFields') or []
            if 'Tags' not in lf:
                lf.append('Tags')
            item['LockedFields'] = lf
            if cfg['fix_lock_data']:
                item['LockData'] = True
            try:
                confirmed = _update_item_verified(
                    cfg, item, {'Tags': new_tags}, user_id, unordered=('Tags',)
                )
            except Exception as exc:
                confirmed = False
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 国家/语言标签写入失败 {item0.get("Name", "未知")}: {exc}')
            if confirmed:
                count += 1
                if ctx:
                    ctx.log.info(f'[emby_toolbox] 国家/语言标签已确认: {item0.get("Name", "未知")} +{len(new_tags)} 标签')
            elif ctx:
                ctx.log.warning(f'[emby_toolbox] 国家/语言标签回读未生效: {item0.get("Name", "未知")}')
            if ctx and scanned % 50 == 0:
                ctx.log.info(f'[emby_toolbox] 国家/语言扫描进度: {scanned}/{len(items)}（已更新 {count}）')
    result = f'国家/语言 Tag 更新完成，共扫描 {scanned} 条，更新 {count} 条。'
    if skip_tmdb > 0:
        result += f'（跳过 {skip_tmdb} 条 TMDB 不可达）'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _alt_renamer(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    user_id = _resolve_user_id(cfg)
    count = 0
    skip_tmdb = 0
    scanned = 0
    skip_unchanged = 0
    skip_cached = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始别名写入，媒体库: {libs}')
    
    # 批量获取条目以减少 API 调用
    cache = _EMBY_STATE.setdefault(_ALT_CACHE_KEY, {})
    if not isinstance(cache, dict):
        cache = {}
        _EMBY_STATE[_ALT_CACHE_KEY] = cache
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            scanned += 1
            provider = (item0.get('ProviderIds') or {}).get('Tmdb')
            if not provider:
                continue
            is_movie = item0.get('Type') == 'Movie'
            item_key = str(item0.get('Id') or '')
            current_sort = str(item0.get('SortName') or '')
            cached = cache.get(item_key) if item_key else None
            if (isinstance(cached, dict)
                    and str(cached.get('provider')) == str(provider)
                    and bool(cached.get('add_hant_title')) == bool(cfg['add_hant_title'])
                    and str(cached.get('sort_name') or '') == current_sort):
                skip_cached += 1
                if ctx:
                    ctx.log.info(f'[emby_toolbox] 别名写入缓存命中，跳过: {item0.get("Name", item_key)}')
                continue
            tmdb = _tmdb_fetch(cfg, str(provider), is_movie=is_movie)
            if not tmdb:
                skip_tmdb += 1
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 别名写入跳过 {item0.get("Name", "未知")}: TMDB 不可达')
                continue
            titles = tmdb.get('alternative_titles', {})
            raw_alt = titles.get('titles' if is_movie else 'results', []) or []
            alt_names = [x.get('title') for x in raw_alt if x.get('iso_3166_1') == 'CN' and x.get('title')]
            if cfg['add_hant_title'] and tmdb.get('hant_trans'):
                alt_names.extend(tmdb['hant_trans'])
            if not alt_names:
                continue
            item = item0
            splitr = ' / '
            old_sort = item.get('SortName', '') or ''
            old_names = [n.strip() for n in old_sort.split(splitr) if n and n.strip()] if old_sort else []
            if not old_names and item.get('Name'):
                old_names = [str(item.get('Name')).strip()]
            existing = set(old_names)
            res = list(old_names)
            changed = False
            clean_alt = []
            for raw in alt_names:
                if raw:
                    clean_alt.extend([p.strip() for p in raw.replace('/', ' / ').split('/') if p and p.strip()])
            for name in clean_alt:
                if name and name not in existing and not _invalid_alt_name(name):
                    res.append(name)
                    existing.add(name)
                    changed = True
            sort_all = splitr.join(res)
            if not changed or sort_all == old_sort:
                skip_unchanged += 1
                continue
            if ctx:
                ctx.log.info(f'[emby_toolbox] 别名写入更新: {item0.get("Name", "未知")} -> {sort_all[:60]}...')
            item['SortName'] = sort_all
            item['ForcedSortName'] = sort_all
            lf = item.get('LockedFields') or []
            if 'SortName' not in lf:
                lf.append('SortName')
            item['LockedFields'] = lf
            if cfg['fix_lock_data']:
                item['LockData'] = True
            try:
                confirmed = _update_item_verified(
                    cfg, item, {'SortName': sort_all, 'ForcedSortName': sort_all}, user_id
                )
            except Exception as exc:
                confirmed = False
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 别名写入失败 {item0.get("Name", "未知")}: {exc}')
            if not confirmed:
                if ctx:
                    ctx.log.warning(f'[emby_toolbox] 别名写入回读未生效: {item0.get("Name", "未知")}')
                continue
            count += 1
            if item_key:
                cache[item_key] = {
                    'provider': str(provider),
                    'sort_name': sort_all,
                    'add_hant_title': bool(cfg['add_hant_title']),
                    'updated_at': time.time(),
                }
                if _EMBY_PERSIST:
                    try:
                        _EMBY_PERSIST(_ALT_CACHE_KEY, cache)
                    except Exception as exc:
                        if ctx:
                            ctx.log.warning(f'[emby_toolbox] 别名缓存写入失败: {exc}')
            if ctx and scanned % 50 == 0:
                ctx.log.info(f'[emby_toolbox] 别名扫描进度: {scanned}/{len(items)}（已更新 {count}，缓存跳过 {skip_cached}）')
    result = f'别名写入完成，共扫描 {scanned} 条，更新 {count} 条。'
    if skip_tmdb > 0:
        result += f'（跳过 {skip_tmdb} 条 TMDB 不可达）'
    if skip_unchanged > 0:
        result += f'（跳过 {skip_unchanged} 条已是最新）'
    if skip_cached > 0:
        result += f'（缓存命中跳过 {skip_cached} 条）'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _strm_mediainfo(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    user_id = _resolve_user_id(cfg)
    count = 0
    delay = cfg['strm_delay']
    scanned = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始 STRM MediaInfo 刷新，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            scanned += 1
            item_type = item0.get('Type')
            targets = []
            if item_type == 'Movie':
                targets = [item0]
            elif item_type == 'Series':
                url = f"{_base_url(cfg['emby_server'])}/emby/Items"
                seasons_response = requests.get(url, headers=_headers(cfg['api_key']), params={'ParentId': item0['Id'], 'api_key': cfg['api_key']}, timeout=60)
                seasons = _items_from_response(seasons_response, endpoint=f'{lib}/{item0.get("Name", item0["Id"])} 季列表', ctx=ctx)
                for season in seasons:
                    eps_response = requests.get(url, headers=_headers(cfg['api_key']), params={
                        'ParentId': season.get('Id'), 'api_key': cfg['api_key'], 'Fields': 'MediaStreams,LocationType', 'IncludeItemTypes': 'Episode', 'Recursive': 'true', 'SortBy': 'SortName', 'SortOrder': 'Ascending'
                    }, timeout=60)
                    targets.extend(_items_from_response(eps_response, endpoint=f'{lib}/{item0.get("Name", item0["Id"])} 单集列表', ctx=ctx))
            for target in targets:
                item_id = target.get('Id') if isinstance(target, dict) else target
                item = target if isinstance(target, dict) else _get_user_item(cfg, user_id, str(item_id))
                if item.get('LocationType') == 'Virtual':
                    continue
                media_streams = item.get('MediaStreams') or []
                if len(media_streams) != 0:
                    continue
                # PlaybackInfo is exposed without the legacy /emby prefix on
                # current Emby servers (same route used by emby_scripts).
                url = f"{_base_url(cfg['emby_server'])}/Items/{item_id}/PlaybackInfo"
                params = {
                    'AutoOpenLiveStream': 'true',
                    'IsPlayback': 'true',
                    'api_key': cfg['api_key'],
                    'UserId': user_id,
                }
                try:
                    r = requests.post(url, params=params, headers=_headers(cfg['api_key']), timeout=60)
                    if r.status_code in (200, 204):
                        count += 1
                    elif ctx:
                        ctx.log.warning(f'[emby_toolbox] STRM 刷新失败 {item_id}: HTTP {r.status_code}')
                except requests.RequestException as exc:
                    if ctx:
                        ctx.log.warning(f'[emby_toolbox] STRM 刷新异常 {item_id}: {exc}')
                if delay > 0:
                    time.sleep(delay)
    result = f'STRM MediaInfo 刷新完成，共扫描 {scanned} 个媒体条目，更新 {count} 条。'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _damaged_check(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    user_id = _resolve_user_id(cfg)
    damaged = []
    total = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始元数据缺失检查，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            total += 1
            item = item0
            has_overview = bool(item.get('Overview'))
            has_year = bool(item.get('ProductionYear'))
            has_premiere = bool(item.get('PremiereDate'))
            if not has_overview and not has_year and not has_premiere:
                damaged.append({'lib': lib, 'id': item0['Id'], 'name': item0.get('Name', '未知名称'), 'type': item.get('Type', 'Unknown')})
            if ctx and total % 100 == 0:
                ctx.log.info(f'[emby_toolbox] 元数据检查进度: {total} 条')
    lines = [f'总计扫描条目: {total} 个', f'受影响/缺少关键元数据条目: {len(damaged)} 个']
    if damaged:
        lines.append('前几条如下：')
        for row in damaged[:cfg['max_output']]:
            lines.append(f"- [{row['lib']}] 《{row['name']}》 | ItemId: {row['id']} | 类型: {row['type']}")
    else:
        lines.append('🎉 未检测到元数据缺失条目')
    return '\n'.join(lines)


def _category_types(raw: str) -> List[str]:
    """Normalize the cover scope while accepting the old singular labels."""
    value = str(raw or 'genre,tag').strip().casefold()
    if value in {'all', '*', '全部'}:
        return ['genre', 'tag']
    aliases = {'genres': 'genre', 'tags': 'tag', '流派': 'genre', '标签': 'tag'}
    result: List[str] = []
    for part in re.split(r'[,，\s]+', value):
        part = aliases.get(part.strip(), part.strip())
        if part in {'genre', 'tag'} and part not in result:
            result.append(part)
    return result or ['genre', 'tag']


def _get_category_items(cfg: Dict[str, Any], kind: str, ctx=None) -> List[Dict[str, Any]]:
    """Read Emby's Genre/Tag entities, preserving the configured reverse proxy."""
    endpoint = '/emby/Genres' if kind == 'genre' else '/emby/Tags'
    fields = 'Name,Type,ImageTags'
    last_error: Optional[Exception] = None
    for base in _server_candidates(cfg):
        result: List[Dict[str, Any]] = []
        seen = set()
        start = 0
        try:
            while True:
                params = {
                    'api_key': cfg['api_key'], 'Fields': fields,
                    'SortBy': 'SortName', 'SortOrder': 'Ascending',
                    'StartIndex': start, 'Limit': 1000,
                }
                response = requests.get(
                    f'{base}{endpoint}', params=params,
                    headers=_headers(cfg['api_key']), timeout=60,
                )
                response.raise_for_status()
                payload = response.json() if response.content else []
                page = payload if isinstance(payload, list) else payload.get('Items', []) if isinstance(payload, dict) else []
                page = [x for x in page if isinstance(x, dict) and x.get('Id') and x.get('Name')]
                fresh = [x for x in page if str(x['Id']) not in seen]
                result.extend(fresh)
                seen.update(str(x['Id']) for x in fresh)
                total = int(payload.get('TotalRecordCount') or 0) if isinstance(payload, dict) else 0
                if not page or len(page) < 1000 or (total and len(result) >= total):
                    break
                start += len(page)
            cfg['_active_server'] = base
            return result
        except (requests.RequestException, ValueError, TypeError) as exc:
            last_error = exc
            continue
    if last_error:
        raise RuntimeError(f'读取 {"Genre" if kind == "genre" else "Tag"} 列表失败：{last_error}') from last_error
    return []


def _upload_category_cover(cfg: Dict[str, Any], item: Dict[str, Any], kind: str, ctx=None) -> None:
    """Upload one deterministic PNG to Emby's Primary image endpoint."""
    item_id = str(item.get('Id') or '').strip()
    title = str(item.get('Name') or '').strip() or '未命名'
    if not item_id:
        raise ValueError('分类缺少 Id')
    payload = render_cover(title, kind)
    headers = {
        'X-Emby-Token': cfg['api_key'], 'Content-Type': 'image/png',
        'Accept': 'application/json',
    }
    last_error: Optional[Exception] = None
    for base in _server_candidates(cfg):
        # Most installations expose /emby; the second route handles older
        # reverse proxies that strip that prefix while keeping the same host.
        for path in (f'/emby/Items/{item_id}/Images/Primary', f'/Items/{item_id}/Images/Primary'):
            try:
                response = requests.post(
                    f'{base}{path}', params={'api_key': cfg['api_key']},
                    headers=headers, data=payload, timeout=60,
                )
                response.raise_for_status()
                cfg['_active_server'] = base
                return
            except requests.RequestException as exc:
                last_error = exc
                status = getattr(exc.response, 'status_code', None)
                if status not in (404, 405):
                    break
    if last_error:
        raise RuntimeError(f'上传分类封面失败（{title}）：{last_error}') from last_error
    raise RuntimeError(f'上传分类封面失败（{title}）')


def _category_covers(cfg: Dict[str, Any], ctx=None) -> str:
    """Generate and upload covers for all configured Genre/Tag entities."""
    kinds = _category_types(cfg.get('category_cover_types', 'genre,tag'))
    totals = {'genre': 0, 'tag': 0}
    uploaded = {'genre': 0, 'tag': 0}
    failed: List[str] = []
    if ctx:
        ctx.log.info('[emby_toolbox] 开始生成分类封面（模板渲染，不调用 AI）: %s', ', '.join(kinds))
    for kind in kinds:
        items = _get_category_items(cfg, kind, ctx)
        totals[kind] = len(items)
        for index, item in enumerate(items, 1):
            try:
                _upload_category_cover(cfg, item, kind, ctx)
                uploaded[kind] += 1
            except Exception as exc:
                failed.append(f'{kind}:{item.get("Name", "未知")}')
                if ctx:
                    ctx.log.warning('[emby_toolbox] 分类封面失败 %s/%s: %s', kind, item.get('Name', '未知'), exc)
            if ctx and (index % 20 == 0 or index == len(items)):
                ctx.log.info('[emby_toolbox] %s 封面进度 %s/%s', 'Genre' if kind == 'genre' else 'Tag', index, len(items))
    summary = (
        f'分类封面完成：Genre {uploaded["genre"]}/{totals["genre"]}，'
        f'Tag {uploaded["tag"]}/{totals["tag"]}'
    )
    if failed:
        summary += f'，失败 {len(failed)} 项（前 5 项：{", ".join(failed[:5])}）'
    if ctx:
        ctx.log.info('[emby_toolbox] %s', summary)
    return summary


async def _previous_setup(ctx):
    active_action_task = None

    def _cancel_active_action():
        nonlocal active_action_task
        if active_action_task is not None and not active_action_task.done():
            active_action_task.cancel()

    ctx.add_cleanup(_cancel_active_action)

    async def _start_action(label, worker, *, need_tmdb=False):
        """校验配置后将耗时维护操作放入后台线程。"""
        nonlocal active_action_task
        if active_action_task is not None and not active_action_task.done():
            return {'ok': False, 'message': '已有手动维护任务正在后台运行，请稍后再试。'}

        cfg = _cfg(ctx)
        ok, msg = _validate_basic(cfg, need_tmdb=need_tmdb)
        if not ok:
            return {'ok': False, 'message': msg}

        async def _run():
            nonlocal active_action_task
            ctx.log.info('[emby_toolbox] 手动任务开始: %s', label)
            try:
                summary = await asyncio.to_thread(worker, cfg)
                _set_last_summary(ctx, f'{label}\n{summary}')
                ctx.log.info('[emby_toolbox] 手动任务完成: %s: %s', label, summary)
            except asyncio.CancelledError:
                ctx.log.info('[emby_toolbox] 手动任务已取消: %s', label)
                raise
            except Exception as exc:
                summary = f'{label}失败：{exc}'
                _set_last_summary(ctx, summary)
                ctx.log.error('[emby_toolbox] %s', summary)
            finally:
                active_action_task = None

        active_action_task = ctx.create_task(
            _run(), name=f'Emby 工具箱：{label}'
        )
        return {
            'ok': True,
            'message': f'已在后台开始“{label}”，可在状态摘要或插件日志查看结果。',
        }

    # 定时任务
    if ctx.config.get('enable_auto_schedule', False):
        schedule_cron = ctx.config.get('schedule_cron', '0 3 * * *')
        schedule_funcs = ctx.config.get('schedule_functions', [])
        
        async def scheduled_task():
            ctx.log.info('[emby_toolbox] 定时任务开始执行')
            cfg = _cfg(ctx)
            results = []
            
            for func_name in schedule_funcs:
                try:
                    ctx.log.info(f'[emby_toolbox] 执行定时任务: {func_name}')
                    if func_name == 'episode_fix':
                        result = _episode_fix(cfg, ctx)
                    elif func_name == 'delete_episode_genre':
                        result = _delete_episode_genre(cfg, ctx)
                    elif func_name == 'genre_mapper':
                        result = _genre_mapper(cfg, ctx)
                    elif func_name == 'season_renamer':
                        result = _season_renamer(cfg, ctx)
                    elif func_name == 'country_scraper':
                        result = _country_scraper(cfg, ctx)
                    elif func_name == 'alt_renamer':
                        result = _alt_renamer(cfg, ctx)
                    elif func_name == 'strm_mediainfo':
                        result = _strm_mediainfo(cfg, ctx)
                    elif func_name == 'damaged_check':
                        result = _damaged_check(cfg, ctx)
                    elif func_name == 'category_covers':
                        result = _category_covers(cfg, ctx)
                    else:
                        result = f'未知功能: {func_name}'
                    results.append(f'{func_name}: {result}')
                    ctx.log.info(f'[emby_toolbox] {func_name} 完成: {result}')
                except Exception as e:
                    ctx.log.error(f'[emby_toolbox] {func_name} 失败: {e}')
                    results.append(f'{func_name}: 失败 - {e}')
            
            summary = '\n'.join(results)
            ctx.log.info(f'[emby_toolbox] 定时任务全部完成')
            _set_last_summary(ctx, f'定时任务完成\n{summary}')
            try:
                await ctx.notify(
                    {'任务': '定时维护', '状态': '完成', '结果': summary},
                    category='Emby工具箱',
                )
            except Exception:
                pass
        
        try:
            cron_parts = schedule_cron.split()
            if len(cron_parts) == 5:
                fields = dict(zip(('minute', 'hour', 'day', 'month', 'day_of_week'), cron_parts))
                ctx.schedule_cron('Emby 工具箱定时维护', scheduled_task, **fields)
                ctx.log.info(f'[emby_toolbox] 定时任务已启用: {schedule_cron}')
        except Exception as e:
            ctx.log.error(f'[emby_toolbox] 定时任务配置失败: {e}')

    @ctx.action('run_all_scheduled')
    async def action_run_all_scheduled():
        cfg = _cfg(ctx)
        ok, msg = _validate_basic(cfg)
        if not ok:
            return {'ok': False, 'message': msg}
        
        schedule_funcs = cfg.get('schedule_functions', [])
        if not schedule_funcs:
            return {'ok': False, 'message': '未配置定时执行功能'}
        
        ctx.log.info('[emby_toolbox] 手动执行所有定时功能')
        results = []
        for func_name in schedule_funcs:
            try:
                ctx.log.info(f'[emby_toolbox] 执行: {func_name}')
                if func_name == 'episode_fix':
                    result = _episode_fix(cfg, ctx)
                elif func_name == 'delete_episode_genre':
                    result = _delete_episode_genre(cfg, ctx)
                elif func_name == 'genre_mapper':
                    result = _genre_mapper(cfg, ctx)
                elif func_name == 'season_renamer':
                    result = _season_renamer(cfg, ctx)
                elif func_name == 'country_scraper':
                    result = _country_scraper(cfg, ctx)
                elif func_name == 'alt_renamer':
                    result = _alt_renamer(cfg, ctx)
                elif func_name == 'strm_mediainfo':
                    result = _strm_mediainfo(cfg, ctx)
                elif func_name == 'damaged_check':
                    result = _damaged_check(cfg, ctx)
                elif func_name == 'category_covers':
                    result = _category_covers(cfg, ctx)
                else:
                    result = f'未知功能: {func_name}'
                results.append(f'{func_name}: {result}')
            except Exception as e:
                ctx.log.error(f'[emby_toolbox] {func_name} 失败: {e}')
                results.append(f'{func_name}: 失败 - {e}')
        
        summary = '\n'.join(results)
        _set_last_summary(ctx, summary)
        return {'ok': True, 'message': summary}

    @ctx.action('test_connection')
    async def action_test_connection():
        cfg = _cfg(ctx)
        ok, msg = _validate_basic(cfg)
        if not ok:
            return {'ok': False, 'message': msg}
        try:
            def _test():
                user_id = _resolve_user_id(cfg)
                r = requests.get(f"{_base_url(cfg['emby_server'])}/emby/Users/{user_id}", headers=_headers(cfg['api_key']), params={'api_key': cfg['api_key']}, timeout=30)
                r.raise_for_status()
                return f'连接成功，用户 ID：{user_id}'
            summary = await asyncio.to_thread(_test)
            _set_last_summary(ctx, summary)
            return {'ok': True, 'message': summary}
        except Exception as e:
            return {'ok': False, 'message': f'连接失败：{e}'}

    @ctx.action('scan_episode_mismatch')
    async def action_scan_episode_mismatch():
        def _scan(cfg):
            mismatches, checked = _episode_collect(cfg)
            return _episode_summary(mismatches, checked, cfg['max_output'])
        return await _start_action('扫描剧集季集不匹配', _scan)

    @ctx.action('fix_episode_mismatch')
    async def action_fix_episode_mismatch():
        return await _start_action('按文件名修复剧集季集', lambda cfg: _episode_fix(cfg, ctx))

    @ctx.action('run_delete_episode_genre')
    async def action_delete_episode_genre():
        return await _start_action('删除单集 Genre', lambda cfg: _delete_episode_genre(cfg, ctx))

    @ctx.action('run_genre_mapper')
    async def action_genre_mapper():
        return await _start_action('执行 Genre 映射', lambda cfg: _genre_mapper(cfg, ctx))

    @ctx.action('run_season_renamer')
    async def action_season_renamer():
        return await _start_action('执行季名刮削', lambda cfg: _season_renamer(cfg, ctx), need_tmdb=True)

    @ctx.action('run_country_scraper')
    async def action_country_scraper():
        return await _start_action('执行国家/语言 Tag', lambda cfg: _country_scraper(cfg, ctx), need_tmdb=True)

    @ctx.action('run_alt_renamer')
    async def action_alt_renamer():
        return await _start_action('执行别名写入', lambda cfg: _alt_renamer(cfg, ctx), need_tmdb=True)

    @ctx.action('run_strm_mediainfo')
    async def action_strm_mediainfo():
        return await _start_action('执行 STRM MediaInfo 刷新', lambda cfg: _strm_mediainfo(cfg, ctx))

    @ctx.action('run_damaged_check')
    async def action_damaged_check():
        return await _start_action('执行元数据缺失检查', lambda cfg: _damaged_check(cfg, ctx))

    @ctx.action('run_category_covers')
    async def action_category_covers():
        return await _start_action('生成分类封面', lambda cfg: _category_covers(cfg, ctx))

async def _previous_teardown(ctx):
    ctx.log.info('[emby_toolbox] 插件已停用')


def _worker_for(key: str, cfg: Dict[str, Any], ctx):
    workers = {
        'episode_fix': lambda: _episode_fix(cfg, ctx),
        'delete_episode_genre': lambda: _delete_episode_genre(cfg, ctx),
        'genre_mapper': lambda: _genre_mapper(cfg, ctx),
        'season_renamer': lambda: _season_renamer(cfg, ctx),
        'country_scraper': lambda: _country_scraper(cfg, ctx),
        'alt_renamer': lambda: _alt_renamer(cfg, ctx),
        'strm_mediainfo': lambda: _strm_mediainfo(cfg, ctx),
        'damaged_check': lambda: _damaged_check(cfg, ctx),
        'category_covers': lambda: _category_covers(cfg, ctx),
        'scan_episode_mismatch': lambda: _episode_summary(*_episode_collect(cfg), cfg['max_output']),
    }
    if key not in workers:
        raise ValueError(f'未知功能：{key}')
    return workers[key]()


async def setup(ctx):
    """Vue 模式：配置交给前端，所有长任务由平台后台托管。"""
    global _EMBY_STATE, _EMBY_PERSIST
    active_task = None
    scheduled_jobs = []
    state = dict(await ctx.storage.items())
    _EMBY_STATE = state
    event_loop = asyncio.get_running_loop()
    pending_writes = set()
    def persist(key, value):
        state[key] = value
        # 别名 worker 在 asyncio.to_thread 中执行，跨线程写入必须提交回
        # 插件事件循环，不能直接调用 ctx.create_task。
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is event_loop:
            task = ctx.create_task(ctx.storage.set(key, value), name=f"emby-toolbox-storage:{key}")
        else:
            task = asyncio.run_coroutine_threadsafe(ctx.storage.set(key, value), event_loop)
        pending_writes.add(task); task.add_done_callback(pending_writes.discard)
    _EMBY_PERSIST = persist
    async def flush_state():
        if pending_writes:
            await asyncio.gather(*(asyncio.wrap_future(x) if not isinstance(x, asyncio.Future) else x for x in list(pending_writes)), return_exceptions=True)
    ctx.add_cleanup(flush_state)

    def _persist_history(row: Dict[str, Any]):
        _RECENT.appendleft(row)
        try:
            saved = list(state.get('run_history', []) or [])
            saved.insert(0, row)
            persist('run_history', saved[:30])
        except Exception:
            pass

    async def _execute(keys: List[str], source: str, label: str):
        nonlocal active_task
        cfg = _cfg(ctx)
        _RUNTIME.update(running=True, task=label, source=source, started_at=_now(),
                        finished_at='', last_result='', last_ok=None)
        results, success = [], True
        try:
            for key in keys:
                title = FEATURES.get(key, (key, '', False))[0] if key != 'scan_episode_mismatch' else '扫描剧集季集'
                need_tmdb = FEATURES.get(key, ('', '', False))[2]
                ok, message = _validate_basic(cfg, need_tmdb=need_tmdb)
                if not ok:
                    raise ValueError(message)
                ctx.log.info('[emby_toolbox] 开始：%s', title)
                try:
                    result = await asyncio.to_thread(_worker_for, key, cfg, ctx)
                    results.append(f'{title}\n{result}')
                except Exception as exc:
                    success = False
                    results.append(f'{title}\n失败：{exc}')
                    ctx.log.exception('[emby_toolbox] %s 失败', title)
            summary = '\n\n'.join(results) or '未执行任何功能'
            _set_last_summary(ctx, summary)
            _RUNTIME.update(last_result=summary, last_ok=success)
            _persist_history({'time': _now(), 'source': source, 'task': label,
                              'ok': success, 'summary': summary})
            if source == '定时':
                try:
                    rows = [{'项目': '任务', '内容': label}, {'项目': '状态', '内容': '完成'}]
                    for block in results:
                        parts = block.split('\n', 1)
                        rows.append({'项目': parts[0], '内容': parts[1] if len(parts) > 1 else ''})
                    await asyncio.wait_for(ctx.notify(rows, category='Emby工具箱'), timeout=30)
                except Exception:
                    ctx.log.warning('[emby_toolbox] 结果通知发送失败', exc_info=True)
        except asyncio.CancelledError:
            _RUNTIME.update(last_result='任务因插件停用或重载而取消', last_ok=False)
            raise
        except Exception as exc:
            success = False
            summary = f'{label}失败：{exc}'
            _RUNTIME.update(last_result=summary, last_ok=False)
            _persist_history({'time': _now(), 'source': source, 'task': label,
                              'ok': False, 'summary': summary})
            ctx.log.exception('[emby_toolbox] %s', summary)
        finally:
            _RUNTIME.update(running=False, finished_at=_now())
            active_task = None

    def _dispatch(keys: List[str], source: str, label: str):
        nonlocal active_task
        if active_task is not None and not active_task.done():
            return False
        active_task = ctx.create_task(
            _execute(keys, source, label),
            name=f'Emby 工具箱：{label}',
        )
        return True

    def _enabled_feature_keys(cfg: Dict[str, Any]) -> List[str]:
        """返回配置中已启用的全部维护模块，供“立即执行全部”使用。"""
        return [key for key in FEATURES if cfg.get(f'enable_{key}', False)]

    def _cleanup():
        if active_task is not None and not active_task.done():
            active_task.cancel()

    ctx.add_cleanup(_cleanup)

    @ctx.on_api('/status', methods=['GET'])
    async def api_status(req):
        history = list(state.get('run_history', []) or [])
        return {**_RUNTIME, 'history': history[:8],
                'schedule': _cfg(ctx)['schedule_cron'],
                'scheduled': bool(scheduled_jobs)}

    @ctx.on_api('/test', methods=['POST'])
    async def api_test(req):
        cfg = _cfg(ctx)
        ok, msg = _validate_basic(cfg)
        if not ok:
            return {'ok': False, 'message': msg}
        try:
            def _test():
                uid = _resolve_user_id(cfg)
                response = requests.get(
                    f"{_base_url(cfg['emby_server'])}/emby/Users/{uid}",
                    headers=_headers(cfg['api_key']), params={'api_key': cfg['api_key']}, timeout=30,
                )
                response.raise_for_status()
                data = response.json() if response.content else {}
                return uid, data.get('Name', '')
            uid, name = await asyncio.to_thread(_test)
            return {'ok': True, 'message': f'连接成功：{name or uid}', 'user_id': uid}
        except Exception as exc:
            return {'ok': False, 'message': f'连接失败：{exc}'}

    @ctx.on_api('/run', methods=['POST'])
    async def api_run(req):
        data = req.json or {}
        key = str(data.get('action') or '').strip()
        if key in ('scheduled', 'all'):
            cfg = _cfg(ctx)
            keys = _enabled_feature_keys(cfg) if key == 'all' else list(cfg.get('schedule_functions') or [])
            label = '立即执行全部已启用模块' if key == 'all' else '手动执行计划'
        else:
            keys = [key]
            label = FEATURES.get(key, ('扫描剧集季集', '', False))[0]
        if not keys or any(k not in FEATURES and k != 'scan_episode_mismatch' for k in keys):
            return {'ok': False, 'message': '请先选择要执行的功能'}
        if not _dispatch(keys, '手动', label):
            return {'ok': False, 'message': '已有维护任务正在运行'}
        return {'ok': True, 'started': True, 'message': f'已在后台开始“{label}”'}

    @ctx.on_api('/history', methods=['GET'])
    async def api_history(req):
        return {'ok': True, 'items': list(state.get('run_history', []) or [])[:30]}

    @ctx.on_api('/history/clear', methods=['POST'])
    async def api_history_clear(req):
        persist('run_history', [])
        _RECENT.clear()
        return {'ok': True}

    cfg = _cfg(ctx)
    if cfg.get('enable_auto_schedule'):
        cron = str(cfg.get('schedule_cron') or '').split()
        if len(cron) == 5:
            async def _scheduled_dispatch():
                keys = list(_cfg(ctx).get('schedule_functions') or [])
                if keys and _dispatch(keys, '定时', '定时媒体维护'):
                    ctx.log.info('[emby_toolbox] 定时任务已投递后台执行')
            try:
                kwargs = dict(zip(('minute', 'hour', 'day', 'month', 'day_of_week'), cron))
                scheduled_jobs.append(ctx.schedule_cron(
                    'Emby 工具箱·媒体维护', _scheduled_dispatch, **kwargs
                ))
            except Exception:
                ctx.log.exception('[emby_toolbox] 定时表达式注册失败：%s', cfg.get('schedule_cron'))


async def teardown(ctx):
    global _EMBY_PERSIST
    _RUNTIME.update(running=False, task='', source='', finished_at=_now())
    _EMBY_PERSIST = None
    ctx.log.info('[emby_toolbox] 插件已停用')


async def self_check(ctx):
    cfg = _cfg(ctx)
    ok, message = _validate_basic(cfg)
    return {
        'id': 'emby_configuration', 'name': 'Emby 连接配置', 'ok': ok,
        'detail': '服务地址与 API Key 已配置' if ok else message,
    }
