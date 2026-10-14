from typing import Dict

from sqlalchemy import or_
from ..core.database import insert
from sqlalchemy.orm import Session

from ..core.database import session_scope
from ..models.cast import Cast
from ..models.movie import Movie
from ..modules.crawler.avbase import av_base
from ..modules.crawler.javdb import javdb
from ..utils import logger
from ..utils.db_lock import acquire_cast_movie_write_lock
from ..utils.wrapper import task_monitor


def get_incomplete_movies(db: Session) -> list[type[Movie]]:
    return (
        db.query(Movie)
        .filter(
            or_(
                Movie.title.is_(None),
                Movie.release_date.is_(None),
                Movie.banner.is_(None),
                Movie.casts.is_(None),
                Movie.cast_names.is_(None),
            )
        )
        .all()
    )


def _collect_cast_aliases(cast: dict) -> list[str]:
    values = [cast.get('name'), *(cast.get('former_name') or [])]
    aliases = []
    seen = set()
    for value in values:
        alias = (value or '').strip()
        if not alias:
            continue
        lowered = alias.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        aliases.append(alias)
    return aliases


def _deduplicate_api_casts(api_casts: list[dict]) -> list[dict]:
    deduplicated: dict[str, dict] = {}

    for cast in api_casts or []:
        name = (cast.get('name') or '').strip()
        if not name:
            continue

        current = deduplicated.get(name)
        if current is None:
            deduplicated[name] = {
                'name': name,
                'former_name': list(cast.get('former_name') or []),
                'avatar': cast.get('avatar'),
            }
            continue

        for alias in _collect_cast_aliases(cast):
            if alias not in current['former_name']:
                current['former_name'].append(alias)
        if not current.get('avatar') and cast.get('avatar'):
            current['avatar'] = cast.get('avatar')

    return list(deduplicated.values())


def _merge_cast_payload(base: dict, extra: dict | None) -> dict:
    if not extra:
        return base
    merged = {
        'name': (extra.get('name') or base.get('name') or '').strip() or base.get('name'),
        'former_name': [],
        'avatar': extra.get('avatar') or base.get('avatar'),
    }
    for alias in _collect_cast_aliases(base) + _collect_cast_aliases(extra):
        if alias not in merged['former_name']:
            merged['former_name'].append(alias)
    return merged


def _find_existing_cast_by_aliases(db: Session, aliases: list[str]) -> Cast | None:
    aliases = [alias for alias in aliases if alias]
    if not aliases:
        return None
    return (
        db.query(Cast)
        .filter(
            or_(
                Cast.name.in_(aliases),
                Cast.former_name.overlap(aliases),
            )
        )
        .order_by(Cast.id.asc())
        .first()
    )


def sync_casts(db: Session, api_casts: list[dict]):
    api_casts = _deduplicate_api_casts(api_casts)
    if not api_casts:
        return

    acquire_cast_movie_write_lock(db)

    all_aliases = []
    for item in api_casts:
        all_aliases.extend(_collect_cast_aliases(item))

    existing_casts = []
    if all_aliases:
        existing_casts = (
            db.query(Cast)
            .filter(
                or_(
                    Cast.name.in_(all_aliases),
                    Cast.former_name.overlap(all_aliases),
                )
            )
            .order_by(Cast.id.asc())
            .all()
        )

    alias_to_cast: dict[str, Cast] = {}
    for cast in existing_casts:
        for alias in [cast.name, cast.cn_name, *(cast.former_name or [])]:
            normalized = (alias or '').strip().lower()
            if normalized and normalized not in alias_to_cast:
                alias_to_cast[normalized] = cast

    payloads = []
    for item in api_casts:
        name = (item.get('name') or '').strip()
        if not name:
            continue

        aliases = _collect_cast_aliases(item)
        existing_cast = None
        for alias in aliases:
            existing_cast = alias_to_cast.get(alias.lower())
            if existing_cast is not None:
                break

        if existing_cast is None and not item.get('_avbase_checked'):
            talent = av_base.get_talent(name, fallback_avatar=item.get('avatar'))
            if not talent:
                logger.info(f'演员未命中 AvBase，按现有信息保存演员 | name={name}')
            else:
                item = _merge_cast_payload(item, talent)
                item['_avbase_checked'] = True
                aliases = _collect_cast_aliases(item)
                existing_cast = _find_existing_cast_by_aliases(db, aliases)
                if existing_cast is not None:
                    for alias in [existing_cast.name, *(existing_cast.former_name or [])]:
                        normalized = (alias or '').strip().lower()
                        if normalized:
                            alias_to_cast[normalized] = existing_cast

        if existing_cast is None:
            payloads.append(
                {
                    'name': item.get('name'),
                    'former_name': list(item.get('former_name') or []),
                    'avatar': item.get('avatar'),
                }
            )
            continue

        merged_aliases = list(existing_cast.former_name or [])
        for alias in aliases:
            if alias not in merged_aliases:
                merged_aliases.append(alias)
        existing_cast.former_name = merged_aliases
        if not existing_cast.avatar and item.get('avatar'):
            existing_cast.avatar = item.get('avatar')

        for alias in [existing_cast.name, *(existing_cast.former_name or [])]:
            normalized = (alias or '').strip().lower()
            if normalized:
                alias_to_cast[normalized] = existing_cast

    if payloads:
        stmt = insert(Cast).values(payloads)
        db.execute(
            stmt.on_conflict_do_nothing(
                index_elements=[Cast.name],
            )
        )
    db.flush()




def _should_update_movie_field(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    # if isinstance(value, (list, tuple, set)):
    #     return len(value) > 0
    return True



def upsert_movie(db: Session, movie: Dict):
    if not movie:
        return

    acquire_cast_movie_write_lock(db)

    payload = dict(movie)
    number = payload.get('number')
    if not number:
        return

    all_cast_names = [(name or '').strip() for name in (payload.get('cast_names') or []) if (name or '').strip()]

    cast_id_by_name: dict[str, int] = {}
    if all_cast_names:
        for cast in (
                db.query(Cast)
                        .filter(
                            or_(
                                Cast.name.in_(all_cast_names),
                                Cast.former_name.overlap(all_cast_names),
                            )
                        )
                        .order_by(Cast.id.asc())
                        .all()
        ):
            for alias in [cast.name, *(cast.former_name or [])]:
                alias_name = (alias or '').strip()
                if alias_name and alias_name not in cast_id_by_name:
                    cast_id_by_name[alias_name] = cast.id

    db_cast_ids: list[int] = []
    seen: set[int] = set()

    for cast_name in all_cast_names:
        cast_id = cast_id_by_name.get(cast_name)
        if not cast_id or cast_id in seen:
            continue
        seen.add(cast_id)
        db_cast_ids.append(cast_id)

    payload['casts'] = db_cast_ids

    exist_movie = db.query(Movie).filter(Movie.number == number).first()
    if exist_movie is None:
        stmt = insert(Movie).values(**payload)
        db.execute(
            stmt.on_conflict_do_nothing(
                index_elements=[Movie.number],
            )
        )
        return

    for field, value in payload.items():
        if field == 'number':
            continue
        if not _should_update_movie_field(value):
            continue
        setattr(exist_movie, field, value)


def _movie_needs_fallback(movie: dict | None, has_casts: bool) -> bool:
    if not movie:
        return True
    return not all([
        movie.get('title'),
        movie.get('release_date'),
        movie.get('banner'),
        has_casts,
    ])


def _merge_movie(primary_movie: dict | None, fallback_movie: dict | None) -> dict | None:
    if primary_movie is None:
        return fallback_movie
    if fallback_movie is None:
        return primary_movie

    merged = dict(primary_movie)
    for key in [
        'title',
        'release_date',
        'duration',
        'poster',
        'banner',
        'still_photos',
        'series',
        'producer',
        'publisher',
    ]:
        if not merged.get(key) and fallback_movie.get(key):
            merged[key] = fallback_movie.get(key)

    return merged


def _ensure_cast_names(movie: dict | None, api_casts: list[dict]):
    if movie is None or movie.get('cast_names'):
        return
    names = []
    for cast in api_casts or []:
        name = (cast.get('name') or '').strip()
        if name and name not in names:
            names.append(name)
    if names:
        movie['cast_names'] = names


@task_monitor
def sync_movies():
    logger.info('开始执行影片元数据补全任务')
    with session_scope() as session:
        incomplete_movies = get_incomplete_movies(session)

    if not incomplete_movies:
        logger.info('影片元数据补全任务结束，无待补全影片')
        return {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'message': '无待补全影片',
        }

    logger.info(f'待补全影片数量 | count={len(incomplete_movies)}')
    completed_count = 0

    for incomplete_movie in incomplete_movies:
        number = incomplete_movie.number
        logger.info(f'开始补全 {number} 的信息')

        avbase_movies, avbase_casts = av_base.get_movie(number)
        primary_movie = avbase_movies[0] if avbase_movies else None
        combined_casts = list(avbase_casts or [])

        if _movie_needs_fallback(primary_movie, bool(combined_casts)):
            logger.info(f'AvBase 信息不足，尝试使用 JavDB 兜底 | number={number}')
            javdb_movies, javdb_casts = javdb.get_movie(number)
            fallback_movie = javdb_movies[0] if javdb_movies else None
            primary_movie = _merge_movie(primary_movie, fallback_movie)
            combined_casts.extend(javdb_casts or [])

        _ensure_cast_names(primary_movie, combined_casts)

        if not primary_movie:
            logger.warning(f'影片元数据补全失败，未抓到有效信息 | number={number}')
            continue

        with session_scope() as session:
            sync_casts(session, combined_casts)
            upsert_movie(session, primary_movie)
        completed_count += 1
        logger.info(f'影片元数据补全完成 | number={number}')

    logger.info(f'影片元数据补全任务结束 | total={len(incomplete_movies)}, completed={completed_count}, failed={len(incomplete_movies) - completed_count}')
    return {
        'total': len(incomplete_movies),
        'completed': completed_count,
        'failed': len(incomplete_movies) - completed_count,
        'message': '影片元数据补全任务完成',
    }
