import json
import re
from datetime import datetime
from urllib.parse import quote

from ...core.config import config_manager
from ...utils import safe_get
from ...core.runtime import get_runtime
from pyquery import PyQuery as pq


def parse_movie_data(data: dict):
    movies = []
    casts = []

    page_props = ((data or {}).get("props") or {}).get("pageProps") or {}
    works = page_props.get("works") or []

    for work in works:
        cast_names = []
        for actor in work.get("actors", []):
            actor_name = actor.get("name")
            if actor_name and actor_name not in cast_names:
                cast_names.append(actor_name)
            cast = {
                "name": actor.get("name"),
                "avatar": actor.get("image_url"),
            }
            casts.append(cast)

        selected_title = None
        selected_poster = None
        selected_banner = None
        selected_series = None
        selected_producer = None
        selected_publisher = None
        still_photos = []
        release_date = None

        for product in work.get("products") or []:
            if not selected_title and product.get("title"):
                selected_title = product.get("title")

            if not selected_poster and product.get("thumbnail_url"):
                selected_poster = product.get("thumbnail_url")

            if not selected_banner and product.get("image_url"):
                selected_banner = product.get("image_url")

            if not selected_series:
                selected_series = (product.get("series") or {}).get("name")
            if not selected_producer:
                selected_producer = (product.get("maker") or {}).get("name")
            if not selected_publisher:
                selected_publisher = (product.get("label") or {}).get("name")

            still_photos.extend([img["l"] for img in product.get("sample_image_urls", [])])

            if not release_date and product.get("date"):
                date_str = re.sub(r"\(.*?\)", "", product["date"]).strip()
                release_date = datetime.strptime(date_str, "%a %b %d %Y %H:%M:%S GMT%z").date()

        number = work["work_id"]
        number = re.sub(r'^\d+([A-Za-z])', r'\1', number) if number else number
        movie = {
            "number": number,
            "title": selected_title,
            "release_date": release_date,
            "poster": selected_poster,
            "banner": selected_banner,
            "still_photos": still_photos,
            "series": selected_series,
            "producer": selected_producer,
            "publisher": selected_publisher,
            "cast_names": cast_names,
        }
        movies.append(movie)
    total = page_props.get('total')
    page = page_props.get('page') or 1
    max_page = page_props.get('max_page')
    return movies, casts, len(works), total, page, max_page


def parse_talent_data(data: dict, keyword: str, fallback_avatar: str | None = None):
    page_props = ((data or {}).get("props") or {}).get("pageProps") or {}
    talent = page_props.get("talent") or {}
    primary = talent.get("primary") or {}
    actors = talent.get("actors") or []

    # 主名只取 primary，不再混用 pageProps.name 或搜索关键字。
    name = (primary.get("name") or '').strip() or keyword
    avatar = primary.get("image_url") or fallback_avatar

    # 曾用名只取 actors
    former_name = []
    for actor in actors:
        actor_name = ((actor or {}).get("name") or '').strip()
        if actor_name and actor_name not in former_name:
            former_name.append(actor_name)

    return {
        "name": name,
        "former_name": former_name,
        "avatar": avatar,
    }


class AvBase:
    domain = 'https://www.avbase.net'

    def get_movie(self, number):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }
        url = f"{self.domain}/works?q={number}"
        res = safe_get(url, proxies=proxies)
        if res:
            doc = pq(res.text)
            json_doc = doc('script#__NEXT_DATA__')
            if json_doc:
                json_str = json_doc.text()
                data = json.loads(json_str)
                movies, casts, _, _, _, _ = parse_movie_data(data)
                return movies, casts
        return [], []

    def get_daily(self, date_str: str):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }
        page = 1
        movies = []
        casts = []
        page_size = 30
        max_page = None

        while page <= 100:
            get_runtime().check_cancelled()
            url = f"{self.domain}/works/date/{date_str}?page={page}"
            res = safe_get(url, proxies=proxies)
            if not res:
                break
            doc = pq(res.text)
            json_doc = doc('script#__NEXT_DATA__')
            if not json_doc:
                break
            json_str = json_doc.text()
            data = json.loads(json_str)
            page_movies, page_casts, work_count, total, _, current_max_page = parse_movie_data(data)
            movies.extend(page_movies)
            casts.extend(page_casts)

            if max_page is None:
                if current_max_page:
                    max_page = int(current_max_page)
                elif total:
                    max_page = max(1, (int(total) + page_size - 1) // page_size)
                else:
                    max_page = 1

            if work_count == 0 or page >= max_page:
                break
            page += 1

        return movies, casts


    def get_recent(self):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }
        page = 1
        movies = []
        casts = []
        page_size = 30
        max_page = None

        while page <= 100:
            get_runtime().check_cancelled()
            url = f"{self.domain}/works/recent?page={page}"
            res = safe_get(url, proxies=proxies)
            if not res:
                break

            doc = pq(res.text)
            json_doc = doc('script#__NEXT_DATA__')
            if not json_doc:
                break

            try:
                data = json.loads(json_doc.text())
            except json.JSONDecodeError:
                break

            page_movies, page_casts, work_count, total, _, current_max_page = parse_movie_data(data)
            movies.extend(page_movies)
            casts.extend(page_casts)

            if max_page is None:
                if current_max_page:
                    max_page = int(current_max_page)
                elif total:
                    max_page = max(1, (int(total) + page_size - 1) // page_size)
                else:
                    max_page = 1

            if work_count == 0 or page >= max_page:
                break
            page += 1

        return movies, casts

    def get_talent(self, keyword: str, fallback_avatar: str | None = None):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }
        encoded_keyword = quote((keyword or '').strip())
        if not encoded_keyword:
            return None

        url = f"{self.domain}/talents/{encoded_keyword}"
        res = safe_get(url, proxies=proxies)
        if not res or res.status_code != 200:
            return None

        doc = pq(res.text)
        json_doc = doc('script#__NEXT_DATA__')
        if not json_doc:
            return None

        try:
            data = json.loads(json_doc.text())
        except json.JSONDecodeError:
            return None

        return parse_talent_data(data, keyword=keyword, fallback_avatar=fallback_avatar)

    def get_talent_works(self, cast_name: str, max_page: int | None = None, is_single: bool = False):
        proxies = {
            "http": config_manager.get().PROXY,
            "https": config_manager.get().PROXY
        }
        encoded_keyword = quote((cast_name or '').strip())
        if not encoded_keyword:
            return [], []

        all_movies = []
        all_casts = []
        page_num = 1
        target_max_page = min(100, max(1, int(max_page))) if max_page else 100

        while True:
            get_runtime().check_cancelled()
            query_params = []
            if page_num > 1:
                query_params.append(f'page={page_num}')
            if is_single:
                query_params.append('cast_size=single')
            query_string = f"?{'&'.join(query_params)}" if query_params else ''
            url = f"{self.domain}/talents/{encoded_keyword}{query_string}"
            res = safe_get(url, proxies=proxies)
            if not res or res.status_code != 200:
                break

            doc = pq(res.text)
            json_doc = doc('script#__NEXT_DATA__')
            if not json_doc:
                break

            try:
                data = json.loads(json_doc.text())
            except json.JSONDecodeError:
                break

            movies, casts, work_count, _, _, current_max_page = parse_movie_data(data)
            all_movies.extend(movies)
            all_casts.extend(casts)

            if work_count == 0:
                break

            if target_max_page is not None and page_num >= target_max_page:
                break

            if target_max_page is None and current_max_page and page_num >= int(current_max_page):
                break

            page_num += 1

        return all_movies, all_casts


av_base = AvBase()
