from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session

from ...enums import SubscribeStatus
from ...core.portable_types import array_any_ilike, array_member
from ...core.runtime import check_cancelled
from ...models import Cast, CastSubscribe, Movie, Subscribe
from ...modules.crawler.avbase import av_base
from ...modules.crawler.javdb import javdb
from ...modules.mediaserver import mediaServerManager
from ...schemas.movie import MovieRecommendParam, MovieSearchParam
from ...schemas.response import success
from ...scheduler.movie_scheduler import sync_casts, upsert_movie

RECOMMEND_SEED_STATUSES = (
    SubscribeStatus.ACTIVE.value,
    SubscribeStatus.PAUSED.value,
    SubscribeStatus.COMPLETED.value,
)


def _build_cast_map(db: Session, cast_ids: set[int]):
    if not cast_ids:
        return {}

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

    return {
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



def _build_movie_search_items(rows, db: Session):
    movie_numbers = {movie.number for movie, _ in rows if movie and movie.number}
    in_library_map = {}

    if movie_numbers:
        max_workers = min(8, len(movie_numbers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_number = {
                executor.submit(copy_context().run, mediaServerManager.any_movie_exists_by_number, number): number
                for number in movie_numbers
            }
            for future in as_completed(future_to_number):
                number = future_to_number[future]
                check_cancelled()
                in_library_map[number] = future.result()

    cast_ids = set()
    items = []
    for movie, subscribe in rows:
        if not movie:
            continue
        data = movie.__dict__.copy()
        data.pop('_sa_instance_state', None)
        if subscribe:
            data['status'] = subscribe.status
            data['subscribe_id'] = subscribe.id
            data['subscribe_time'] = subscribe.create_time.strftime('%Y-%m-%d %H:%M:%S') if subscribe.create_time else ''
            data['filter_id'] = subscribe.filter_id
            data['priority_id'] = subscribe.priority_id
            data['pre_download_enabled'] = bool(subscribe.pre_download_enabled)
        else:
            data['status'] = 'released'
            data['subscribe_id'] = None
            data['subscribe_time'] = ''
            data['filter_id'] = None
            data['priority_id'] = None
            data['pre_download_enabled'] = None
        data['in_library'] = in_library_map.get(movie.number, False)
        if movie.casts:
            cast_ids.update(movie.casts)
        items.append(data)

    cast_map = _build_cast_map(db, cast_ids)

    for movie in items:
        movie['casts'] = [cast_map[cid] for cid in (movie.get('casts') or []) if cid in cast_map]
    return items


def _build_movie_list_items(movies: list[Movie], db: Session):
    return _build_movie_search_items([(movie, None) for movie in movies], db)


def _deduplicate_movies(movies: list[dict]) -> list[dict]:
    items = []
    seen_numbers = set()
    for movie in movies or []:
        number = (movie or {}).get('number')
        if not number or number in seen_numbers:
            continue
        seen_numbers.add(number)
        items.append(movie)
    return items


def _save_movies_from_network(
    db: Session,
    movies: list[dict],
    casts: list[dict],
    include_items: bool = False,
):
    movies = _deduplicate_movies(movies)
    if not movies:
        return {
            'saved_count': 0,
            'items': [],
        }

    sync_casts(db, casts or [])
    for movie in movies:
        upsert_movie(db, movie)
    db.flush()

    saved_count = len(movies)
    if not include_items:
        return {
            'saved_count': saved_count,
            'items': [],
        }

    ordered_numbers = [movie.get('number') for movie in movies if movie.get('number')]
    rows = (
        db.query(Movie, Subscribe)
        .outerjoin(Subscribe, Subscribe.movie_id == Movie.id)
        .filter(Movie.number.in_(ordered_numbers))
        .all()
    )
    items = _build_movie_search_items(rows, db)
    order_map = {number: index for index, number in enumerate(ordered_numbers)}
    items.sort(key=lambda item: order_map.get(item.get('number'), len(order_map)))
    return {
        'saved_count': saved_count,
        'items': items,
    }


def _build_movie_keyword_filter(keyword: str):
    cast_keyword_exists = exists().where(
        array_member(Movie.casts, Cast.id),
        or_(
            Cast.name.ilike(keyword),
            Cast.cn_name.ilike(keyword),
            array_any_ilike(Cast.former_name, keyword)
        ),
    )
    return or_(
        Movie.title.ilike(keyword),
        Movie.cn_title.ilike(keyword),
        Movie.description.ilike(keyword),
        Movie.cn_description.ilike(keyword),
        Movie.number.ilike(keyword),
        Movie.series.ilike(keyword),
        Movie.producer.ilike(keyword),
        Movie.publisher.ilike(keyword),
        array_any_ilike(Movie.genres, keyword),
        cast_keyword_exists,
    )


def _collect_recommend_profile(seed_movies: list[Movie]):
    profile = {
        'movie_ids': set(),
        'casts': Counter(),
        'genres': Counter(),
        'series': Counter(),
        'producers': Counter(),
        'publishers': Counter(),
    }

    for movie in seed_movies:
        profile['movie_ids'].add(movie.id)
        profile['casts'].update(movie.casts or [])
        profile['genres'].update(movie.genres or [])
        if movie.series:
            profile['series'].update([movie.series])
        if movie.producer:
            profile['producers'].update([movie.producer])
        if movie.publisher:
            profile['publishers'].update([movie.publisher])

    return profile


def _build_recommend_candidate_filter(profile: dict):
    clauses = []

    cast_ids = list(profile['casts'].keys())
    if cast_ids:
        clauses.append(Movie.casts.overlap(cast_ids))

    genres = list(profile['genres'].keys())
    if genres:
        clauses.append(Movie.genres.overlap(genres))

    series_list = list(profile['series'].keys())
    if series_list:
        clauses.append(Movie.series.in_(series_list))

    producers = list(profile['producers'].keys())
    if producers:
        clauses.append(Movie.producer.in_(producers))

    publishers = list(profile['publishers'].keys())
    if publishers:
        clauses.append(Movie.publisher.in_(publishers))

    if not clauses:
        return None
    return or_(*clauses)


def _score_recommended_movie(movie: Movie, profile: dict):
    score = 0

    shared_casts = set(movie.casts or []) & set(profile['casts'].keys())
    for cast_id in shared_casts:
        score += 6 + min(profile['casts'][cast_id] - 1, 2)

    shared_genres = set(movie.genres or []) & set(profile['genres'].keys())
    for genre in shared_genres:
        score += 2 + min(profile['genres'][genre] - 1, 1)

    if movie.series and movie.series in profile['series']:
        score += 8 + min(profile['series'][movie.series] - 1, 2)

    if movie.producer and movie.producer in profile['producers']:
        score += 4 + min(profile['producers'][movie.producer] - 1, 2)

    if movie.publisher and movie.publisher in profile['publishers']:
        score += 3 + min(profile['publishers'][movie.publisher] - 1, 2)

    return score


def _movie_sort_date_value(movie: Movie):
    if movie.release_date is None:
        return 0
    return movie.release_date.toordinal()


def _top_counter_items(counter: Counter, limit: int = 10):
    return [
        {'name': str(name), 'count': count}
        for name, count in counter.most_common(limit)
        if name
    ]


def get_movie_frequency_stats(db: Session):
    rows = (
        db.query(Movie.casts, Movie.producer, Movie.series)
        .join(Subscribe, Subscribe.movie_id == Movie.id)
        .filter(Subscribe.status.in_(RECOMMEND_SEED_STATUSES))
        .distinct()
        .all()
    )

    cast_counter = Counter()
    producer_counter = Counter()
    series_counter = Counter()

    for casts, producer, series in rows:
        if casts:
            cast_counter.update(cast_id for cast_id in casts if cast_id)
        if producer:
            producer_counter.update([producer])
        if series:
            series_counter.update([series])

    top_cast_ids = [cast_id for cast_id, _ in cast_counter.most_common(10)]
    cast_info_map = {}
    if top_cast_ids:
        casts = db.query(Cast).filter(Cast.id.in_(top_cast_ids)).all()
        cast_info_map = {
            cast.id: {
                'name': cast.cn_name or cast.name or str(cast.id),
                'avatar': cast.avatar or cast.photo or '',
            }
            for cast in casts
        }

    subscribe_map = {}
    if top_cast_ids:
        cast_subscribes = (
            db.query(CastSubscribe)
            .filter(CastSubscribe.cast_id.in_(top_cast_ids), CastSubscribe.status.in_(['active', 'paused']))
            .order_by(CastSubscribe.id.desc())
            .all()
        )
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

    actor_items = [
        {
            'id': cast_id,
            'name': cast_info_map.get(cast_id, {}).get('name', str(cast_id)),
            'count': count,
            'avatar': cast_info_map.get(cast_id, {}).get('avatar', ''),
            'subscribe': subscribe_map.get(cast_id),
        }
        for cast_id, count in cast_counter.most_common(10)
        if cast_info_map.get(cast_id, {}).get('name', str(cast_id))
    ]

    return success({
        'actors': actor_items,
        'producers': _top_counter_items(producer_counter),
        'series': _top_counter_items(series_counter),
    })


def search_movies(param: MovieSearchParam, db: Session):
    query = db.query(Movie, Subscribe).outerjoin(Subscribe, Subscribe.movie_id == Movie.id)

    if param.keyword:
        keyword = f'%{param.keyword}%'
        query = query.filter(_build_movie_keyword_filter(keyword))

    total = query.count()
    offset = (param.page - 1) * param.page_size
    rows = query.order_by(Movie.id.desc()).offset(offset).limit(param.page_size).all()
    items = _build_movie_search_items(rows, db)

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(rows) < total,
    })


def recommend_subscribed_movies(param: MovieRecommendParam, db: Session):
    seed_movies = (
        db.query(Movie)
        .join(Subscribe, Subscribe.movie_id == Movie.id)
        .filter(Subscribe.status.in_(RECOMMEND_SEED_STATUSES))
        .all()
    )
    if not seed_movies:
        return success({
            'page': param.page,
            'pageSize': param.page_size,
            'total': 0,
            'items': [],
            'hasMore': False,
        })

    profile = _collect_recommend_profile(seed_movies)
    candidate_filter = _build_recommend_candidate_filter(profile)
    if candidate_filter is None:
        return success({
            'page': param.page,
            'pageSize': param.page_size,
            'total': 0,
            'items': [],
            'hasMore': False,
        })

    excluded_movie_ids = {movie_id for (movie_id,) in db.query(Subscribe.movie_id).all() if movie_id}
    candidate_query = db.query(Movie).filter(candidate_filter)
    if excluded_movie_ids:
        candidate_query = candidate_query.filter(~Movie.id.in_(excluded_movie_ids))

    candidate_movies = candidate_query.all()
    scored_movies = []
    for movie in candidate_movies:
        if len(movie.casts or []) >= 5:
            continue
        score = _score_recommended_movie(movie, profile)
        if score <= 0:
            continue
        scored_movies.append((movie, score))

    scored_movies.sort(
        key=lambda item: (
            item[1],
            _movie_sort_date_value(item[0]),
            item[0].create_time.timestamp() if item[0].create_time else 0,
        ),
        reverse=True,
    )

    total = len(scored_movies)
    offset = (param.page - 1) * param.page_size
    page_movies = [movie for movie, _ in scored_movies[offset: offset + param.page_size]]
    items = _build_movie_list_items(page_movies, db)

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(page_movies) < total,
    })




def network_search_movies(param: MovieSearchParam, db: Session):
    keyword = (param.keyword or '').strip()
    if not keyword:
        raise ValueError('Keyword is required')

    movies, casts = av_base.get_movie(keyword)
    source = 'avbase'

    if not movies:
        movies, casts = javdb.get_movie(keyword)
        source = 'javdb'

    save_result = _save_movies_from_network(db, movies, casts, include_items=True)
    items = save_result.get('items') or []
    total = len(items)
    offset = (param.page - 1) * param.page_size
    paged_items = items[offset: offset + param.page_size]
    saved_count = int(save_result.get('saved_count') or 0)

    return success({
        'keyword': keyword,
        'found': total > 0,
        'savedCount': saved_count,
        'source': source if total > 0 else None,
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': paged_items,
        'hasMore': offset + len(paged_items) < total,
    })
