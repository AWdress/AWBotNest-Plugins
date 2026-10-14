from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session

from ...enums import SubscribeStatus
from ...core.portable_types import array_member, array_to_string
from ...models import Article, Cast, CastSubscribe, Filter, GeneralSubscribe, Movie, Priority, Subscribe
from ...utils.movie_number import extract_movie_numbers
from ...modules.mediaserver import mediaServerManager
from ...modules.notification.manager import pushManager
from ...api.services.subscribe_preference_service import get_subscribe_preference_config
from ...schemas.response import success
from ...core.runtime import get_runtime
from ...utils.db_lock import acquire_subscribe_write_lock
from ...utils.log import logger
from ...schemas.subscribe import (
    CastSubscribePageParam,
    CastSubscribeParam,
    CastSubscribeUpdateParam,
    GeneralSubscribePageParam,
    GeneralSubscribeParam,
    GeneralSubscribeUpdateParam,
    SubscribeCleanupDiagnosticParam,
    SubscribePageParam,
    SubscribeParam,
    SubscribeUpdateParam,
)


def _value_or_none(value: Any) -> Any:
    return None if value is None else value


def _format_date(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return ''


def _format_datetime(value):
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return ''


def _join_values(values):
    if not values:
        return ''
    if isinstance(values, (list, tuple, set)):
        return ' / '.join(str(item) for item in values if item)
    return str(values)


def _flag_text(value: Any) -> str:
    return '是' if bool(value) else '否'


def _normalize_general_subscribe_text(value: str | None, *, uppercase: bool = False) -> str | None:
    normalized = (value or '').strip()
    if not normalized:
        return None
    return normalized.upper() if uppercase else normalized


def _normalize_general_subscribe_genres(values: list[str] | None) -> list[str] | None:
    if not values:
        return None

    normalized_values = []
    seen = set()
    for value in values:
        normalized = (value or '').strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized_values.append(normalized)

    if not normalized_values:
        return None

    return sorted(normalized_values, key=lambda item: item.casefold())


def get_general_subscribe_options(
        db: Session,
        publisher: str | None = None,
        series: str | None = None,
        producer: str | None = None,
        genres: list[str] | None = None,
):
    normalized_publisher = _normalize_general_subscribe_text(publisher)
    normalized_series = _normalize_general_subscribe_text(series)
    normalized_producer = _normalize_general_subscribe_text(producer)
    normalized_genres = _normalize_general_subscribe_genres(genres)

    query = db.query(Movie.publisher, Movie.series, Movie.producer, Movie.genres)

    if normalized_publisher:
        query = query.filter(func.lower(func.coalesce(Movie.publisher, '')) == normalized_publisher.lower())
    if normalized_series:
        query = query.filter(func.lower(func.coalesce(Movie.series, '')) == normalized_series.lower())
    if normalized_producer:
        query = query.filter(func.lower(func.coalesce(Movie.producer, '')) == normalized_producer.lower())
    if normalized_genres:
        query = query.filter(Movie.genres.contains(normalized_genres))

    rows = query.limit(5000).all()

    publisher_counter: Counter[str] = Counter()
    series_counter: Counter[str] = Counter()
    producer_counter: Counter[str] = Counter()
    genre_counter: Counter[str] = Counter()

    for movie_publisher, movie_series, movie_producer, movie_genres in rows:
        normalized_publisher_value = str(movie_publisher or '').strip()
        if normalized_publisher_value:
            publisher_counter.update([normalized_publisher_value])

        normalized_series_value = str(movie_series or '').strip()
        if normalized_series_value:
            series_counter.update([normalized_series_value])

        normalized_producer_value = str(movie_producer or '').strip()
        if normalized_producer_value:
            producer_counter.update([normalized_producer_value])

        for genre in movie_genres or []:
            normalized_genre = str(genre or '').strip()
            if normalized_genre:
                genre_counter.update([normalized_genre])

    def _sort_counter_values(counter: Counter[str]) -> list[str]:
        return [
            value
            for value, _ in sorted(
                counter.items(),
                key=lambda item: (-item[1], item[0].casefold()),
            )
        ]

    return success({
        'publishers': _sort_counter_values(publisher_counter),
        'series': _sort_counter_values(series_counter),
        'producers': _sort_counter_values(producer_counter),
        'genres': _sort_counter_values(genre_counter),
    })


def _find_general_subscribe_by_match(
        db: Session,
        *,
        number_prefix: str | None,
        publisher: str | None,
        series: str | None,
        producer: str | None,
        genres: list[str] | None,
        exclude_id: int | None = None,
):
    query = db.query(GeneralSubscribe)
    if exclude_id is not None:
        query = query.filter(GeneralSubscribe.id != exclude_id)

    if number_prefix is None:
        query = query.filter(GeneralSubscribe.number_prefix.is_(None))
    else:
        query = query.filter(GeneralSubscribe.number_prefix == number_prefix)

    if publisher is None:
        query = query.filter(GeneralSubscribe.publisher.is_(None))
    else:
        query = query.filter(GeneralSubscribe.publisher == publisher)

    if series is None:
        query = query.filter(GeneralSubscribe.series.is_(None))
    else:
        query = query.filter(GeneralSubscribe.series == series)

    if producer is None:
        query = query.filter(GeneralSubscribe.producer.is_(None))
    else:
        query = query.filter(GeneralSubscribe.producer == producer)

    if genres is None:
        query = query.filter(GeneralSubscribe.genres.is_(None))
    else:
        query = query.filter(GeneralSubscribe.genres == genres)

    return query.order_by(GeneralSubscribe.id.desc()).first()


def _serialize_movie(movie: Movie | None) -> dict[str, Any]:
    if movie is None:
        return {}
    return {
        'id': movie.id,
        'number': movie.number or '',
        'title': movie.title or '',
        'cn_title': movie.cn_title or '',
        'description': movie.description or '',
        'cn_description': movie.cn_description or '',
        'release_date': _format_date(movie.release_date),
        'duration': _value_or_none(movie.duration),
        'poster': movie.poster or '',
        'banner': movie.banner or '',
        'still_photos': movie.still_photos or [],
        'genres': movie.genres or [],
        'series': movie.series or '',
        'producer': movie.producer or '',
        'publisher': movie.publisher or '',
        'casts': movie.casts or [],
        'cast_names': movie.cast_names or [],
        'create_time': _format_datetime(getattr(movie, 'create_time', None)),
        'update_time': _format_datetime(getattr(movie, 'update_time', None)),
    }


def _serialize_cast(cast: Cast | None) -> dict[str, Any]:
    if cast is None:
        return {}
    return {
        'id': cast.id,
        'name': cast.name or '',
        'cn_name': cast.cn_name or '',
        'former_name': cast.former_name or [],
        'avatar': cast.avatar or '',
        'photo': cast.photo or '',
        'create_time': _format_datetime(getattr(cast, 'create_time', None)),
        'update_time': _format_datetime(getattr(cast, 'update_time', None)),
    }


def _serialize_article(article: Article | None) -> dict[str, Any]:
    if article is None:
        return {}
    return {
        'id': article.id,
        'tid': article.tid,
        'title': article.title or '',
        'publish_date': _format_date(article.publish_date),
        'magnet': article.magnet or [],
        'edk': article.edk or [],
        'preview_images': article.preview_images or [],
        'detail_url': article.detail_url or '',
        'size': _value_or_none(article.size),
        'section': article.section or '',
        'category': article.category or '',
        'website': article.website or '',
        'match_number': article.match_number or '',
        'create_time': _format_datetime(getattr(article, 'create_time', None)),
        'update_time': _format_datetime(getattr(article, 'update_time', None)),
    }


def _serialize_filter(filter_obj: Filter | None) -> dict[str, Any]:
    if filter_obj is None:
        return {}
    return {
        'id': filter_obj.id,
        'name': filter_obj.filter_name or '',
        'keyword': filter_obj.keyword or '',
        'resolutions': filter_obj.resolutions or [],
        'subtitles': filter_obj.subtitles or [],
        'mosaic': filter_obj.mosaic or [],
        'min_size': _value_or_none(filter_obj.min_size),
        'max_size': _value_or_none(filter_obj.max_size),
        'skip_in_library_check': bool(filter_obj.skip_in_library_check),
        'enable_pre_download': bool(filter_obj.enable_pre_download),
        'is_default': bool(filter_obj.is_default),
        'create_time': _format_datetime(getattr(filter_obj, 'create_time', None)),
        'update_time': _format_datetime(getattr(filter_obj, 'update_time', None)),
    }


def _serialize_priority(priority_obj: Priority | None) -> dict[str, Any]:
    if priority_obj is None:
        return {}
    return {
        'id': priority_obj.id,
        'name': priority_obj.priority_name or '',
        'resolutions': priority_obj.resolutions or [],
        'subtitles': priority_obj.subtitles or [],
        'mosaic': priority_obj.mosaic or [],
        'priority_sort': priority_obj.priority_sort or [],
        'is_default': bool(priority_obj.is_default),
        'create_time': _format_datetime(getattr(priority_obj, 'create_time', None)),
        'update_time': _format_datetime(getattr(priority_obj, 'update_time', None)),
    }


def _serialize_subscribe(subscribe: Subscribe | None) -> dict[str, Any]:
    if subscribe is None:
        return {}
    return {
        'id': subscribe.id,
        'movie_id': subscribe.movie_id,
        'filter_id': subscribe.filter_id or '',
        'priority_id': subscribe.priority_id or '',
        'status': subscribe.status or '',
        'pre_download_enabled': bool(subscribe.pre_download_enabled),
        'create_time': _format_datetime(getattr(subscribe, 'create_time', None)),
        'update_time': _format_datetime(getattr(subscribe, 'update_time', None)),
    }


def _serialize_cast_subscribe(cast_subscribe: CastSubscribe | None) -> dict[str, Any]:
    if cast_subscribe is None:
        return {}
    return {
        'id': cast_subscribe.id,
        'cast_id': cast_subscribe.cast_id,
        'max_coactors': _value_or_none(cast_subscribe.max_coactors),
        'max_page': _value_or_none(cast_subscribe.max_page),
        'replace_max_page': _value_or_none(cast_subscribe.replace_max_page),
        'is_single': bool(cast_subscribe.is_single),
        'earliest_release_date': _format_date(cast_subscribe.earliest_release_date),
        'exclude_vr': bool(cast_subscribe.exclude_vr),
        'filter_id': cast_subscribe.filter_id or '',
        'priority_id': cast_subscribe.priority_id or '',
        'status': cast_subscribe.status or '',
        'create_time': _format_datetime(getattr(cast_subscribe, 'create_time', None)),
        'update_time': _format_datetime(getattr(cast_subscribe, 'update_time', None)),
    }


def _serialize_general_subscribe(general_subscribe: GeneralSubscribe | None) -> dict[str, Any]:
    if general_subscribe is None:
        return {}
    return {
        'id': general_subscribe.id,
        'number_prefix': general_subscribe.number_prefix or '',
        'publisher': general_subscribe.publisher or '',
        'series': general_subscribe.series or '',
        'producer': general_subscribe.producer or '',
        'genres': general_subscribe.genres or [],
        'max_coactors': _value_or_none(general_subscribe.max_coactors),
        'earliest_release_date': _format_date(general_subscribe.earliest_release_date),
        'exclude_vr': bool(general_subscribe.exclude_vr),
        'filter_id': general_subscribe.filter_id or '',
        'priority_id': general_subscribe.priority_id or '',
        'status': general_subscribe.status or '',
        'create_time': _format_datetime(getattr(general_subscribe, 'create_time', None)),
        'update_time': _format_datetime(getattr(general_subscribe, 'update_time', None)),
    }


def _general_subscribe_summary(general_subscribe: GeneralSubscribe | None) -> str:
    payload = _serialize_general_subscribe(general_subscribe)
    if not payload:
        return ''
    parts = []
    if payload.get('number_prefix'):
        parts.append(f"番号前缀={payload.get('number_prefix')}")
    if payload.get('publisher'):
        parts.append(f"发行商={payload.get('publisher')}")
    if payload.get('series'):
        parts.append(f"系列={payload.get('series')}")
    if payload.get('producer'):
        parts.append(f"制作商={payload.get('producer')}")
    genres = [str(item).strip() for item in (payload.get('genres') or []) if str(item).strip()]
    if genres:
        parts.append('类型=' + '/'.join(genres))
    return '；'.join(parts) if parts else '未设置匹配条件'


def _serialize_cleanup_candidate(
        candidate_type: str,
        severity: str,
        reason: str,
        recommended_followup: str,
        **payload: Any,
) -> dict[str, Any]:
    return {
        'candidate_type': candidate_type,
        'severity': severity,
        'reason': reason,
        'recommended_followup': recommended_followup,
        **payload,
    }


def _general_subscribe_signature(general_subscribe: GeneralSubscribe | None) -> tuple[Any, ...]:
    if general_subscribe is None:
        return tuple()
    return (
        _normalize_general_subscribe_text(general_subscribe.number_prefix, uppercase=True),
        _normalize_general_subscribe_text(general_subscribe.publisher),
        _normalize_general_subscribe_text(general_subscribe.series),
        _normalize_general_subscribe_text(general_subscribe.producer),
        tuple(_normalize_general_subscribe_genres(list(general_subscribe.genres or [])) or []),
    )


def _serialize_general_signature(signature: tuple[Any, ...]) -> dict[str, Any]:
    values = list(signature or ())
    while len(values) < 5:
        values.append(None)
    return {
        'number_prefix': values[0] or '',
        'publisher': values[1] or '',
        'series': values[2] or '',
        'producer': values[3] or '',
        'genres': list(values[4] or []),
    }


def _build_movie_push_fields(movie: Movie | None) -> dict[str, Any]:
    movie_data = _serialize_movie(movie)
    payload = {
        'movie': movie_data,
        'movie_id': movie_data.get('id', ''),
        'movie_number': movie_data.get('number', ''),
        'movie_title': movie_data.get('title', ''),
        'movie_cn_title': movie_data.get('cn_title', ''),
        'movie_description': movie_data.get('description', ''),
        'movie_cn_description': movie_data.get('cn_description', ''),
        'movie_release_date': movie_data.get('release_date', ''),
        'movie_duration': movie_data.get('duration', ''),
        'movie_poster': movie_data.get('poster', ''),
        'movie_banner': movie_data.get('banner', ''),
        'movie_still_photos': movie_data.get('still_photos', []),
        'movie_genres': movie_data.get('genres', []),
        'movie_cast_ids': movie_data.get('casts', []),
        'movie_cast_names': movie_data.get('cast_names', []),
        'movie_create_time': movie_data.get('create_time', ''),
        'movie_update_time': movie_data.get('update_time', ''),
    }
    return payload


def _build_cast_push_fields(cast: Cast | None) -> dict[str, Any]:
    cast_data = _serialize_cast(cast)
    payload = {
        'cast': cast_data,
        'cast_id': cast_data.get('id', ''),
        'cast_name': cast_data.get('name', ''),
        'cast_cn_name': cast_data.get('cn_name', ''),
        'cast_former_name': cast_data.get('former_name', []),
        'cast_avatar': cast_data.get('avatar', ''),
        'cast_photo': cast_data.get('photo', ''),
        'cast_create_time': cast_data.get('create_time', ''),
        'cast_update_time': cast_data.get('update_time', ''),
    }
    return payload


def _build_article_push_fields(article: Article | None) -> dict[str, Any]:
    article_data = _serialize_article(article)

    # Compute article_in_library by checking if any movie number exists in library
    article_in_library = False
    if article and article.title:
        movie_numbers = extract_movie_numbers(article.title.strip())
        for number in movie_numbers:
            if mediaServerManager.any_movie_exists_by_number(number):
                article_in_library = True
                break

    payload = {
        'article': article_data,
        'article_id': article_data.get('id', ''),
        'article_tid': article_data.get('tid', ''),
        'article_title': article_data.get('title', ''),
        'article_match_number': article_data.get('match_number', ''),
        'article_publish_date': article_data.get('publish_date', ''),
        'article_magnet': article_data.get('magnet', []),
        'article_edk': article_data.get('edk', []),
        'article_preview_images': article_data.get('preview_images', []),
        'article_detail_url': article_data.get('detail_url', ''),
        'article_size': _value_or_none(article_data.get('size')),
        'article_section': article_data.get('section', ''),
        'article_category': article_data.get('category', ''),
        'article_website': article_data.get('website', ''),
        'article_create_time': article_data.get('create_time', ''),
        'article_update_time': article_data.get('update_time', ''),
        'article_in_library': article_in_library,
    }
    return payload


def build_article_push_fields(article: Article | None) -> dict[str, Any]:
    return _build_article_push_fields(article)


def _build_subscribe_filter_priority_push_fields(
        subscribe: Subscribe | None,
        filter_obj: Filter | None,
        priority_obj: Priority | None,
) -> dict[str, Any]:
    subscribe_data = _serialize_subscribe(subscribe)
    filter_data = _serialize_filter(filter_obj)
    priority_data = _serialize_priority(priority_obj)
    payload = {
        'subscribe': subscribe_data,
        'filter': filter_data,
        'priority': priority_data,
        'subscribe_id': subscribe_data.get('id', ''),
        'subscribe_movie_id': subscribe_data.get('movie_id', ''),
        'subscribe_filter_id': subscribe_data.get('filter_id', ''),
        'subscribe_priority_id': subscribe_data.get('priority_id', ''),
        'subscribe_status': subscribe_data.get('status', ''),
        'subscribe_pre_download_enabled': _flag_text(subscribe_data.get('pre_download_enabled')),
        'subscribe_create_time': subscribe_data.get('create_time', ''),
        'subscribe_update_time': subscribe_data.get('update_time', ''),
        'filter_id': subscribe_data.get('filter_id', '') or filter_data.get('id', ''),
        'filter_name': filter_data.get('name', ''),
        'filter_keyword': filter_data.get('keyword', ''),
        'filter_resolutions': _join_values(filter_data.get('resolutions')),
        'filter_subtitles': _join_values(filter_data.get('subtitles')),
        'filter_mosaic': _join_values(filter_data.get('mosaic')),
        'filter_min_size': _value_or_none(filter_data.get('min_size')),
        'filter_max_size': _value_or_none(filter_data.get('max_size')),
        'filter_skip_in_library_check': _flag_text(filter_data.get('skip_in_library_check')),
        'filter_enable_pre_download': _flag_text(filter_data.get('enable_pre_download')),
        'filter_is_default': _flag_text(filter_data.get('is_default')),
        'filter_create_time': filter_data.get('create_time', ''),
        'filter_update_time': filter_data.get('update_time', ''),
        'priority_id': subscribe_data.get('priority_id', '') or priority_data.get('id', ''),
        'priority_name': priority_data.get('name', ''),
        'priority_resolutions': _join_values(priority_data.get('resolutions')),
        'priority_subtitles': _join_values(priority_data.get('subtitles')),
        'priority_mosaic': _join_values(priority_data.get('mosaic')),
        'priority_sort': _join_values(priority_data.get('priority_sort')),
        'priority_is_default': _flag_text(priority_data.get('is_default')),
        'priority_create_time': priority_data.get('create_time', ''),
        'priority_update_time': priority_data.get('update_time', ''),
    }
    return payload


def _build_cast_subscribe_filter_priority_push_fields(
        cast_subscribe: CastSubscribe | None,
        filter_obj: Filter | None,
        priority_obj: Priority | None,
) -> dict[str, Any]:
    cast_subscribe_data = _serialize_cast_subscribe(cast_subscribe)
    payload = _build_subscribe_filter_priority_push_fields(None, filter_obj, priority_obj)
    payload.update({
        'cast_subscribe': cast_subscribe_data,
        'filter_id': cast_subscribe_data.get('filter_id', '') or payload.get('filter_id', ''),
        'priority_id': cast_subscribe_data.get('priority_id', '') or payload.get('priority_id', ''),
        'cast_subscribe_id': cast_subscribe_data.get('id', ''),
        'cast_subscribe_cast_id': cast_subscribe_data.get('cast_id', ''),
        'cast_subscribe_max_coactors': cast_subscribe_data.get('max_coactors', ''),
        'cast_subscribe_max_page': cast_subscribe_data.get('max_page', ''),
        'cast_subscribe_replace_max_page': cast_subscribe_data.get('replace_max_page', ''),
        'cast_subscribe_is_single': _flag_text(cast_subscribe_data.get('is_single')),
        'cast_subscribe_earliest_release_date': cast_subscribe_data.get('earliest_release_date', ''),
        'cast_subscribe_exclude_vr': _flag_text(cast_subscribe_data.get('exclude_vr')),
        'cast_subscribe_filter_id': cast_subscribe_data.get('filter_id', ''),
        'cast_subscribe_priority_id': cast_subscribe_data.get('priority_id', ''),
        'cast_subscribe_status': cast_subscribe_data.get('status', ''),
        'cast_subscribe_create_time': cast_subscribe_data.get('create_time', ''),
        'cast_subscribe_update_time': cast_subscribe_data.get('update_time', ''),
    })
    return payload


def _build_filter_priority_push_fields(filter_obj: Filter | None, priority_obj: Priority | None) -> dict[str, Any]:
    return _build_subscribe_filter_priority_push_fields(None, filter_obj, priority_obj)


def _load_filter_priority(db: Session | None, filter_id: int | None, priority_id: int | None) -> tuple[
    Filter | None, Priority | None]:
    if db is None:
        return None, None
    filter_obj = db.get(Filter, filter_id) if filter_id else None
    priority_obj = db.get(Priority, priority_id) if priority_id else None
    return filter_obj, priority_obj


def _build_movie_subscribe_push_data(subscribe: Subscribe, movie: Movie, filter_obj: Filter | None = None,
                                     priority_obj: Priority | None = None) -> dict:
    payload = {
        "image": movie.banner
    }
    payload.update(_build_movie_push_fields(movie))
    payload.update(_build_subscribe_filter_priority_push_fields(subscribe, filter_obj, priority_obj))
    return payload


def _build_cast_subscribe_push_data(cast_subscribe: CastSubscribe, cast: Cast, filter_obj: Filter | None = None,
                                    priority_obj: Priority | None = None) -> dict:
    payload = {
        "image": cast.avatar
    }
    payload.update(_build_cast_push_fields(cast))
    payload.update(_build_cast_subscribe_filter_priority_push_fields(cast_subscribe, filter_obj, priority_obj))
    return payload


def _build_subscribe_completed_push_data(
        subscribe: Subscribe,
        movie: Movie,
        article=None,
        completion_source: str = '',
        filter_obj: Filter | None = None,
        priority_obj: Priority | None = None,
) -> dict:
    payload = {
        'completion_source': completion_source,
        'image': movie.banner
    }
    payload.update(_build_movie_push_fields(movie))
    payload.update(_build_article_push_fields(article))
    payload.update(_build_subscribe_filter_priority_push_fields(subscribe, filter_obj, priority_obj))
    return payload


def _push_movie_subscribe(subscribe: Subscribe, movie: Movie | None, db: Session | None = None):
    if movie is None:
        return
    filter_obj, priority_obj = _load_filter_priority(db, subscribe.filter_id, subscribe.priority_id)
    pushManager.send_event('movie_subscribe',
                           _build_movie_subscribe_push_data(subscribe, movie, filter_obj, priority_obj))


def _push_cast_subscribe(cast_subscribe: CastSubscribe, cast: Cast | None, db: Session | None = None):
    if cast is None:
        return
    filter_obj, priority_obj = _load_filter_priority(db, cast_subscribe.filter_id, cast_subscribe.priority_id)
    pushManager.send_event('cast_subscribe',
                           _build_cast_subscribe_push_data(cast_subscribe, cast, filter_obj, priority_obj))


def _push_subscribe_completed(
        subscribe: Subscribe,
        movie: Movie,
        article=None,
        completion_source: str = '',
        db: Session | None = None,
):
    filter_obj, priority_obj = _load_filter_priority(db, subscribe.filter_id, subscribe.priority_id)
    pushManager.send_event(
        'subscribe_completed',
        _build_subscribe_completed_push_data(subscribe, movie, article, completion_source, filter_obj, priority_obj),
    )


def _get_filter_pre_download_default(db: Session, filter_id: int | None) -> bool:
    if not filter_id:
        return False
    filter_obj = db.get(Filter, filter_id)
    return bool(filter_obj.enable_pre_download) if filter_obj else False


def _resolve_pre_download_enabled(param: SubscribeParam, db: Session, current_value: bool = False) -> bool:
    if param.pre_download_enabled is not None:
        return param.pre_download_enabled
    if param.inherit_pre_download_from_filter:
        return _get_filter_pre_download_default(db, param.filter_id)
    return current_value


def _execute_subscribe_download_async(subscribe_id: int):
    from ...scheduler.subscribe_scheduler import execute_subscribe_once

    get_runtime().require_download()
    get_runtime().check_cancelled()
    return execute_subscribe_once(subscribe_id)


def _trigger_subscribe_download_async(subscribe_id: int):
    runtime = get_runtime()
    runtime.require_download()
    return runtime.submit('执行订阅下载', _execute_subscribe_download_async, subscribe_id,
                          task_key=f'subscription-download:{subscribe_id}')


def sub_movie(param: SubscribeParam, db: Session):
    acquire_subscribe_write_lock(db)
    movie = db.get(Movie, param.movie_id)
    if not movie:
        raise ValueError('Movie not found')

    exist = db.query(Subscribe).filter(Subscribe.movie_id == param.movie_id).first()

    if exist:
        if exist.status in [SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]:
            raise ValueError('Movie already subscribed')
        if exist.status in [SubscribeStatus.CANCELED.value, SubscribeStatus.COMPLETED.value]:
            exist.filter_id = param.filter_id
            exist.priority_id = param.priority_id
            exist.pre_download_enabled = _resolve_pre_download_enabled(
                param,
                db,
                current_value=bool(exist.pre_download_enabled),
            )
            exist.status = SubscribeStatus.ACTIVE.value
            db.flush()
            _push_movie_subscribe(exist, movie, db)
            return success({'subscribe_id': exist.id})

    subscribe = Subscribe(
        movie_id=param.movie_id,
        filter_id=param.filter_id,
        priority_id=param.priority_id,
        pre_download_enabled=_resolve_pre_download_enabled(param, db),
        status=SubscribeStatus.ACTIVE.value,
    )
    db.add(subscribe)
    db.flush()
    _push_movie_subscribe(subscribe, movie, db)
    return success({'subscribe_id': subscribe.id})


def cancel_subscribe(subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    subscribe = db.get(Subscribe, subscribe_id)
    if not subscribe:
        raise ValueError('Subscribe not found')
    subscribe.status = SubscribeStatus.CANCELED.value
    return success()


def pause_subscribe(subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    subscribe = db.get(Subscribe, subscribe_id)
    if not subscribe:
        raise ValueError('Subscribe not found')
    if subscribe.status != SubscribeStatus.ACTIVE.value:
        raise ValueError('Only active subscription can be paused')
    subscribe.status = SubscribeStatus.PAUSED.value
    return success()


def update_subscribe(param: SubscribeUpdateParam, db: Session):
    acquire_subscribe_write_lock(db)
    subscribe = db.get(Subscribe, param.subscribe_id)
    if not subscribe:
        raise ValueError('Subscribe not found')
    subscribe.filter_id = param.filter_id
    subscribe.priority_id = param.priority_id
    if param.pre_download_enabled is not None:
        subscribe.pre_download_enabled = param.pre_download_enabled
    db.flush()
    return success()


def resume_subscribe(subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    subscribe = db.get(Subscribe, subscribe_id)
    if not subscribe:
        raise ValueError('Subscribe not found')
    if subscribe.status != SubscribeStatus.PAUSED.value:
        raise ValueError('Only paused subscription can resume')
    subscribe.status = SubscribeStatus.ACTIVE.value
    return success()


def execute_subscribe_download(subscribe_id: int, db: Session):
    subscribe = db.get(Subscribe, subscribe_id)
    if not subscribe:
        raise ValueError('Subscribe not found')

    db.commit()
    result = _trigger_subscribe_download_async(subscribe_id)
    return success(result, message='订阅下载已加入任务队列')


def sub_cast(param: CastSubscribeParam, db: Session):
    exist = db.query(CastSubscribe).filter(CastSubscribe.cast_id == param.cast_id).first()

    if exist:
        if exist.status in [SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]:
            raise ValueError('Cast already subscribed')
        exist.max_coactors = param.max_coactors
        exist.max_page = param.max_page
        exist.replace_max_page = param.replace_max_page
        exist.is_single = param.is_single
        exist.earliest_release_date = param.earliest_release_date
        exist.exclude_vr = param.exclude_vr
        exist.filter_id = param.filter_id
        exist.priority_id = param.priority_id
        exist.status = SubscribeStatus.ACTIVE.value
        db.flush()
        _push_cast_subscribe(exist, db.get(Cast, param.cast_id), db)
        return success({'cast_subscribe_id': exist.id})

    cast_subscribe = CastSubscribe(
        cast_id=param.cast_id,
        max_coactors=param.max_coactors,
        max_page=param.max_page,
        replace_max_page=param.replace_max_page,
        is_single=param.is_single,
        earliest_release_date=param.earliest_release_date,
        exclude_vr=param.exclude_vr,
        filter_id=param.filter_id,
        priority_id=param.priority_id,
        status=SubscribeStatus.ACTIVE.value,
    )
    db.add(cast_subscribe)
    db.flush()
    _push_cast_subscribe(cast_subscribe, db.get(Cast, param.cast_id), db)
    return success({'cast_subscribe_id': cast_subscribe.id})


def sub_general(param: GeneralSubscribeParam, db: Session):
    acquire_subscribe_write_lock(db)
    number_prefix = _normalize_general_subscribe_text(param.number_prefix, uppercase=True)
    publisher = _normalize_general_subscribe_text(param.publisher)
    series = _normalize_general_subscribe_text(param.series)
    producer = _normalize_general_subscribe_text(param.producer)
    genres = _normalize_general_subscribe_genres(param.genres)

    if not any([number_prefix, publisher, series, producer, genres]):
        raise ValueError('At least one matching condition is required')

    exist = _find_general_subscribe_by_match(
        db,
        number_prefix=number_prefix,
        publisher=publisher,
        series=series,
        producer=producer,
        genres=genres,
    )
    if exist:
        if exist.status in [SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]:
            raise ValueError('General subscribe already exists')

        exist.number_prefix = number_prefix
        exist.publisher = publisher
        exist.series = series
        exist.producer = producer
        exist.genres = genres
        exist.max_coactors = param.max_coactors
        exist.earliest_release_date = param.earliest_release_date
        exist.exclude_vr = param.exclude_vr
        exist.filter_id = param.filter_id
        exist.priority_id = param.priority_id
        exist.status = SubscribeStatus.ACTIVE.value
        db.flush()
        return success({'general_subscribe_id': exist.id})

    general_subscribe = GeneralSubscribe(
        number_prefix=number_prefix,
        publisher=publisher,
        series=series,
        producer=producer,
        genres=genres,
        max_coactors=param.max_coactors,
        earliest_release_date=param.earliest_release_date,
        exclude_vr=param.exclude_vr,
        filter_id=param.filter_id,
        priority_id=param.priority_id,
        status=SubscribeStatus.ACTIVE.value,
    )
    db.add(general_subscribe)
    db.flush()
    return success({'general_subscribe_id': general_subscribe.id})


def update_general_subscribe(param: GeneralSubscribeUpdateParam, db: Session):
    acquire_subscribe_write_lock(db)
    general_subscribe = db.get(GeneralSubscribe, param.general_subscribe_id)
    if not general_subscribe:
        raise ValueError('General subscribe not found')

    number_prefix = _normalize_general_subscribe_text(param.number_prefix, uppercase=True)
    publisher = _normalize_general_subscribe_text(param.publisher)
    series = _normalize_general_subscribe_text(param.series)
    producer = _normalize_general_subscribe_text(param.producer)
    genres = _normalize_general_subscribe_genres(param.genres)

    if not any([number_prefix, publisher, series, producer, genres]):
        raise ValueError('At least one matching condition is required')

    duplicate = _find_general_subscribe_by_match(
        db,
        number_prefix=number_prefix,
        publisher=publisher,
        series=series,
        producer=producer,
        genres=genres,
        exclude_id=general_subscribe.id,
    )
    if duplicate and duplicate.status in [SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]:
        raise ValueError('General subscribe already exists')

    general_subscribe.number_prefix = number_prefix
    general_subscribe.publisher = publisher
    general_subscribe.series = series
    general_subscribe.producer = producer
    general_subscribe.genres = genres
    general_subscribe.max_coactors = param.max_coactors
    general_subscribe.earliest_release_date = param.earliest_release_date
    general_subscribe.exclude_vr = param.exclude_vr
    general_subscribe.filter_id = param.filter_id
    general_subscribe.priority_id = param.priority_id
    db.flush()
    return success()


def cancel_general_subscribe(general_subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    general_subscribe = db.get(GeneralSubscribe, general_subscribe_id)
    if not general_subscribe:
        raise ValueError('General subscribe not found')
    general_subscribe.status = SubscribeStatus.CANCELED.value
    return success()


def pause_general_subscribe(general_subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    general_subscribe = db.get(GeneralSubscribe, general_subscribe_id)
    if not general_subscribe:
        raise ValueError('General subscribe not found')
    if general_subscribe.status != SubscribeStatus.ACTIVE.value:
        raise ValueError('Only active general subscription can be paused')
    general_subscribe.status = SubscribeStatus.PAUSED.value
    return success()


def resume_general_subscribe(general_subscribe_id: int, db: Session):
    acquire_subscribe_write_lock(db)
    general_subscribe = db.get(GeneralSubscribe, general_subscribe_id)
    if not general_subscribe:
        raise ValueError('General subscribe not found')
    if general_subscribe.status != SubscribeStatus.PAUSED.value:
        raise ValueError('Only paused general subscription can resume')
    general_subscribe.status = SubscribeStatus.ACTIVE.value
    return success()


def update_cast_subscribe(param: CastSubscribeUpdateParam, db: Session):
    cast_subscribe = db.get(CastSubscribe, param.cast_subscribe_id)
    if not cast_subscribe:
        raise ValueError('Cast subscribe not found')

    cast_subscribe.max_coactors = param.max_coactors
    cast_subscribe.max_page = param.max_page
    cast_subscribe.replace_max_page = param.replace_max_page
    cast_subscribe.is_single = param.is_single
    cast_subscribe.earliest_release_date = param.earliest_release_date
    cast_subscribe.exclude_vr = param.exclude_vr
    cast_subscribe.filter_id = param.filter_id
    cast_subscribe.priority_id = param.priority_id
    db.flush()
    return success()


def cancel_cast_subscribe(cast_subscribe_id: int, db: Session):
    cast_subscribe = db.get(CastSubscribe, cast_subscribe_id)
    if not cast_subscribe:
        raise ValueError('Cast subscribe not found')
    cast_subscribe.status = SubscribeStatus.CANCELED.value
    return success()


def pause_cast_subscribe(cast_subscribe_id: int, db: Session):
    cast_subscribe = db.get(CastSubscribe, cast_subscribe_id)
    if not cast_subscribe:
        raise ValueError('Cast subscribe not found')
    if cast_subscribe.status != SubscribeStatus.ACTIVE.value:
        raise ValueError('Only active cast subscription can be paused')
    cast_subscribe.status = SubscribeStatus.PAUSED.value
    return success()


def resume_cast_subscribe(cast_subscribe_id: int, db: Session):
    cast_subscribe = db.get(CastSubscribe, cast_subscribe_id)
    if not cast_subscribe:
        raise ValueError('Cast subscribe not found')
    if cast_subscribe.status != SubscribeStatus.PAUSED.value:
        raise ValueError('Only paused cast subscription can resume')
    cast_subscribe.status = SubscribeStatus.ACTIVE.value
    return success()


def _build_movie_items(result, db: Session):
    movie_numbers = {movie.number for _, movie in result if movie.number}
    in_library_map = {}

    for number in movie_numbers:
        get_runtime().check_cancelled()
        in_library_map[number] = mediaServerManager.any_movie_exists_by_number(number)

    cast_ids = set()
    items = []
    for sub, movie in result:
        data = movie.__dict__.copy()
        data.pop('_sa_instance_state', None)
        data['subscribe_id'] = sub.id
        data['status'] = sub.status
        data['subscribe_time'] = sub.create_time.strftime('%Y-%m-%d %H:%M:%S') if sub.create_time else ''
        data['filter_id'] = sub.filter_id
        data['priority_id'] = sub.priority_id
        data['pre_download_enabled'] = bool(sub.pre_download_enabled)
        data['in_library'] = in_library_map.get(movie.number, False)
        if movie.casts:
            cast_ids.update(movie.casts)
        items.append(data)

    cast_map = {}
    if cast_ids:
        casts = db.query(Cast).filter(Cast.id.in_(cast_ids)).all()
        cast_subscribes = (
            db.query(CastSubscribe)
            .filter(CastSubscribe.cast_id.in_(cast_ids), CastSubscribe.status.in_(['active', 'paused']))
            .order_by(CastSubscribe.id.desc())
            .all()
        )
        subscribe_map = {}
        for subscribe in cast_subscribes:
            subscribe_map.setdefault(
                subscribe.cast_id,
                {
                    'id': subscribe.id,
                    'cast_id': subscribe.cast_id,
                    'status': subscribe.status,
                    'max_coactors': subscribe.max_coactors,
                    'max_page': subscribe.max_page,
                    'replace_max_page': subscribe.replace_max_page,
                    'is_single': bool(subscribe.is_single),
                    'earliest_release_date': subscribe.earliest_release_date.isoformat() if subscribe.earliest_release_date else None,
                    'exclude_vr': bool(subscribe.exclude_vr),
                    'filter_id': subscribe.filter_id,
                    'priority_id': subscribe.priority_id,
                    'create_time': subscribe.create_time.strftime('%Y-%m-%d %H:%M:%S') if subscribe.create_time else '',
                },
            )

        cast_map = {
            c.id: {
                'id': c.id,
                'name': c.name,
                'cn_name': c.cn_name,
                'avatar': c.avatar,
                'photo': c.photo,
                'former_name': c.former_name or [],
                'subscribe': subscribe_map.get(c.id),
            }
            for c in casts
        }

    for movie in items:
        movie['casts'] = [cast_map[cid] for cid in (movie.get('casts') or []) if cid in cast_map]
    return items


def diagnose_subscription_cleanup_candidates(param: SubscribeCleanupDiagnosticParam, db: Session):
    from ...scheduler.subscribe_scheduler import _is_blacklisted_movie_keyword, _is_blacklisted_movie_number, \
        _movie_matches_general_subscribe

    include_inactive = bool(param.include_inactive)
    limit = max(1, min(int(param.limit or 20), 100))
    allowed_candidate_types = {str(item).strip() for item in (param.candidate_types or []) if str(item).strip()}

    subscribe_query = db.query(Subscribe, Movie).join(Movie, Movie.id == Subscribe.movie_id)
    cast_query = db.query(CastSubscribe, Cast).join(Cast, Cast.id == CastSubscribe.cast_id)
    general_query = db.query(GeneralSubscribe)

    if not include_inactive:
        subscribe_query = subscribe_query.filter(
            Subscribe.status.in_([SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]))
        cast_query = cast_query.filter(
            CastSubscribe.status.in_([SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]))
        general_query = general_query.filter(
            GeneralSubscribe.status.in_([SubscribeStatus.ACTIVE.value, SubscribeStatus.PAUSED.value]))

    if param.movie_id is not None:
        subscribe_query = subscribe_query.filter(Subscribe.movie_id == param.movie_id)
    if param.subscribe_id is not None:
        subscribe_query = subscribe_query.filter(Subscribe.id == param.subscribe_id)
    if param.cast_subscribe_id is not None:
        cast_query = cast_query.filter(CastSubscribe.id == param.cast_subscribe_id)
    if param.general_subscribe_id is not None:
        general_query = general_query.filter(GeneralSubscribe.id == param.general_subscribe_id)

    subscribe_rows = subscribe_query.all()
    cast_rows = cast_query.all()
    general_subscribes = general_query.all()
    preference_config = get_subscribe_preference_config(db)
    number_prefix_blacklist = preference_config.get('number_prefix_blacklist', [])
    keyword_blacklist = preference_config.get('keyword_blacklist', [])

    subscribe_by_movie_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    movie_map: dict[int, Movie] = {}
    for subscribe, movie in subscribe_rows:
        movie_map[movie.id] = movie
        subscribe_by_movie_id[movie.id].append({
            **_serialize_subscribe(subscribe),
            'movie': _serialize_movie(movie),
            'label': f"{movie.number or ''} {movie.cn_title or movie.title or ''}".strip(),
        })

    cast_coverage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for cast_subscribe, cast in cast_rows:
        query = db.query(Movie).filter(array_member(Movie.casts, cast_subscribe.cast_id))
        if cast_subscribe.earliest_release_date:
            query = query.filter(Movie.release_date >= cast_subscribe.earliest_release_date)
        for movie in query.all():
            if (
                    _is_blacklisted_movie_number(movie, number_prefix_blacklist)
                    or _is_blacklisted_movie_keyword(movie, keyword_blacklist)
            ):
                continue
            cast_total = len(movie.casts or [])
            coactor_count = max(cast_total - 1, 0)
            if cast_subscribe.max_coactors is not None and coactor_count > cast_subscribe.max_coactors:
                continue
            if cast_subscribe.exclude_vr and any(
                    'VR' in (value or '').upper() for value in [movie.number, movie.title, *(movie.genres or [])]):
                continue
            movie_map[movie.id] = movie
            cast_coverage[movie.id].append({
                **_serialize_cast_subscribe(cast_subscribe),
                'cast': _serialize_cast(cast),
                'label': cast.name,
            })

    general_coverage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    signature_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for general_subscribe in general_subscribes:
        signature_groups[_general_subscribe_signature(general_subscribe)].append({
            **_serialize_general_subscribe(general_subscribe),
            'summary': _general_subscribe_summary(general_subscribe),
        })
        query = db.query(Movie)
        if general_subscribe.number_prefix:
            query = query.filter(Movie.number.ilike(f'{general_subscribe.number_prefix}%'))
        if general_subscribe.publisher:
            query = query.filter(func.lower(func.coalesce(Movie.publisher, '')) == general_subscribe.publisher.lower())
        if general_subscribe.series:
            query = query.filter(func.lower(func.coalesce(Movie.series, '')) == general_subscribe.series.lower())
        if general_subscribe.producer:
            query = query.filter(func.lower(func.coalesce(Movie.producer, '')) == general_subscribe.producer.lower())
        if general_subscribe.genres:
            query = query.filter(Movie.genres.contains(general_subscribe.genres))
        if general_subscribe.earliest_release_date:
            query = query.filter(Movie.release_date >= general_subscribe.earliest_release_date)
        for movie in query.all():
            if (
                    _is_blacklisted_movie_number(movie, number_prefix_blacklist)
                    or _is_blacklisted_movie_keyword(movie, keyword_blacklist)
            ):
                continue
            if not _movie_matches_general_subscribe(movie, general_subscribe):
                continue
            movie_map[movie.id] = movie
            general_coverage[movie.id].append({
                **_serialize_general_subscribe(general_subscribe),
                'summary': _general_subscribe_summary(general_subscribe),
                'label': _general_subscribe_summary(general_subscribe),
            })

    items: list[dict[str, Any]] = []

    for movie_id, subscribe_items in subscribe_by_movie_id.items():
        movie = movie_map.get(movie_id)
        if movie is None:
            continue
        cast_items = cast_coverage.get(movie_id) or []
        general_items = general_coverage.get(movie_id) or []
        for subscribe_item in subscribe_items:
            if cast_items:
                items.append(_serialize_cleanup_candidate(
                    'movie_covered_by_cast',
                    'medium',
                    '该影片已被演员订阅覆盖，存在重复维护成本。',
                    'review_only',
                    movie=_serialize_movie(movie),
                    sources={'movie_subscribe': subscribe_item, 'cast_subscribes': cast_items,
                             'general_subscribes': []},
                ))
            if general_items:
                items.append(_serialize_cleanup_candidate(
                    'movie_covered_by_general',
                    'medium',
                    '该影片已被综合订阅覆盖，存在重复维护成本。',
                    'review_only',
                    movie=_serialize_movie(movie),
                    sources={'movie_subscribe': subscribe_item, 'cast_subscribes': [],
                             'general_subscribes': general_items},
                ))
            source_count = (1 if subscribe_item else 0) + (1 if cast_items else 0) + (1 if general_items else 0)
            if source_count >= 3 or (subscribe_item and cast_items and general_items):
                items.append(_serialize_cleanup_candidate(
                    'movie_multi_source_overlap',
                    'high',
                    '该影片同时被直接订阅、演员订阅和综合订阅覆盖。',
                    'review_only',
                    movie=_serialize_movie(movie),
                    sources={'movie_subscribe': subscribe_item, 'cast_subscribes': cast_items,
                             'general_subscribes': general_items},
                ))
            all_filter_ids = {str(value) for value in
                              [subscribe_item.get('filter_id'), *(item.get('filter_id') for item in cast_items),
                               *(item.get('filter_id') for item in general_items)] if value not in [None, '']}
            all_priority_ids = {str(value) for value in
                                [subscribe_item.get('priority_id'), *(item.get('priority_id') for item in cast_items),
                                 *(item.get('priority_id') for item in general_items)] if value not in [None, '']}
            pre_download_values = {bool(value) for value in [subscribe_item.get('pre_download_enabled'),
                                                             *(item.get('pre_download_enabled') for item in cast_items),
                                                             *(item.get('pre_download_enabled') for item in
                                                               general_items)] if value not in [None, '']}
            if len(all_filter_ids) > 1 or len(all_priority_ids) > 1 or len(pre_download_values) > 1:
                items.append(_serialize_cleanup_candidate(
                    'configuration_divergence',
                    'medium',
                    '覆盖同一影片的多来源订阅配置不一致。',
                    'review_only',
                    movie=_serialize_movie(movie),
                    sources={'movie_subscribe': subscribe_item, 'cast_subscribes': cast_items,
                             'general_subscribes': general_items},
                    config_divergence={
                        'filter_ids': sorted(all_filter_ids),
                        'priority_ids': sorted(all_priority_ids),
                        'pre_download_values': sorted(pre_download_values),
                    },
                ))

    for signature, group_items in signature_groups.items():
        if len(group_items) < 2:
            continue
        items.append(_serialize_cleanup_candidate(
            'general_duplicate_signature',
            'high',
            '归一化后的综合订阅条件相同，存在重复规则。',
            'review_only',
            signature=_serialize_general_signature(signature),
            sources={'general_subscribes': group_items},
        ))

    if allowed_candidate_types:
        items = [item for item in items if item.get('candidate_type') in allowed_candidate_types]

    counts = Counter(str(item.get('candidate_type') or '') for item in items)
    return success({
        'diagnostic_only': True,
        'summary': {
            'movie_subscribe_count': len(subscribe_rows),
            'cast_subscribe_count': len(cast_rows),
            'general_subscribe_count': len(general_subscribes),
            'candidate_count': len(items),
            'candidate_counts_by_type': dict(counts),
        },
        'items': items[:limit],
    })


def list_subscribe(param: SubscribePageParam, db: Session):
    query = db.query(Subscribe, Movie).join(Movie, Movie.id == Subscribe.movie_id)

    if param.status:
        query = query.filter(Subscribe.status == param.status.value)

    if param.release_date_start:
        query = query.filter(Movie.release_date >= param.release_date_start)

    if param.release_date_end:
        query = query.filter(Movie.release_date <= param.release_date_end)

    if param.keyword:
        keyword = f'%{param.keyword}%'
        cast_keyword_exists = exists().where(
            array_member(Movie.casts, Cast.id),
            or_(
                Cast.name.ilike(keyword),
                Cast.cn_name.ilike(keyword),
                array_to_string(Cast.former_name, ' ').ilike(keyword),
            ),
        )
        query = query.filter(
            or_(
                Movie.title.ilike(keyword),
                Movie.cn_title.ilike(keyword),
                Movie.description.ilike(keyword),
                Movie.cn_description.ilike(keyword),
                Movie.number.ilike(keyword),
                cast_keyword_exists,
            )
        )

    total = query.count()
    offset = (param.page - 1) * param.page_size
    if param.release_date_start or param.release_date_end:
        query = query.order_by(Movie.release_date.asc().nullslast(), Subscribe.id.desc())
    else:
        query = query.order_by(Subscribe.id.desc())
    result = query.offset(offset).limit(param.page_size).all()
    items = _build_movie_items(result, db)

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(result) < total,
    })


def list_general_subscribe(param: GeneralSubscribePageParam, db: Session):
    query = db.query(GeneralSubscribe)

    if param.status:
        query = query.filter(GeneralSubscribe.status == param.status.value)

    if param.keyword:
        keyword = f'%{param.keyword}%'
        query = query.filter(
            or_(
                GeneralSubscribe.number_prefix.ilike(keyword),
                GeneralSubscribe.publisher.ilike(keyword),
                GeneralSubscribe.series.ilike(keyword),
                GeneralSubscribe.producer.ilike(keyword),
                array_to_string(GeneralSubscribe.genres, ' ').ilike(keyword),
            )
        )

    total = query.count()
    offset = (param.page - 1) * param.page_size
    rows = query.order_by(GeneralSubscribe.id.desc()).offset(offset).limit(param.page_size).all()

    items = []
    for general_subscribe in rows:
        items.append({
            'id': general_subscribe.id,
            'number_prefix': general_subscribe.number_prefix,
            'publisher': general_subscribe.publisher,
            'series': general_subscribe.series,
            'producer': general_subscribe.producer,
            'genres': general_subscribe.genres or [],
            'max_coactors': general_subscribe.max_coactors,
            'earliest_release_date': general_subscribe.earliest_release_date.isoformat() if general_subscribe.earliest_release_date else None,
            'exclude_vr': bool(general_subscribe.exclude_vr),
            'filter_id': general_subscribe.filter_id,
            'priority_id': general_subscribe.priority_id,
            'status': general_subscribe.status,
            'create_time': general_subscribe.create_time.strftime(
                '%Y-%m-%d %H:%M:%S') if general_subscribe.create_time else '',
        })

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(rows) < total,
    })


def list_cast_subscribe(param: CastSubscribePageParam, db: Session):
    query = db.query(CastSubscribe, Cast).join(Cast, Cast.id == CastSubscribe.cast_id)

    if param.status:
        query = query.filter(CastSubscribe.status == param.status.value)

    if param.keyword:
        keyword = f'%{param.keyword}%'
        query = query.filter(or_(Cast.name.ilike(keyword), Cast.cn_name.ilike(keyword)))

    total = query.count()
    offset = (param.page - 1) * param.page_size
    rows = query.order_by(CastSubscribe.id.desc()).offset(offset).limit(param.page_size).all()

    items = []
    for cast_subscribe, cast in rows:
        items.append({
            'id': cast.id,
            'name': cast.name,
            'cn_name': cast.cn_name,
            'avatar': cast.avatar,
            'photo': cast.photo,
            'former_name': cast.former_name or [],
            'subscribe': {
                'id': cast_subscribe.id,
                'cast_id': cast_subscribe.cast_id,
                'status': cast_subscribe.status,
                'max_coactors': cast_subscribe.max_coactors,
                'max_page': cast_subscribe.max_page,
                'replace_max_page': cast_subscribe.replace_max_page,
                'is_single': bool(cast_subscribe.is_single),
                'earliest_release_date': cast_subscribe.earliest_release_date.isoformat() if cast_subscribe.earliest_release_date else None,
                'exclude_vr': bool(cast_subscribe.exclude_vr),
                'filter_id': cast_subscribe.filter_id,
                'priority_id': cast_subscribe.priority_id,
                'create_time': cast_subscribe.create_time.strftime(
                    '%Y-%m-%d %H:%M:%S') if cast_subscribe.create_time else '',
            },
        })

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(rows) < total,
    })
