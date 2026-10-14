import re
import time
from hashlib import md5
from urllib.parse import quote, urlparse, urlunparse

from ...core.config import config_manager
from ...utils import logger, safe_get


def get_headers():
    timestamp = int(time.time())
    secret = '71cf27bb3c0bcdf207b64abecddc970098c7421ee7203b9cdae54478478a199e7d5a6e1a57691123c1a931c057842fb73ba3b3c83bcd69c17ccf174081e3d8aa'
    md5_str = md5(f'{timestamp}{secret}'.encode()).hexdigest()
    jdsignature = f'{timestamp}.lpw6vgqzsp.{md5_str}'
    return {
        'User-Agent': 'Dart/3.5 (dart:io)',
        'accept-language': 'zh-TW',
        'jdsignature': jdsignature,
    }


def convert_image_url(old_url):
    if not old_url:
        return old_url
    parsed = urlparse(old_url)
    path_parts = parsed.path.split('/')
    if len(path_parts) < 3:
        return old_url
    new_path = '/'.join(path_parts[0:1] + path_parts[2:])
    new_parsed = parsed._replace(netloc='c0.jdbstatic.com', path=new_path)
    return urlunparse(new_parsed)


def _get_proxies():
    return {
        'http': config_manager.get().PROXY,
        'https': config_manager.get().PROXY,
    }


def _get_api_host() -> str:
    return config_manager.get().JAVDB_API_HOST or 'https://api.btyjscl.com'


def _normalize_number(number: str | None) -> str:
    return re.sub(r'[^A-Z0-9]', '', (number or '').upper())


def _convert_casts(actors):
    actors = actors or []
    casts = []
    seen = set()
    for actor in actors:
        if actor.get('gender') != 0:
            continue
        name = (actor.get('name') or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        casts.append({
            'name': name,
            'avatar': convert_image_url(actor.get('avatar_url')) if actor.get('avatar_url') else None,
        })
    return casts


def convert_movie(movie):
    preview_images = movie.get('preview_images') or []
    tags = movie.get('tags') or []
    still_photos = []
    seen_photos = set()
    for item in preview_images:
        large_url = item.get('large_url')
        if not large_url:
            continue
        photo = convert_image_url(large_url)
        if photo in seen_photos:
            continue
        seen_photos.add(photo)
        still_photos.append(photo)

    number = movie['number']
    number = re.sub(r'^\d+([A-Za-z])', r'\1', number) if number else number
    return {
        'number': number,
        'title': movie.get('title'),
        'banner': convert_image_url(movie.get('cover_url')) if movie.get('cover_url') else None,
        'poster': convert_image_url(movie.get('cover_url')) if movie.get('cover_url') else None,
        'release_date': movie.get('release_date') or None,
        'duration': movie.get('duration'),
        'still_photos': still_photos,
        'series': movie.get('series_name'),
        'producer': movie.get('maker_name'),
        'publisher': movie.get('publisher_name'),
        'genres': [tag.get('name') for tag in tags if tag.get('name')],
    }


def _request_json(url: str):
    headers = get_headers()
    res = safe_get(url, proxies=_get_proxies(), headers=headers, allow_redirects=True, timeout=10)
    if not res:
        return None
    try:
        return res.json()
    except Exception:
        logger.exception(f'JavDB API 响应解析失败 | url={url}')
        return None


def crawler_api(keyword: str):
    url = f'{_get_api_host()}/api/v2/search?q={quote(keyword)}'
    data = _request_json(url)
    if not data:
        return None

    movies = ((data.get('data') or {}).get('movies') or [])
    normalized_keyword = _normalize_number(keyword)
    for movie in movies:
        if _normalize_number(movie.get('number')) == normalized_keyword:
            movie_id = movie.get('id')
            if movie_id:
                return crawler_detail_api(movie_id)
    return None


def crawler_detail_api(movie_id: str):
    url = f'{_get_api_host()}/api/v4/movies/{movie_id}'
    data = _request_json(url)
    if not data:
        return None
    movie = ((data.get('data') or {}).get('movie') or None)
    if not movie:
        return None
    return movie


class JavDB:
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'

    def get_top_movie(self, section_type, period):
        url = f'{_get_api_host()}/api/v1/rankings?type={section_type}&period={period}'
        try:
            data = _request_json(url)
            movies = ((data or {}).get('data') or {}).get('movies') or []
            if movies:
                return [convert_movie(movie) for movie in movies]
        except Exception:
            logger.exception('')
        return []

    def get_movie(self, number: str):
        try:
            movie = crawler_api(number)
            if not movie:
                return [], []
            casts = _convert_casts(movie.get('actors'))
            return [convert_movie(movie)], casts
        except Exception:
            logger.exception(f'JavDB 影片抓取失败 | number={number}')
            return [], []


javdb = JavDB()
