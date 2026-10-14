from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ...models import RankMovie, Movie, Subscribe, Cast, CastSubscribe, RankCast
from ...core.portable_types import array_position
from ...core.runtime import check_cancelled
from ...modules.mediaserver import mediaServerManager
from ...schemas.response import success

RANK_MOVIE_PAGE_SIZE = 25


def _build_cast_map(db: Session, cast_ids: set[int]):
    if not cast_ids:
        return {}

    casts = (
        db.query(Cast)
        .filter(Cast.id.in_(cast_ids))
        .all()
    )
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
            "id": c.id,
            "name": c.name,
            "cn_name": c.cn_name,
            "avatar": c.avatar,
            "photo": c.photo,
            "former_name": c.former_name or [],
            'subscribe': subscribe_map.get(c.id),
        }
        for c in casts
    }


def _build_cast_rank_items(db: Session, cast_ids: list[int]) -> list[dict]:
    cast_map = _build_cast_map(db, set(cast_ids))
    items = []
    for cast_id in cast_ids:
        cast = cast_map.get(cast_id)
        if not cast:
            continue
        items.append({
            'id': cast['id'],
            'name': cast['name'],
            'cn_name': cast['cn_name'],
            'avatar': cast['avatar'],
            'photo': cast['photo'],
            'former_name': cast['former_name'],
            'subscribe': cast.get('subscribe'),
        })
    return items


def _build_share_cast_rank_items(db: Session, cast_ids: list[int]) -> list[dict]:
    cast_map = _build_cast_map(db, set(cast_ids))
    items = []
    for cast_id in cast_ids:
        cast = cast_map.get(cast_id)
        if not cast:
            continue
        items.append({
            'cast': {
                'id': cast['id'],
                'name': cast['name'],
                'cn_name': cast['cn_name'],
                'avatar': cast['avatar'] or cast['photo'],
                'photo': cast['photo'],
                'former_name': cast['former_name'],
                'subscribe': cast.get('subscribe'),
            },
        })
    return items


def rank_movie(db: Session, rank_name, page: int = 1, library_filter: str = 'all'):
    rank = (
        db.query(RankMovie)
        .filter(RankMovie.rank_name == rank_name)
        .order_by(RankMovie.create_time.desc())
        .first()
    )

    current_page = max(int(page or 1), 1)
    normalized_library_filter = str(library_filter or 'all').strip().lower()
    if normalized_library_filter not in {'all', 'in', 'out'}:
        normalized_library_filter = 'all'

    empty_payload = {
        "movies": [],
        "sync_time": rank.create_time.strftime("%Y-%m-%d %H:%M:%S") if rank else "",
        "page": current_page,
        "pageSize": RANK_MOVIE_PAGE_SIZE,
        "total": 0,
        "totalPages": 0,
    }

    if not rank or not rank.movie_ids:
        return success(empty_payload)

    stmt = (
        select(
            Movie,
            Subscribe.id.label("subscribe_id"),
            Subscribe.filter_id.label("filter_id"),
            Subscribe.priority_id.label("priority_id"),
            Subscribe.pre_download_enabled.label("pre_download_enabled"),
            func.coalesce(Subscribe.status, "released").label("status")
        )
        .outerjoin(
            Subscribe,
            Subscribe.movie_id == Movie.id
        )
        .where(Movie.id.in_(rank.movie_ids))
        .order_by(array_position(rank.movie_ids, Movie.id))
    )

    rows = db.execute(stmt).all()
    if not rows:
        return success(empty_payload)

    if normalized_library_filter == 'all':
        page_start = (current_page - 1) * RANK_MOVIE_PAGE_SIZE
        page_end = page_start + RANK_MOVIE_PAGE_SIZE
        selected_rows = rows[page_start:page_end]
    else:
        movie_numbers = {
            movie.number
            for movie, *_ in rows
            if movie and movie.number
        }
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

        filtered_rows = []
        for row in rows:
            movie = row[0]
            if movie is None:
                continue
            in_library = in_library_map.get(movie.number, False)
            if normalized_library_filter == 'in' and not in_library:
                continue
            if normalized_library_filter == 'out' and in_library:
                continue
            filtered_rows.append(row)

        rows = filtered_rows
        page_start = (current_page - 1) * RANK_MOVIE_PAGE_SIZE
        page_end = page_start + RANK_MOVIE_PAGE_SIZE
        selected_rows = rows[page_start:page_end]

    total = len(rows)
    total_pages = (total + RANK_MOVIE_PAGE_SIZE - 1) // RANK_MOVIE_PAGE_SIZE
    if total_pages > 0 and current_page > total_pages:
        current_page = total_pages
        page_start = (current_page - 1) * RANK_MOVIE_PAGE_SIZE
        page_end = page_start + RANK_MOVIE_PAGE_SIZE
        selected_rows = rows[page_start:page_end]

    movie_numbers = {
        movie.number
        for movie, *_ in selected_rows
        if movie and movie.number
    }
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

    movies = []
    cast_ids = set()

    for movie, subscribe_id, filter_id, priority_id, pre_download_enabled, status in selected_rows:
        if not movie:
            continue

        data = movie.__dict__.copy()
        data.pop("_sa_instance_state", None)
        data["status"] = status
        data["subscribe_id"] = subscribe_id
        data["filter_id"] = filter_id
        data["priority_id"] = priority_id
        data["pre_download_enabled"] =  bool(pre_download_enabled)
        data["in_library"] = in_library_map.get(movie.number, False)

        if movie.casts:
            cast_ids.update(movie.casts)

        movies.append(data)

    cast_map = _build_cast_map(db, cast_ids)

    for movie in movies:
        movie["casts"] = [
            cast_map[cid]
            for cid in (movie.get("casts") or [])
            if cid in cast_map
        ]

    return success({
        "movies": movies,
        "sync_time": rank.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        "page": current_page,
        "pageSize": RANK_MOVIE_PAGE_SIZE,
        "total": total,
        "totalPages": total_pages,
    })


def rank_cast(db: Session, rank_name):
    rank = (
        db.query(RankCast)
        .filter(RankCast.rank_name == rank_name)
        .order_by(RankCast.create_time.desc())
        .first()
    )

    if not rank or not rank.cast_ids:
        return success({
            "casts": [],
            "sync_time": ""
        })

    return success({
        "casts": _build_cast_rank_items(db, rank.cast_ids),
        "sync_time": rank.create_time.strftime("%Y-%m-%d %H:%M:%S")
    })


def _serialize_movie_rank(db: Session, rank: RankMovie) -> dict:
    numbers = list(db.execute(
        select(Movie.number)
        .where(Movie.id.in_(rank.movie_ids))
        .order_by(array_position(rank.movie_ids, Movie.id))
    ).scalars())
    ordered_numbers = [number for number in numbers if number]

    return {
        "rank_type": "movie",
        "rank_name": rank.rank_name,
        "numbers": ordered_numbers,
        "count": len(ordered_numbers),
        "sync_time": rank.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _serialize_cast_rank(db: Session, rank: RankCast) -> dict:
    ordered_casts = _build_share_cast_rank_items(db, rank.cast_ids)

    return {
        "rank_type": "cast",
        "rank_name": rank.rank_name,
        "casts": ordered_casts,
        "count": len(ordered_casts),
        "sync_time": rank.create_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _latest_movie_ranks(db: Session) -> list[RankMovie]:
    rows = (
        db.query(RankMovie)
        .order_by(RankMovie.create_time.desc(), RankMovie.id.desc())
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault(row.rank_name, row)
    return list(latest.values())


def _latest_cast_ranks(db: Session) -> list[RankCast]:
    rows = (
        db.query(RankCast)
        .order_by(RankCast.create_time.desc(), RankCast.id.desc())
        .all()
    )
    latest = {}
    for row in rows:
        latest.setdefault(row.rank_name, row)
    return list(latest.values())


def share_rank(db: Session, rank_name: str | None = None, rank_type: str | None = None):
    normalized_rank_type = (rank_type or '').strip().lower()
    normalized_rank_name = (rank_name or '').strip()

    ranks: list[dict] = []

    if normalized_rank_type in {'', 'movie'}:
        for row in _latest_movie_ranks(db):
            if normalized_rank_name and row.rank_name != normalized_rank_name:
                continue
            if not row.movie_ids:
                continue
            ranks.append(_serialize_movie_rank(db, row))

    if normalized_rank_type in {'', 'cast'}:
        for row in _latest_cast_ranks(db):
            if normalized_rank_name and row.rank_name != normalized_rank_name:
                continue
            if not row.cast_ids:
                continue
            ranks.append(_serialize_cast_rank(db, row))

    ranks.sort(key=lambda item: (item.get('rank_type') != 'movie', item.get('rank_name') or ''))
    sync_time = max((item.get('sync_time') or '' for item in ranks), default='')

    return success({
        'ranks': ranks,
        'count': len(ranks),
        'sync_time': sync_time,
    })


def share_rank_movie_numbers(db: Session, rank_name: str):
    return share_rank(db, rank_name, rank_type='movie')


def share_rank_casts(db: Session, rank_name: str):
    return share_rank(db, rank_name, rank_type='cast')
