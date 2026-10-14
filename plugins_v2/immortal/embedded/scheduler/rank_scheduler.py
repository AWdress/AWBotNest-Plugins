from sqlalchemy import or_, select
from ..core.database import insert

from ..core.database import session_scope
from ..models import Movie, RankMovie, Cast, RankCast
from ..modules.crawler.avbase import av_base
from ..modules.crawler.javdb import javdb
from ..modules.crawler.library import library
from ..scheduler.crawler_scheduler import create_session, destroy_session
from ..schemas.movie import MovieSearchParam
from ..scheduler.movie_scheduler import _collect_cast_aliases, sync_casts
from ..utils import logger, safe_get
from ..utils.db_lock import acquire_cast_movie_write_lock
from ..utils.wrapper import task_monitor


def _get_latest_rank_movie(session, rank_name: str):
    return (
        session.query(RankMovie)
        .filter(RankMovie.rank_name == rank_name)
        .order_by(RankMovie.create_time.desc(), RankMovie.id.desc())
        .first()
    )


def _get_latest_rank_cast(session, rank_name: str):
    return (
        session.query(RankCast)
        .filter(RankCast.rank_name == rank_name)
        .order_by(RankCast.create_time.desc(), RankCast.id.desc())
        .first()
    )


def _sync_rank_movies(session, top_movie) -> list[int]:
    top_numbers = [movie["number"] for movie in top_movie]
    if not top_numbers:
        return []

    acquire_cast_movie_write_lock(session)
    stmt = insert(Movie).values(top_movie)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[Movie.number]
    )
    session.execute(stmt)
    movies = session.execute(
        select(Movie.id, Movie.number)
        .where(Movie.number.in_(top_numbers))
    ).all()
    movie_map = {m.number: m.id for m in movies}
    return [
        movie_map[num]
        for num in top_numbers
        if num in movie_map
    ]


def save_top_movie(top_movie, rank_name):
    with session_scope() as session:
        ordered_movie_ids = _sync_rank_movies(session, top_movie)
        latest_rank = _get_latest_rank_movie(session, rank_name)
        if latest_rank and list(latest_rank.movie_ids or []) == ordered_movie_ids:
            return {
                'saved': False,
                'count': len(ordered_movie_ids),
                'message': '榜单无变化，跳过保存',
            }
        session.add(RankMovie(rank_name=rank_name, movie_ids=ordered_movie_ids))
        return {
            'saved': True,
            'count': len(ordered_movie_ids),
            'message': '榜单同步完成',
        }


def _resolve_ordered_cast_ids(session, top_casts) -> tuple[list[int], list[str]]:
    if not top_casts:
        return [], []

    cast_aliases = []
    for row in top_casts:
        cast_aliases.extend(_collect_cast_aliases(row))
    cast_aliases = [alias for alias in cast_aliases if alias]
    if not cast_aliases:
        return [], []

    sync_casts(session, top_casts)

    casts = (
        session.query(Cast)
        .filter(
            or_(
                Cast.name.in_(cast_aliases),
                Cast.former_name.overlap(cast_aliases),
            )
        )
        .order_by(Cast.id.asc())
        .all()
    )

    cast_map = {}
    for cast in casts:
        for alias in [cast.name, cast.cn_name, *(cast.former_name or [])]:
            alias_name = (alias or '').strip()
            if alias_name and alias_name not in cast_map:
                cast_map[alias_name] = cast.id

    ordered_cast_ids = []
    seen_cast_ids = set()
    missing_names = []
    for row in top_casts:
        matched_cast_id = None
        for alias in _collect_cast_aliases(row):
            matched_cast_id = cast_map.get(alias)
            if matched_cast_id is not None:
                break
        if matched_cast_id is None:
            name = (row.get('name') or '').strip()
            if name:
                missing_names.append(name)
            continue
        if matched_cast_id in seen_cast_ids:
            continue
        seen_cast_ids.add(matched_cast_id)
        ordered_cast_ids.append(matched_cast_id)

    return ordered_cast_ids, missing_names


def _save_rank_cast_ids(session, rank_name: str, cast_ids: list[int]):
    if not cast_ids:
        return {
            'saved': False,
            'count': 0,
            'message': '榜单无结果',
        }
    latest_rank = _get_latest_rank_cast(session, rank_name)
    if latest_rank and list(latest_rank.cast_ids or []) == cast_ids:
        return {
            'saved': False,
            'count': len(cast_ids),
            'message': '榜单无变化，跳过保存',
        }
    session.add(RankCast(rank_name=rank_name, cast_ids=cast_ids))
    return {
        'saved': True,
        'count': len(cast_ids),
        'message': '榜单同步完成',
    }


def save_top_cast(top_casts, rank_name):
    if not top_casts:
        return {
            'saved': False,
            'count': 0,
            'message': '榜单无结果',
        }

    with session_scope() as session:
        ordered_cast_ids, _ = _resolve_ordered_cast_ids(session, top_casts)
        return _save_rank_cast_ids(session, rank_name, ordered_cast_ids)


def _merge_talent_info_to_cast(cast: Cast, talent: dict | None, fallback_avatar: str | None = None):
    if not talent:
        cast.avatar = fallback_avatar or cast.avatar
        return

    cast.name = talent.get('name') or cast.name
    cast.avatar = talent.get('avatar') or fallback_avatar or cast.avatar

    former_names = list(cast.former_name or [])
    for name in talent.get('former_name') or []:
        if name and name not in former_names:
            former_names.append(name)
    cast.former_name = former_names


@task_monitor
def sync_library_top_cast():
    create_session('library_cast_session')
    try:
        logger.info("女修榜同步开始")
        top_casts = library.get_top_actor('library_cast_session') or []
        if not top_casts:
            logger.info("女修榜同步结果为空")
            return []

        rank_name = f'library-{library.STAR_MOSTFAV}'
        save_result = save_top_cast(top_casts, rank_name)
        logger.info(f"女修榜同步完成 rank={rank_name} total={len(top_casts)} saved={save_result.get('saved')}")
        return {
            'rank_name': rank_name,
            'count': len(top_casts),
            'saved': save_result.get('saved', False),
            'saved_count': save_result.get('count', 0),
            'message': save_result.get('message') or '女修榜同步完成',
        }
    finally:
        destroy_session('library_cast_session')


@task_monitor
def sync_library_top_movie(rank_type_list, max_page):
    create_session('library_session')
    try:
        results = []
        for rank_type in rank_type_list:
            logger.info(f"图书馆榜单同步开始 rank={rank_type} pages={max_page}")
            top_movie = []
            expected_count = int(max_page) * 20
            for page in range(1, int(max_page) + 1):
                top = library.get_top_movie(rank_type, page, 'library_session')
                if top:
                    top_movie.extend(top)
            if top_movie:
                rank_name = f'library-{rank_type}'
                if len(top_movie) != expected_count:
                    with session_scope() as session:
                        synced_movie_ids = _sync_rank_movies(session, top_movie)
                    logger.warning(
                        f"图书馆榜单数量不完整，跳过保存 rank={rank_name} expected={expected_count} actual={len(top_movie)} synced_movies={len(synced_movie_ids)}"
                    )
                    results.append({
                        'rank_name': rank_name,
                        'count': len(top_movie),
                        'saved': False,
                        'saved_count': 0,
                        'message': '图书馆榜单数量不完整，已同步影片但跳过保存榜单',
                    })
                    continue
                save_result = save_top_movie(top_movie, rank_name)
                logger.info(
                    f"图书馆榜单同步完成 rank={rank_name} total={len(top_movie)} saved={save_result.get('saved')}")
                results.append({
                    'rank_name': rank_name,
                    'count': len(top_movie),
                    'saved': save_result.get('saved', False),
                    'saved_count': save_result.get('count', 0),
                    'message': '图书馆榜单同步完成' if save_result.get('saved', False) else save_result.get('message',
                                                                                                            '榜单无变化，跳过保存'),
                })
            else:
                logger.info(f"图书馆榜单无结果 rank={rank_type}")
                results.append({
                    'rank_name': f'library-{rank_type}',
                    'count': 0,
                    'message': '图书馆榜单无结果',
                })
        return results
    finally:
        destroy_session('library_session')


@task_monitor
def sync_javdb_top_movie(rank_type_list):
    results = []
    for rank_type in rank_type_list:
        type_arr = rank_type.split('-')
        section_type = type_arr[0]
        period = type_arr[1]
        logger.info(f"JavDB榜单同步开始 rank={rank_type} section={section_type} period={period}")
        top_movies = javdb.get_top_movie(section_type, period)
        if top_movies:
            rank_name = f'javdb-{rank_type}'
            save_result = save_top_movie(top_movies, rank_name)
            logger.info(f"JavDB榜单同步完成 rank={rank_name} total={len(top_movies)} saved={save_result.get('saved')}")
            results.append({
                'rank_name': rank_name,
                'count': len(top_movies),
                'saved': save_result.get('saved', False),
                'saved_count': save_result.get('count', 0),
                'message': 'JavDB榜单同步完成' if save_result.get('saved', False) else save_result.get('message',
                                                                                                       '榜单无变化，跳过保存'),
            })
        else:
            logger.info(f"JavDB榜单无结果 rank={rank_type}")
            results.append({
                'rank_name': f'javdb-{rank_type}',
                'count': 0,
                'message': 'JavDB榜单无结果',
            })
    return results


def _normalize_rank_numbers(numbers: list[str] | None) -> list[str]:
    normalized_numbers = []
    seen = set()

    for raw_number in numbers or []:
        number = str(raw_number or '').strip()
        if not number:
            continue

        dedupe_key = number.lower()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        normalized_numbers.append(number)

    return normalized_numbers


def _normalize_shared_casts(casts) -> list[dict]:
    normalized = []
    cast_map = {}

    for row in casts or []:
        if not isinstance(row, dict):
            continue

        name = str(row.get('name') or '').strip()
        if not name:
            continue

        raw_former_names = row.get('former_name') or []
        if isinstance(raw_former_names, str):
            former_names = [item.strip() for item in raw_former_names.split(',') if item.strip()]
        elif isinstance(raw_former_names, (list, tuple, set)):
            former_names = [str(item).strip() for item in raw_former_names if str(item).strip()]
        else:
            former_names = []

        dedupe_key = name.lower()
        current = cast_map.get(dedupe_key)
        if current is None:
            current = {
                'name': name,
                'former_name': [],
                'avatar': row.get('avatar') or row.get('photo'),
            }
            normalized.append(current)
            cast_map[dedupe_key] = current

        for alias in former_names:
            if alias and alias not in current['former_name']:
                current['former_name'].append(alias)

        if not current.get('avatar') and (row.get('avatar') or row.get('photo')):
            current['avatar'] = row.get('avatar') or row.get('photo')

    return normalized


def _normalize_shared_rank_item(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None

    rank_name = str(item.get('rank_name') or '').strip()
    if not rank_name:
        return None

    casts = _normalize_shared_casts(item.get('casts'))
    numbers = _normalize_rank_numbers(item.get('numbers'))
    explicit_rank_type = str(item.get('rank_type') or '').strip().lower()
    if explicit_rank_type in {'movie', 'cast'}:
        rank_kind = explicit_rank_type
    elif 'casts' in item and 'numbers' not in item:
        rank_kind = 'cast'
    elif 'numbers' in item:
        rank_kind = 'movie'
    else:
        rank_kind = 'unknown'

    return {
        'rank_name': rank_name,
        'sync_time': item.get('sync_time') or '',
        'numbers': numbers,
        'casts': casts,
        'rank_kind': rank_kind,
    }


def _load_shared_rank_snapshot(url: str, token: str) -> dict:
    headers = {
        'X-API-Key': token,
        'Authorization': f'Bearer {token}',
    }
    response = safe_get(url, headers=headers, timeout=600)
    if response is None:
        raise ValueError('下载榜单失败')

    if getattr(response, 'status_code', 200) >= 400:
        raise ValueError(f'下载榜单失败: HTTP {response.status_code}')

    try:
        payload = response.json()
    except Exception as exc:
        raise ValueError('榜单分享响应不是有效的 JSON') from exc

    data = payload.get('data') if isinstance(payload, dict) and 'data' in payload else payload
    if not isinstance(data, dict):
        raise ValueError('榜单分享响应格式不正确')

    ranks = []
    if isinstance(data.get('ranks'), list):
        for item in data.get('ranks') or []:
            normalized = _normalize_shared_rank_item(item)
            if normalized is not None:
                ranks.append(normalized)
    else:
        normalized = _normalize_shared_rank_item(data)
        if normalized is not None:
            ranks.append(normalized)

    return {
        'sync_time': data.get('sync_time') or '',
        'ranks': ranks,
    }


def _save_rank_movie_ids(session, rank_name: str, movie_ids: list[int]):
    if not movie_ids:
        return
    session.add(RankMovie(rank_name=rank_name, movie_ids=movie_ids))


def _normalize_target_rank_names(rank_name_list, rank_name, default_rank_name: str) -> list[str]:
    values = []

    if isinstance(rank_name_list, str):
        values.extend([item.strip() for item in rank_name_list.split(',') if item.strip()])
    elif isinstance(rank_name_list, (list, tuple, set)):
        values.extend([str(item).strip() for item in rank_name_list if str(item).strip()])

    if rank_name:
        values.append(str(rank_name).strip())

    if not values and default_rank_name:
        values.append(default_rank_name.strip())

    normalized_values = []
    seen = set()
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized_values.append(value)

    return normalized_values


@task_monitor
def sync_shared_movie_rank(url, token, rank_name_list=None, rank_name=None):
    from ..api.services.movie_service import network_search_movies

    logger.info(f'开始同步远程榜单 | url={url}')
    shared_snapshot = _load_shared_rank_snapshot(url, token)
    shared_ranks = shared_snapshot.get('ranks') or []
    shared_rank_map = {
        item['rank_name']: item
        for item in shared_ranks
        if item.get('rank_name')
    }

    target_rank_names = _normalize_target_rank_names(
        rank_name_list=rank_name_list,
        rank_name=rank_name,
        default_rank_name='',
    )
    if not target_rank_names:
        target_rank_names = list(shared_rank_map.keys())
    if not target_rank_names:
        return {
            'rank_name_list': [],
            'count': 0,
            'saved_count': 0,
            'saved_rank_count': 0,
            'missing_rank_names': [],
            'missing_numbers': {},
            'missing_cast_names': {},
            'message': '远程榜单为空',
        }

    missing_rank_names = [name for name in target_rank_names if name not in shared_rank_map]
    saved_rank_count = 0
    saved_count = 0
    total_count = 0
    missing_numbers_by_rank = {}
    missing_cast_names_by_rank = {}

    with session_scope() as session:
        for target_rank_name in target_rank_names:
            shared_rank = shared_rank_map.get(target_rank_name)
            if not shared_rank:
                continue

            rank_kind = shared_rank.get('rank_kind') or 'unknown'
            if rank_kind == 'cast':
                casts = shared_rank.get('casts') or []
                total_count += len(casts)
                if not casts:
                    continue

                ordered_cast_ids, missing_cast_names = _resolve_ordered_cast_ids(session, casts)
                if missing_cast_names:
                    missing_cast_names_by_rank[target_rank_name] = missing_cast_names
                if not ordered_cast_ids:
                    continue

                save_result = _save_rank_cast_ids(session, target_rank_name, ordered_cast_ids)
                if save_result.get('saved'):
                    saved_rank_count += 1
                    saved_count += len(ordered_cast_ids)
                continue

            if rank_kind != 'movie':
                logger.warning(f'跳过未知榜单类型 | rank_name={target_rank_name}, rank_kind={rank_kind}')
                continue

            numbers = shared_rank.get('numbers') or []
            total_count += len(numbers)
            if not numbers:
                continue

            ordered_movie_ids = []
            missing_numbers = []
            for number in numbers:
                movie = session.query(Movie).filter(Movie.number == number).first()
                if movie is None:
                    logger.info(f'本地缺少影片，开始抓取番号 | rank_name={target_rank_name}, number={number}')
                    network_search_movies(
                        MovieSearchParam(keyword=number, page=1, page_size=5),
                        session,
                    )
                    session.flush()
                    movie = session.query(Movie).filter(Movie.number == number).first()

                if movie is None:
                    logger.warning(f'番号抓取失败，已跳过 | rank_name={target_rank_name}, number={number}')
                    missing_numbers.append(number)
                    continue

                ordered_movie_ids.append(movie.id)

            if missing_numbers:
                missing_numbers_by_rank[target_rank_name] = missing_numbers
            if not ordered_movie_ids:
                continue

            _save_rank_movie_ids(session, target_rank_name, ordered_movie_ids)
            saved_rank_count += 1
            saved_count += len(ordered_movie_ids)

    logger.info(
        f'远程榜单同步完成 | requested={len(target_rank_names)} saved_rank_count={saved_rank_count} saved_count={saved_count} missing_rank_count={len(missing_rank_names)}'
    )
    return {
        'rank_name_list': target_rank_names,
        'count': total_count,
        'saved_count': saved_count,
        'saved_rank_count': saved_rank_count,
        'missing_rank_names': missing_rank_names,
        'missing_numbers': missing_numbers_by_rank,
        'missing_cast_names': missing_cast_names_by_rank,
        'message': '远程榜单同步完成' if saved_rank_count else '未找到可同步的远程榜单数据',
    }
