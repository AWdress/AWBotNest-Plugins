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
import json
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

__plugin__ = {
    "name": "Emby 工具箱",
    "id": "emby_toolbox",
    "version": "1.4.1",
    "author": "AWdress",
    "description": "集成 Emby 剧集校验、Genre 清理/映射、季名刮削、国家语言 Tag、别名写入、STRM 刷新、元数据缺失检查等维护功能。支持定时执行与完整日志。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/icons/family_utility.png",
    "changelog": "v1.4.1 重做 Vue 界面配色\n- 去除大面积墨绿色背景，改为与平台一致的深海军蓝中性层次\n- Emby 青蓝仅用于开关、主按钮和选中状态\n- 重新校正卡片、输入框、次要文字与边框对比度\n\nv1.4.0 迁移 Vue 媒体维护控制台\n- 新增实时任务状态、历史记录和后台 API",
    "scope": "standalone",
    "render_mode": "vue",
    "min_platform_version": "1.1.4.0",
    "plugin_api_version": 1,
    "default_enabled": False,
    "requirements": ["requests>=2.28"],
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
    'enable_auto_schedule': False, 'schedule_cron': '0 3 * * *',
    'schedule_functions': [],
}

FEATURES = {
    'episode_fix': ('剧集季集修复', '_episode_fix', False),
    'delete_episode_genre': ('删除单集 Genre', '_delete_episode_genre', False),
    'genre_mapper': ('Genre 映射', '_genre_mapper', False),
    'season_renamer': ('季名刮削', '_season_renamer', True),
    'country_scraper': ('国家/语言标签', '_country_scraper', True),
    'alt_renamer': ('别名写入', '_alt_renamer', True),
    'strm_mediainfo': ('STRM 媒体信息', '_strm_mediainfo', False),
    'damaged_check': ('元数据缺失检查', '_damaged_check', False),
}

_RUNTIME: Dict[str, Any] = {
    'running': False, 'task': '', 'source': '', 'started_at': '',
    'finished_at': '', 'last_result': '', 'last_ok': None,
}
_RECENT = deque(maxlen=30)


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
        'enable_auto_schedule': bool(c.get('enable_auto_schedule', False)),
        'schedule_cron': str(c.get('schedule_cron', '0 3 * * *') or '0 3 * * *'),
        'schedule_functions': list(c.get('schedule_functions', []) or []),
    }


def _base_url(server: str) -> str:
    return server.rstrip('/')


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


def _get_user_item(cfg: Dict[str, Any], user_id: str, item_id: str) -> Dict[str, Any]:
    url = f"{_base_url(cfg['emby_server'])}/emby/Users/{user_id}/Items/{item_id}"
    r = requests.get(url, headers=_headers(cfg['api_key']), timeout=30)
    r.raise_for_status()
    return r.json()


def _update_item(cfg: Dict[str, Any], item: Dict[str, Any]) -> None:
    item_id = str(item['Id'])
    base = _base_url(cfg['emby_server'])
    url = f"{base}/emby/Items/{item_id}"
    params = {'api_key': cfg['api_key']}
    try:
        r = requests.post(url, params=params, headers=_post_headers(cfg['api_key']), data=json.dumps(item, ensure_ascii=False), timeout=60)
        r.raise_for_status()
    except requests.HTTPError as e:
        if '404' in str(e):
            # 某些条目需要通过用户路径更新
            user_id = _resolve_user_id(cfg)
            url = f"{base}/emby/Users/{user_id}/Items/{item_id}"
            r = requests.post(url, params=params, headers=_post_headers(cfg['api_key']), data=json.dumps(item, ensure_ascii=False), timeout=60)
            r.raise_for_status()
        else:
            raise


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
    user_id = _resolve_user_id(cfg)
    url = f"{_base_url(cfg['emby_server'])}/emby/Users/{user_id}/Views"
    r = requests.get(url, params={'api_key': cfg['api_key']}, headers=_headers(cfg['api_key']), timeout=30)
    r.raise_for_status()
    return r.json().get('Items', [])


def _get_library_id(cfg: Dict[str, Any], lib_name: str) -> Optional[str]:
    for item in _get_libraries(cfg):
        if item.get('Name') == lib_name:
            return str(item.get('Id'))
    return None


def _get_lib_items(cfg: Dict[str, Any], parent_id: str) -> List[Dict[str, Any]]:
    url = f"{_base_url(cfg['emby_server'])}/emby/Users/{_resolve_user_id(cfg)}/Items"
    params = {
        'api_key': cfg['api_key'],
        'ParentId': parent_id,
        'Recursive': 'false',
        'Fields': 'ProviderIds,Name,Type',
        'SortBy': 'SortName',
        'SortOrder': 'Ascending',
    }
    r = requests.get(url, params=params, headers=_headers(cfg['api_key']), timeout=60)
    r.raise_for_status()
    return r.json().get('Items', [])


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
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始删除单集 Genre，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        series_list = _get_lib_items(cfg, parent_id)
        if ctx:
            ctx.log.info(f'[emby_toolbox] 处理媒体库 {lib}，共 {len(series_list)} 个剧集')
        for serie in series_list:
            serie_id = serie['Id']
            url = f"{_base_url(cfg['emby_server'])}/emby/Items"
            params = {'ParentId': serie_id}
            seasons = requests.get(url, headers=_headers(cfg['api_key']), params=params, timeout=60).json().get('Items', [])
            for season in seasons:
                season_id = season.get('Id')
                eps = requests.get(url, headers=_headers(cfg['api_key']), params={
                    'ParentId': season_id, 'Fields': 'Genres,Overview', 'IncludeItemTypes': 'Episode', 'Recursive': 'true', 'SortBy': 'SortName', 'SortOrder': 'Ascending'
                }, timeout=60).json().get('Items', [])
                for ep in eps:
                    item = _get_user_item(cfg, _resolve_user_id(cfg), str(ep['Id']))
                    if item.get('Genres'):
                        item['Genres'] = []
                        item['GenreItems'] = []
                        if cfg['fix_lock_data']:
                            item['LockData'] = True
                        _update_item(cfg, item)
                        count += 1
    result = f'单集 Genre 清理完成，共更新 {count} 条。'
    if ctx:
        ctx.log.info(f'[emby_toolbox] {result}')
    return result


def _genre_mapper(cfg: Dict[str, Any], ctx=None) -> str:
    libs = _parse_libs(cfg['library_names'])
    if not libs:
        raise RuntimeError('未配置媒体库名称列表')
    mapping = _parse_genre_mapping(cfg['genre_mapping_json'])
    remove_list = _parse_remove_list(cfg['genre_remove_list'])
    count = 0
    user_id = _resolve_user_id(cfg)
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始 Genre 映射，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        if ctx:
            ctx.log.info(f'[emby_toolbox] 处理媒体库 {lib}，共 {len(items)} 个条目')
        for item0 in items:
            item = _get_user_item(cfg, user_id, str(item0['Id']))
            raw_genres = item.get('Genres', [])
            genres = [g.strip() for g in raw_genres if isinstance(g, str) and g.strip()]
            genre_items = item.get('GenreItems', [])
            need = any(g in mapping or g in remove_list for g in genres) or any((g.get('Name') or '').strip() in mapping for g in genre_items)
            if not need:
                continue
            new_genres = [mapping[g]['Name'] if g in mapping else g for g in genres]
            new_genres = [g for g in new_genres if g not in remove_list and g != '']
            if new_genres == genres:
                continue
            item['Genres'] = new_genres
            new_genre_items = []
            for gi in genre_items:
                gname = (gi.get('Name') or '').strip()
                if gname in mapping:
                    new_genre_items.append(mapping[gname])
                elif gname not in remove_list and gname != '':
                    new_genre_items.append(gi)
            item['GenreItems'] = new_genre_items
            if cfg['fix_lock_data']:
                item['LockData'] = True
            _update_item(cfg, item)
            count += 1
    result = f'Genre 映射完成，共更新 {count} 条。'
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
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始季名刮削，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        series_list = _get_lib_items(cfg, parent_id)
        if ctx:
            ctx.log.info(f'[emby_toolbox] 处理媒体库 {lib}，共 {len(series_list)} 个剧集')
        for serie in series_list:
            if serie.get('Type') == 'Movie':
                continue
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
            seasons = requests.get(url, headers=_headers(cfg['api_key']), params={'ParentId': serie['Id'], 'fields': 'Name,IndexNumber,LockedFields'}, timeout=60).json().get('Items', [])
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
                _update_item(cfg, full)
                count += 1
                if ctx:
                    ctx.log.info(f'[emby_toolbox] 季名刮削更新: {serie.get("Name", "未知")} S{idx} -> {new_name}')
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
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始国家/语言 Tag 刮削，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
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
            item = _get_user_item(cfg, user_id, str(item0['Id']))
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
            _update_item(cfg, item)
            count += 1
            if ctx:
                ctx.log.info(f'[emby_toolbox] 国家/语言标签更新: {item0.get("Name", "未知")} +{len(new_tags)} 标签')
    result = f'国家/语言 Tag 更新完成，共更新 {count} 条。'
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
    skip_unchanged = 0
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始别名写入，媒体库: {libs}')
    
    # 批量获取条目以减少 API 调用
    import time
    request_count = 0
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            provider = (item0.get('ProviderIds') or {}).get('Tmdb')
            if not provider:
                continue
            is_movie = item0.get('Type') == 'Movie'
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
            item = _get_user_item(cfg, user_id, str(item0['Id']))
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
            _update_item(cfg, item)
            count += 1
    result = f'别名写入完成，共更新 {count} 条。'
    if skip_tmdb > 0:
        result += f'（跳过 {skip_tmdb} 条 TMDB 不可达）'
    if skip_unchanged > 0:
        result += f'（跳过 {skip_unchanged} 条已是最新）'
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
    if ctx:
        ctx.log.info(f'[emby_toolbox] 开始 STRM MediaInfo 刷新，媒体库: {libs}')
    for lib in libs:
        parent_id = _get_library_id(cfg, lib)
        if not parent_id:
            continue
        items = _get_lib_items(cfg, parent_id)
        for item0 in items:
            item_type = item0.get('Type')
            targets = []
            if item_type == 'Movie':
                targets = [item0['Id']]
            elif item_type == 'Series':
                url = f"{_base_url(cfg['emby_server'])}/emby/Items"
                seasons = requests.get(url, headers=_headers(cfg['api_key']), params={'ParentId': item0['Id']}, timeout=60).json().get('Items', [])
                for season in seasons:
                    eps = requests.get(url, headers=_headers(cfg['api_key']), params={
                        'ParentId': season.get('Id'), 'IncludeItemTypes': 'Episode', 'Recursive': 'true', 'SortBy': 'SortName', 'SortOrder': 'Ascending'
                    }, timeout=60).json().get('Items', [])
                    targets.extend([ep['Id'] for ep in eps])
            for item_id in targets:
                item = _get_user_item(cfg, user_id, str(item_id))
                if item.get('LocationType') == 'Virtual':
                    continue
                media_streams = item.get('MediaStreams') or []
                if len(media_streams) != 0:
                    continue
                url = f"{_base_url(cfg['emby_server'])}/Items/{item_id}/PlaybackInfo?AutoOpenLiveStream=true&IsPlayback=true&api_key={cfg['api_key']}&UserId={user_id}"
                r = requests.post(url, headers=_headers(cfg['api_key']), timeout=60)
                if r.status_code == 200:
                    count += 1
                time.sleep(delay)
    result = f'STRM MediaInfo 刷新完成，共更新 {count} 条。'
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
            item = _get_user_item(cfg, user_id, str(item0['Id']))
            has_overview = bool(item.get('Overview'))
            has_year = bool(item.get('ProductionYear'))
            has_premiere = bool(item.get('PremiereDate'))
            if not has_overview and not has_year and not has_premiere:
                damaged.append({'lib': lib, 'id': item0['Id'], 'name': item0.get('Name', '未知名称'), 'type': item.get('Type', 'Unknown')})
    lines = [f'总计扫描条目: {total} 个', f'受影响/缺少关键元数据条目: {len(damaged)} 个']
    if damaged:
        lines.append('前几条如下：')
        for row in damaged[:cfg['max_output']]:
            lines.append(f"- [{row['lib']}] 《{row['name']}》 | ItemId: {row['id']} | 类型: {row['type']}")
    else:
        lines.append('🎉 未检测到元数据缺失条目')
    return '\n'.join(lines)


async def _legacy_setup(ctx):
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
            _run(), name=f'Emby 工具箱：{label}', operation='manual_maintenance'
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
                await ctx.notify(f'[Emby工具箱] 定时任务完成\n{summary}', category='Emby工具箱')
            except Exception:
                pass
        
        try:
            cron_parts = schedule_cron.split()
            if len(cron_parts) == 5:
                ctx.schedule(scheduled_task, 'cron', id='Emby 工具箱定时维护',
                            minute=int(cron_parts[0]) if cron_parts[0] != '*' else None,
                            hour=int(cron_parts[1]) if cron_parts[1] != '*' else None,
                            day=int(cron_parts[2]) if cron_parts[2] != '*' else None,
                            month=int(cron_parts[3]) if cron_parts[3] != '*' else None,
                            day_of_week=int(cron_parts[4]) if cron_parts[4] != '*' else None)
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

async def _legacy_teardown(ctx):
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
        'scan_episode_mismatch': lambda: _episode_summary(*_episode_collect(cfg), cfg['max_output']),
    }
    if key not in workers:
        raise ValueError(f'未知功能：{key}')
    return workers[key]()


async def setup(ctx):
    """Vue 模式：配置交给前端，所有长任务由平台后台托管。"""
    active_task = None
    scheduled_jobs = []

    def _persist_history(row: Dict[str, Any]):
        _RECENT.appendleft(row)
        try:
            saved = list(ctx.kv.get('run_history', []) or [])
            saved.insert(0, row)
            ctx.kv.set('run_history', saved[:30])
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
                    await asyncio.wait_for(ctx.notify(
                        f'[Emby工具箱] {label}完成\n{summary}', category='Emby工具箱'
                    ), timeout=30)
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
            name=f'Emby 工具箱：{label}', operation='emby_maintenance',
        )
        return True

    def _cleanup():
        if active_task is not None and not active_task.done():
            active_task.cancel()

    ctx.add_cleanup(_cleanup)

    @ctx.on_api('/status', methods=['GET'])
    async def api_status(req):
        history = list(ctx.kv.get('run_history', []) or [])
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
        if key == 'scheduled':
            keys = list(_cfg(ctx).get('schedule_functions') or [])
            label = '手动执行计划'
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
        return {'ok': True, 'items': list(ctx.kv.get('run_history', []) or [])[:30]}

    @ctx.on_api('/history/clear', methods=['POST'])
    async def api_history_clear(req):
        ctx.kv.set('run_history', [])
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
                kwargs = {}
                for name, value in zip(('minute', 'hour', 'day', 'month', 'day_of_week'), cron):
                    if value != '*':
                        kwargs[name] = int(value)
                scheduled_jobs.append(ctx.schedule(
                    _scheduled_dispatch, 'cron', id='Emby 工具箱·媒体维护', **kwargs
                ))
            except Exception:
                ctx.log.exception('[emby_toolbox] 定时表达式注册失败：%s', cfg.get('schedule_cron'))


async def teardown(ctx):
    _RUNTIME.update(running=False, task='', source='', finished_at=_now())
    ctx.log.info('[emby_toolbox] 插件已停用')


async def self_check(ctx):
    cfg = _cfg(ctx)
    ok, message = _validate_basic(cfg)
    return {
        'id': 'emby_configuration', 'name': 'Emby 连接配置', 'ok': ok,
        'detail': '服务地址与 API Key 已配置' if ok else message,
    }
