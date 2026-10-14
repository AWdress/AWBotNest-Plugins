from datetime import date, datetime
from typing import List, Dict, Any

from sqlalchemy import func
from ..core.database import insert
from ..core.portable_types import array_member
from sqlalchemy.exc import OperationalError

from ..api.services.article_match_service import build_article_features, matches_article_filter
from ..api.services.article_service import download_article
from ..api.services.subscribe_service import _push_subscribe_completed
from ..api.services.subscribe_preference_service import (
    get_subscribe_preference_config,
    is_movie_number_prefix_blocked,
)
from ..core.database import session_scope
from ..enums import SubscribeStatus
from ..models import Cast, CastSubscribe, GeneralSubscribe, Subscribe, Movie, Article, Filter, Priority, RankMovie
from ..utils.movie_number import extract_primary_movie_number
from ..modules.crawler.avbase import av_base
from ..modules.mediaserver import mediaServerManager
from ..scheduler.movie_scheduler import sync_casts, upsert_movie
from ..utils import logger
from ..utils.db_lock import acquire_cast_movie_subscribe_write_lock, acquire_subscribe_write_lock
from ..utils.wrapper import task_monitor


RESOLUTION_ORDER = ['1080p', '4K', '8K']
SUBTITLE_ORDER = ['中文']
MOSAIC_ORDER = ['有码', '无码流出', '新模型','无码破解']
SORT_FIELD_MAP = {
    '分辨率': 'resolution',
    '字幕': 'subtitle',
    '马赛克': 'mosaic',
}


def _normalize_movie_text(value: str | None, *, uppercase: bool = False) -> str:
    normalized = (value or '').strip()
    if uppercase:
        return normalized.upper()
    return normalized.lower()


def _is_blacklisted_movie_number(movie: Movie, blacklist: list[str] | None) -> bool:
    return is_movie_number_prefix_blocked(movie.number, blacklist)


def _iter_movie_keyword_fields(movie: Movie):
    for value in [
        movie.number,
        movie.title,
        movie.cn_title,
        movie.description,
        movie.cn_description,
        movie.series,
        movie.producer,
        movie.publisher,
    ]:
        normalized = _normalize_movie_text(value)
        if normalized:
            yield normalized

    for values in [movie.genres or [], movie.cast_names or []]:
        for value in values:
            normalized = _normalize_movie_text(value)
            if normalized:
                yield normalized


def _is_blacklisted_movie_keyword(movie: Movie, blacklist: list[str] | None) -> bool:
    if not blacklist:
        return False

    candidates = tuple(_iter_movie_keyword_fields(movie))
    if not candidates:
        return False

    for keyword in blacklist:
        normalized_keyword = _normalize_movie_text(keyword)
        if not normalized_keyword:
            continue
        if any(normalized_keyword in candidate for candidate in candidates):
            return True
    return False


def _get_filter(session, filter_id: int | None) -> Filter | None:
    if not filter_id:
        return None
    return session.get(Filter, filter_id)


def _get_priority(session, priority_id: int | None) -> Priority | None:
    if not priority_id:
        return None
    return session.get(Priority, priority_id)


LIBRARY_COMPLETED_MESSAGE = '影片已在媒体库中，已直接完成订阅'
LIBRARY_PRE_DOWNLOAD_DISABLED_MESSAGE = '影片已在媒体库中，已关闭预下载并保持订阅激活'


def _default_pre_download_enabled(filter_obj: Filter | None) -> bool:
    return bool(filter_obj.enable_pre_download) if filter_obj else False


def _movie_exists_in_library(number: str | None, in_library_cache: dict[str, bool] | None = None) -> bool:
    normalized_number = (number or '').strip()
    if not normalized_number:
        return False
    if in_library_cache is not None and normalized_number in in_library_cache:
        return in_library_cache[normalized_number]
    exists = mediaServerManager.any_movie_exists_by_number(normalized_number)
    if in_library_cache is not None:
        in_library_cache[normalized_number] = exists
    return exists


def _resolve_in_library_subscribe_decision(
    movie_number: str | None,
    filter_obj: Filter | None,
    *,
    in_library_cache: dict[str, bool] | None = None,
) -> dict[str, Any]:
    default_pre_download_enabled = _default_pre_download_enabled(filter_obj)
    if filter_obj and filter_obj.skip_in_library_check:
        return {
            'skip_in_library_check': True,
            'in_library': False,
            'status': SubscribeStatus.ACTIVE.value,
            'pre_download_enabled': default_pre_download_enabled,
            'should_push_completed': False,
            'message': '',
        }

    if not _movie_exists_in_library(movie_number, in_library_cache):
        return {
            'skip_in_library_check': False,
            'in_library': False,
            'status': SubscribeStatus.ACTIVE.value,
            'pre_download_enabled': default_pre_download_enabled,
            'should_push_completed': False,
            'message': '',
        }

    if default_pre_download_enabled:
        return {
            'skip_in_library_check': False,
            'in_library': True,
            'status': SubscribeStatus.ACTIVE.value,
            'pre_download_enabled': False,
            'should_push_completed': False,
            'message': LIBRARY_PRE_DOWNLOAD_DISABLED_MESSAGE,
        }

    return {
        'skip_in_library_check': False,
        'in_library': True,
        'status': SubscribeStatus.COMPLETED.value,
        'pre_download_enabled': False,
        'should_push_completed': True,
        'message': LIBRARY_COMPLETED_MESSAGE,
    }


def _priority_index(value: str | None, candidates: List[str] | None, default_order: List[str]) -> int:
    options = candidates or default_order
    if not value:
        return len(options) + 1
    try:
        return options.index(value)
    except ValueError:
        return len(options) + 1


def _normalize_subscribe_match_number(number: str | None) -> str | None:
    return extract_primary_movie_number(number)


ARTICLE_SUBSCRIBE_CANDIDATE_LIMIT = 50


def _fetch_article_candidates(session, match_number: str) -> list[Article]:
    return (
        session.query(Article)
        .filter(Article.match_number == match_number)
        .order_by(Article.publish_date.desc().nullslast(), Article.create_time.desc(), Article.id.desc())
        .limit(ARTICLE_SUBSCRIBE_CANDIDATE_LIMIT)
        .all()
    )


def _sort_key(article: Article, priority_obj: Priority | None):
    features = build_article_features(article)
    sort_fields = priority_obj.priority_sort if priority_obj and priority_obj.priority_sort else ['字幕', '马赛克', '分辨率']

    key = []
    for field in sort_fields:
        mapped = SORT_FIELD_MAP.get(field)
        if mapped == 'resolution':
            key.append(_priority_index(features['resolution'], priority_obj.resolutions if priority_obj else None, RESOLUTION_ORDER))
        elif mapped == 'subtitle':
            key.append(_priority_index(features['subtitle'], priority_obj.subtitles if priority_obj else None, SUBTITLE_ORDER))
        elif mapped == 'mosaic':
            key.append(_priority_index(features['mosaic'], priority_obj.mosaic if priority_obj else None, MOSAIC_ORDER))
        else:
            key.append(999)

    publish_ord = article.publish_date.toordinal() if isinstance(article.publish_date, date) else -1
    create_ts = int(article.create_time.timestamp()) if isinstance(article.create_time, datetime) else -1
    key.extend([-publish_ord, -create_ts, -int(article.id or 0)])
    return tuple(key)


def _find_sorted_articles_by_subscribe(number: str, priority_id: int | None) -> list[Article]:
    with session_scope() as session:
        match_number = _normalize_subscribe_match_number(number)
        if not match_number:
            return []

        articles = _fetch_article_candidates(session, match_number)
        if not articles:
            return []

        priority_obj = _get_priority(session, priority_id)
        return sorted(articles, key=lambda article: _sort_key(article, priority_obj))



def _find_best_article_by_subscribe(number: str, filter_id: int | None, priority_id: int | None) -> Article | None:
    sorted_articles = _find_sorted_articles_by_subscribe(number, priority_id)
    if not sorted_articles:
        return None

    with session_scope() as session:
        filter_obj = _get_filter(session, filter_id)
        filtered_articles = [article for article in sorted_articles if matches_article_filter(article, filter_obj)]

    logger.info(
        f"订阅资源匹配结果 | number={number}, candidate_count={len(sorted_articles)}, filtered_count={len(filtered_articles)}, has_filter={bool(filter_id)}, has_priority={bool(priority_id)}"
    )

    if filtered_articles:
        return filtered_articles[0]
    return None



def _find_pre_download_article_by_subscribe(number: str, priority_id: int | None) -> Article | None:
    sorted_articles = _find_sorted_articles_by_subscribe(number, priority_id)
    return sorted_articles[0] if sorted_articles else None


@task_monitor
def execute_subscribe() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    in_library_cache: dict[str, bool] = {}

    subscribe_ids: list[int] = []

    def _collect(session, _subscribe_id):
        nonlocal subscribe_ids
        subscribe_ids = [
            sid
            for sid, in (
                session.query(Subscribe.id)
                .filter(Subscribe.status == SubscribeStatus.ACTIVE.value)
                .order_by(Subscribe.create_time.asc())
                .all()
            )
        ]

    try:
        _with_subscribe_write_lock(0, _collect)
    except LockTimeoutError:
        logger.warning("订阅锁等待超时，跳过本次执行（整个批次）")
        return results

    if not subscribe_ids:
        logger.info("当前没有需要执行的订阅任务")
        return results

    logger.info(f"开始执行订阅任务，共 {len(subscribe_ids)} 条激活订阅")

    for subscribe_id in subscribe_ids:
        results.append(execute_subscribe_once(subscribe_id, in_library_cache=in_library_cache))

    return results


def _with_subscribe_write_lock(subscribe_id: int, mutate):
    """
    在订阅写锁保护下执行 mutate(session, subscribe_id)。
    锁等待超时（pg_advisory_xact_lock 触发 lock_timeout）时，
    抛出 LockTimeoutError，由调用方决定跳过当前订阅，避免一条卡住阻塞整批。
    """
    from sqlalchemy.orm import Session

    from ..core.database import session_scope
    from ..utils.db_lock import acquire_subscribe_write_lock

    try:
        with session_scope() as session:
            acquire_subscribe_write_lock(session)
            mutate(session, subscribe_id)
    except OperationalError as e:
        # PostgreSQL lock_timeout 触发后抛 55P03 (LockNotAvailable)
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        sqlite_code = getattr(getattr(e, 'orig', None), 'sqlite_errorcode', None)
        if pgcode == '55P03' or sqlite_code is not None and sqlite_code & 0xff in {5, 6}:
            logger.warning(
                f"订阅写锁等待超时，跳过本次执行 | subscribe_id={subscribe_id}"
            )
            raise LockTimeoutError(subscribe_id) from e
        raise


class LockTimeoutError(Exception):
    """订阅锁等待超时，用于在批处理中跳过当前条目。"""
    def __init__(self, subscribe_id: int):
        self.subscribe_id = subscribe_id
        super().__init__(f"Lock timeout for subscribe {subscribe_id}")


def execute_subscribe_once(subscribe_id: int, in_library_cache: dict[str, bool] | None = None) -> Dict[str, Any]:
    with session_scope() as session:
        row = (
            session.query(Subscribe, Movie)
            .join(Movie, Movie.id == Subscribe.movie_id)
            .filter(Subscribe.id == subscribe_id)
            .first()
        )

    if not row:
        raise ValueError('Subscribe not found')

    subscribe, movie = row
    if subscribe.status == SubscribeStatus.CANCELED.value:
        raise ValueError('Canceled subscription cannot be executed')

    logger.info(
        f"处理订阅：id={subscribe.id}, movie_id={movie.id}, number={movie.number}, filter_id={subscribe.filter_id}, priority_id={subscribe.priority_id}"
    )

    with session_scope() as session:
        filter_obj = _get_filter(session, subscribe.filter_id)

    library_decision = _resolve_in_library_subscribe_decision(
        movie.number,
        filter_obj,
        in_library_cache=in_library_cache,
    )

    if library_decision['skip_in_library_check']:
        logger.info(
            f"过滤器已配置跳过在库检测 | subscribe_id={subscribe.id}, filter_id={subscribe.filter_id}, number={movie.number}"
        )
    elif library_decision['in_library']:
        def _mark_in_library(session, _sid):
            sub_in_db = session.get(Subscribe, subscribe.id)
            if sub_in_db:
                sub_in_db.status = library_decision['status']
                sub_in_db.pre_download_enabled = library_decision['pre_download_enabled']
                subscribe.status = sub_in_db.status
                subscribe.pre_download_enabled = sub_in_db.pre_download_enabled
                logger.info(
                    f"影片已存在于媒体库，按过滤器配置更新订阅 | subscribe_id={subscribe.id}, number={movie.number}, "
                    f"status={sub_in_db.status}, pre_download_enabled={sub_in_db.pre_download_enabled}"
                )

        try:
            _with_subscribe_write_lock(subscribe.id, _mark_in_library)
        except LockTimeoutError:
            logger.warning(
                f"订阅锁等待超时，跳过在库状态更新 | subscribe_id={subscribe.id}, number={movie.number}"
            )
            return {
                'subscribe_id': subscribe.id,
                'movie_id': movie.id,
                'movie_number': movie.number,
                'article_id': None,
                'success': False,
                'message': '订阅锁等待超时，跳过在库状态更新',
            }

        if library_decision['should_push_completed']:
            with session_scope() as session:
                _push_subscribe_completed(
                    subscribe,
                    movie,
                    completion_source='library',
                    db=session,
                )
        return {
            'subscribe_id': subscribe.id,
            'movie_id': movie.id,
            'movie_number': movie.number,
            'article_id': None,
            'success': True,
            'message': library_decision['message'],
        }

    article = _find_best_article_by_subscribe(
        movie.number,
        subscribe.filter_id,
        subscribe.priority_id,
    )

    is_pre_download = False
    if not article and subscribe.pre_download_enabled:
        article = _find_pre_download_article_by_subscribe(
            movie.number,
            subscribe.priority_id,
        )
        if article:
            is_pre_download = True
            logger.info(
                f"未命中过滤器，改为执行预下载 | subscribe_id={subscribe.id}, number={movie.number}, article_id={article.id}"
            )

    if not article:
        logger.warning(
            f"未找到匹配文章，订阅保持当前状态 | subscribe_id={subscribe.id}, number={movie.number}"
        )
        return {
            'subscribe_id': subscribe.id,
            'movie_id': movie.id,
            'movie_number': movie.number,
            'article_id': None,
            'success': False,
            'message': '未找到符合过滤条件的文章',
        }

    logger.info(
        f"找到匹配文章 article_id={article.id}, title={article.title}，开始创建下载任务"
    )

    resp = download_article(article.id, update_subscribe_state=False)
    success = isinstance(resp, dict) and resp.get('code') == 0

    if success:
        def _mark_completed(session, _sid):
            sub_in_db = session.get(Subscribe, subscribe.id)
            if sub_in_db:
                if is_pre_download:
                    sub_in_db.pre_download_enabled = False
                    logger.info(
                        f"预下载执行成功，关闭预下载状态并保持 ACTIVE | subscribe_id={subscribe.id}"
                    )
                else:
                    sub_in_db.status = SubscribeStatus.COMPLETED.value
                    sub_in_db.pre_download_enabled = False
                    logger.info(
                        f"订阅执行成功，状态更新为 COMPLETED | subscribe_id={subscribe.id}"
                    )

        try:
            _with_subscribe_write_lock(subscribe.id, _mark_completed)
        except LockTimeoutError:
            logger.warning(
                f"订阅锁等待超时，状态更新失败（下个周期重试） | subscribe_id={subscribe.id}, number={movie.number}"
            )
        if is_pre_download:
            return {
                'subscribe_id': subscribe.id,
                'movie_id': movie.id,
                'movie_number': movie.number,
                'article_id': article.id,
                'success': True,
                'message': '未命中过滤器，已按排序器优先级执行一次预下载',
            }

        with session_scope() as session:
            _push_subscribe_completed(
                subscribe,
                movie,
                article=article,
                completion_source='download',
                db=session,
            )
    else:
        logger.error(
            f"订阅执行失败 | subscribe_id={subscribe.id}, article_id={article.id}, resp={resp}"
        )

    return {
        'subscribe_id': subscribe.id,
        'movie_id': movie.id,
        'movie_number': movie.number,
        'article_id': article.id,
        'success': success,
        'message': (
            '未命中过滤器，已按排序器优先级执行一次预下载'
            if success and is_pre_download
            else (resp.get('message') if isinstance(resp, dict) else None)
        ),
    }


def _normalize_rank_name_list(rank_name_list: Any) -> List[str]:
    if not rank_name_list:
        return []
    if isinstance(rank_name_list, str):
        return [rank_name_list]
    if isinstance(rank_name_list, (list, tuple, set)):
        return [item for item in rank_name_list if item]
    return []


def _normalize_limit(limit: Any) -> int | None:
    if limit in (None, ''):
        return None
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _build_subscribe_push_snapshot(
    *,
    subscribe_id: int | None,
    movie_id: int,
    filter_id: int | None,
    priority_id: int | None,
    pre_download_enabled: bool,
    status: str,
) -> Subscribe:
    subscribe = Subscribe()
    subscribe.id = subscribe_id
    subscribe.movie_id = movie_id
    subscribe.filter_id = filter_id
    subscribe.priority_id = priority_id
    subscribe.pre_download_enabled = pre_download_enabled
    subscribe.status = status
    return subscribe


def _flush_library_completed_pushes(completed_push_payloads: list[tuple[Subscribe, Movie]]) -> None:
    if not completed_push_payloads:
        return
    with session_scope() as session:
        for subscribe, movie in completed_push_payloads:
            _push_subscribe_completed(
                subscribe,
                movie,
                completion_source='library',
                db=session,
            )


@task_monitor
def execute_rank_subscribe(rank_name_list: List[str] | str, limit: int | str | None = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    completed_push_payloads: list[tuple[Subscribe, Movie]] = []
    in_library_cache: dict[str, bool] = {}
    rank_names = _normalize_rank_name_list(rank_name_list)
    normalized_limit = _normalize_limit(limit)
    logger.info(f"execute_rank_subscribe | rank_name_list={rank_names}, limit={normalized_limit}")
    if not rank_names:
        return results

    with session_scope() as session:
        acquire_subscribe_write_lock(session)
        default_filter = (
            session.query(Filter)
            .order_by(Filter.is_default.desc(), Filter.id.asc())
            .first()
        )
        default_priority = (
            session.query(Priority)
            .order_by(Priority.is_default.desc(), Priority.id.asc())
            .first()
        )
        scheduled_movie_ids = {
            movie_id
            for movie_id, in session.query(Subscribe.movie_id).all()
        }
        preference_config = get_subscribe_preference_config(session)
        number_prefix_blacklist = preference_config.get('number_prefix_blacklist', [])
        keyword_blacklist = preference_config.get('keyword_blacklist', [])

        for rank_name in rank_names:
            rank = (
                session.query(RankMovie)
                .filter(RankMovie.rank_name == rank_name)
                .order_by(RankMovie.create_time.desc())
                .first()
            )

            if not rank or not rank.movie_ids:
                logger.info(f"未找到可订阅的榜单数据 | rank_name={rank_name}")
                results.append({
                    'rank_name': rank_name,
                    'rank_id': None,
                    'total_rank_movies': 0,
                    'subscribed_count': 0,
                    'skipped_count': 0,
                    'subscribed_movie_ids': [],
                    'message': '未找到榜单数据',
                })
                continue

            ordered_movie_ids = []
            seen_movie_ids = set()
            for movie_id in rank.movie_ids:
                if movie_id in seen_movie_ids:
                    continue
                seen_movie_ids.add(movie_id)
                ordered_movie_ids.append(movie_id)

            if normalized_limit is not None:
                ordered_movie_ids = ordered_movie_ids[:normalized_limit]

            movie_map = {movie.id: movie for movie in session.query(Movie).filter(Movie.id.in_(ordered_movie_ids)).all()} if ordered_movie_ids else {}

            candidate_movie_ids = []
            seen_candidate_ids = set()
            blocked_count = 0
            for movie_id in ordered_movie_ids:
                movie = movie_map.get(movie_id)
                if movie and (
                    _is_blacklisted_movie_number(movie, number_prefix_blacklist)
                    or _is_blacklisted_movie_keyword(movie, keyword_blacklist)
                ):
                    blocked_count += 1
                    continue
                if movie_id in scheduled_movie_ids or movie_id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(movie_id)
                candidate_movie_ids.append(movie_id)

            subscribed_movie_ids = []
            for movie_id in candidate_movie_ids:
                movie = movie_map.get(movie_id)
                if movie is None:
                    continue
                library_decision = _resolve_in_library_subscribe_decision(
                    movie.number,
                    default_filter,
                    in_library_cache=in_library_cache,
                )
                stmt = (
                    insert(Subscribe)
                    .values(
                        movie_id=movie_id,
                        filter_id=default_filter.id if default_filter else None,
                        priority_id=default_priority.id if default_priority else None,
                        pre_download_enabled=library_decision['pre_download_enabled'],
                        status=library_decision['status'],
                    )
                    .on_conflict_do_nothing(index_elements=[Subscribe.movie_id])
                    .returning(Subscribe.id, Subscribe.movie_id)
                )
                inserted_row = session.execute(stmt).first()
                if inserted_row is None:
                    continue
                subscribe_id, inserted_movie_id = inserted_row
                scheduled_movie_ids.add(inserted_movie_id)
                subscribed_movie_ids.append(inserted_movie_id)
                if library_decision['should_push_completed']:
                    completed_push_payloads.append((
                        _build_subscribe_push_snapshot(
                            subscribe_id=subscribe_id,
                            movie_id=inserted_movie_id,
                            filter_id=default_filter.id if default_filter else None,
                            priority_id=default_priority.id if default_priority else None,
                            pre_download_enabled=library_decision['pre_download_enabled'],
                            status=library_decision['status'],
                        ),
                        movie,
                    ))

            skipped_count = len(ordered_movie_ids) - len(subscribed_movie_ids)

            logger.info(
                f"榜单订阅完成 | rank_name={rank_name}, total={len(ordered_movie_ids)}, blocked={blocked_count}, "
                f"subscribed={len(subscribed_movie_ids)}, skipped={skipped_count}"
            )

            results.append({
                'rank_name': rank_name,
                'rank_id': rank.id,
                'total_rank_movies': len(ordered_movie_ids),
                'subscribed_count': len(subscribed_movie_ids),
                'blocked_count': blocked_count,
                'skipped_count': skipped_count,
                'subscribed_movie_ids': subscribed_movie_ids,
                'message': f"榜单订阅完成，新增 {len(subscribed_movie_ids)} 条，黑名单跳过 {blocked_count} 条，已存在或重复跳过 {skipped_count} 条",
            })

    _flush_library_completed_pushes(completed_push_payloads)
    return results




def _sync_movies_for_cast_subscribe(session, cast_subscribe: CastSubscribe):
    cast = session.get(Cast, cast_subscribe.cast_id)
    if not cast:
        logger.warning(f'演员订阅对应演员不存在 | cast_subscribe_id={cast_subscribe.id}, cast_id={cast_subscribe.cast_id}')
        return None, 0

    cast_name = cast.name
    if not cast_name:
        logger.warning(f'演员缺少可用于抓取的名称 | cast_subscribe_id={cast_subscribe.id}, cast_id={cast_subscribe.cast_id}')
        return cast, 0

    movies, casts = av_base.get_talent_works(
        cast_name,
        max_page=cast_subscribe.max_page,
        is_single=bool(cast_subscribe.is_single),
    )
    if not movies:
        logger.info(f'演员作品同步为空 | cast_id={cast.id}, cast_name={cast_name}')
        return cast, 0

    sync_casts(session, casts)
    for movie in movies:
        upsert_movie(session, movie)

    logger.info(f'演员作品同步完成 | cast_id={cast.id}, cast_name={cast_name}, movie_count={len(movies)}')
    return cast, len(movies)

def _is_vr_movie(movie: Movie) -> bool:
    candidates = [movie.number, movie.title, *(movie.genres or [])]
    return any('VR' in (value or '').upper() for value in candidates)


def _movie_matches_general_subscribe(movie: Movie, general_subscribe: GeneralSubscribe) -> bool:
    if general_subscribe.number_prefix:
        if not _normalize_movie_text(movie.number, uppercase=True).startswith(general_subscribe.number_prefix.upper()):
            return False

    if general_subscribe.publisher:
        if _normalize_movie_text(movie.publisher) != _normalize_movie_text(general_subscribe.publisher):
            return False

    if general_subscribe.series:
        if _normalize_movie_text(movie.series) != _normalize_movie_text(general_subscribe.series):
            return False

    if general_subscribe.producer:
        if _normalize_movie_text(movie.producer) != _normalize_movie_text(general_subscribe.producer):
            return False

    if general_subscribe.genres:
        movie_genres = {_normalize_movie_text(item) for item in (movie.genres or []) if item}
        subscribe_genres = {_normalize_movie_text(item) for item in (general_subscribe.genres or []) if item}
        if not subscribe_genres.issubset(movie_genres):
            return False

    if general_subscribe.earliest_release_date and (
        movie.release_date is None or movie.release_date < general_subscribe.earliest_release_date
    ):
        return False

    cast_total = len(movie.casts or [])
    coactor_count = max(cast_total - 1, 0)
    if general_subscribe.max_coactors is not None and coactor_count > general_subscribe.max_coactors:
        return False

    if general_subscribe.exclude_vr and _is_vr_movie(movie):
        return False

    return True


@task_monitor
def execute_general_subscribe() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    completed_push_payloads: list[tuple[Subscribe, Movie]] = []
    in_library_cache: dict[str, bool] = {}

    with session_scope() as session:
        acquire_cast_movie_subscribe_write_lock(session)
        general_subscribes = (
            session.query(GeneralSubscribe)
            .filter(GeneralSubscribe.status == SubscribeStatus.ACTIVE.value)
            .order_by(GeneralSubscribe.create_time.asc())
            .all()
        )
        scheduled_movie_ids = {
            movie_id
            for movie_id, in session.query(Subscribe.movie_id).all()
        }
        preference_config = get_subscribe_preference_config(session)
        number_prefix_blacklist = preference_config.get('number_prefix_blacklist', [])
        keyword_blacklist = preference_config.get('keyword_blacklist', [])

        if not general_subscribes:
            logger.info('当前没有需要执行的综合订阅任务')
            return results

        for general_subscribe in general_subscribes:
            general_filter = session.get(Filter, general_subscribe.filter_id) if general_subscribe.filter_id else None

            query = session.query(Movie)
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

            movies = query.order_by(Movie.release_date.desc().nullslast(), Movie.id.desc()).all()
            movie_map = {movie.id: movie for movie in movies}

            ordered_movie_ids = []
            seen_movie_ids = set()
            blocked_count = 0
            for movie in movies:
                if movie.id in seen_movie_ids:
                    continue
                seen_movie_ids.add(movie.id)
                if (
                    _is_blacklisted_movie_number(movie, number_prefix_blacklist)
                    or _is_blacklisted_movie_keyword(movie, keyword_blacklist)
                ):
                    blocked_count += 1
                    continue
                if not _movie_matches_general_subscribe(movie, general_subscribe):
                    continue
                ordered_movie_ids.append(movie.id)

            candidate_movie_ids = []
            seen_candidate_ids = set()
            for movie_id in ordered_movie_ids:
                if movie_id in scheduled_movie_ids or movie_id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(movie_id)
                candidate_movie_ids.append(movie_id)

            subscribed_movie_ids = []
            for movie_id in candidate_movie_ids:
                movie = movie_map.get(movie_id)
                if movie is None:
                    continue
                library_decision = _resolve_in_library_subscribe_decision(
                    movie.number,
                    general_filter,
                    in_library_cache=in_library_cache,
                )
                stmt = (
                    insert(Subscribe)
                    .values(
                        movie_id=movie_id,
                        filter_id=general_subscribe.filter_id,
                        priority_id=general_subscribe.priority_id,
                        pre_download_enabled=library_decision['pre_download_enabled'],
                        status=library_decision['status'],
                    )
                    .on_conflict_do_nothing(index_elements=[Subscribe.movie_id])
                    .returning(Subscribe.id, Subscribe.movie_id)
                )
                inserted_row = session.execute(stmt).first()
                if inserted_row is None:
                    continue
                subscribe_id, inserted_movie_id = inserted_row
                scheduled_movie_ids.add(inserted_movie_id)
                subscribed_movie_ids.append(inserted_movie_id)
                if library_decision['should_push_completed']:
                    completed_push_payloads.append((
                        _build_subscribe_push_snapshot(
                            subscribe_id=subscribe_id,
                            movie_id=inserted_movie_id,
                            filter_id=general_subscribe.filter_id,
                            priority_id=general_subscribe.priority_id,
                            pre_download_enabled=library_decision['pre_download_enabled'],
                            status=library_decision['status'],
                        ),
                        movie,
                    ))

            skipped_count = len(ordered_movie_ids) - len(subscribed_movie_ids)

            logger.info(
                f"综合订阅执行完成 | general_subscribe_id={general_subscribe.id}, total={len(ordered_movie_ids)}, blocked={blocked_count}, "
                f"subscribed={len(subscribed_movie_ids)}, skipped={skipped_count}"
            )

            results.append({
                'general_subscribe_id': general_subscribe.id,
                'number_prefix': general_subscribe.number_prefix,
                'publisher': general_subscribe.publisher,
                'series': general_subscribe.series,
                'producer': general_subscribe.producer,
                'genres': general_subscribe.genres or [],
                'total_movies': len(ordered_movie_ids),
                'subscribed_count': len(subscribed_movie_ids),
                'blocked_count': blocked_count,
                'skipped_count': skipped_count,
                'subscribed_movie_ids': subscribed_movie_ids,
                'message': f"综合订阅执行完成，新增 {len(subscribed_movie_ids)} 条，黑名单跳过 {blocked_count} 条，已存在或重复跳过 {skipped_count} 条",
            })

    _flush_library_completed_pushes(completed_push_payloads)
    return results


@task_monitor
def execute_cast_subscribe() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    completed_push_payloads: list[tuple[Subscribe, Movie]] = []
    in_library_cache: dict[str, bool] = {}

    with session_scope() as session:
        acquire_cast_movie_subscribe_write_lock(session)
        cast_subscribes = (
            session.query(CastSubscribe)
            .filter(CastSubscribe.status == SubscribeStatus.ACTIVE.value)
            .order_by(CastSubscribe.create_time.asc())
            .all()
        )
        scheduled_movie_ids = {
            movie_id
            for movie_id, in session.query(Subscribe.movie_id).all()
        }
        preference_config = get_subscribe_preference_config(session)
        number_prefix_blacklist = preference_config.get('number_prefix_blacklist', [])
        keyword_blacklist = preference_config.get('keyword_blacklist', [])

        if not cast_subscribes:
            logger.info('当前没有需要执行的演员订阅任务')
            return results

        for cast_subscribe in cast_subscribes:
            used_max_page = cast_subscribe.max_page
            next_max_page = cast_subscribe.replace_max_page if cast_subscribe.replace_max_page is not None else 1

            cast, synced_movie_count = _sync_movies_for_cast_subscribe(session, cast_subscribe)
            cast_filter = session.get(Filter, cast_subscribe.filter_id) if cast_subscribe.filter_id else None

            query = session.query(Movie).filter(array_member(Movie.casts, cast_subscribe.cast_id))
            if cast_subscribe.earliest_release_date:
                query = query.filter(Movie.release_date >= cast_subscribe.earliest_release_date)

            movies = query.order_by(Movie.release_date.desc().nullslast(), Movie.id.desc()).all()
            movie_map = {movie.id: movie for movie in movies}

            ordered_movie_ids = []
            seen_movie_ids = set()
            blocked_count = 0
            for movie in movies:
                if movie.id in seen_movie_ids:
                    continue
                seen_movie_ids.add(movie.id)

                if (
                    _is_blacklisted_movie_number(movie, number_prefix_blacklist)
                    or _is_blacklisted_movie_keyword(movie, keyword_blacklist)
                ):
                    blocked_count += 1
                    continue

                cast_total = len(movie.casts or [])
                coactor_count = max(cast_total - 1, 0)
                if cast_subscribe.max_coactors is not None and coactor_count > cast_subscribe.max_coactors:
                    continue
                if cast_subscribe.exclude_vr and _is_vr_movie(movie):
                    continue
                ordered_movie_ids.append(movie.id)

            candidate_movie_ids = []
            seen_candidate_ids = set()
            for movie_id in ordered_movie_ids:
                if movie_id in scheduled_movie_ids or movie_id in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(movie_id)
                candidate_movie_ids.append(movie_id)

            subscribed_movie_ids = []
            for movie_id in candidate_movie_ids:
                movie = movie_map.get(movie_id)
                if movie is None:
                    continue
                library_decision = _resolve_in_library_subscribe_decision(
                    movie.number,
                    cast_filter,
                    in_library_cache=in_library_cache,
                )
                stmt = (
                    insert(Subscribe)
                    .values(
                        movie_id=movie_id,
                        filter_id=cast_subscribe.filter_id,
                        priority_id=cast_subscribe.priority_id,
                        pre_download_enabled=library_decision['pre_download_enabled'],
                        status=library_decision['status'],
                    )
                    .on_conflict_do_nothing(index_elements=[Subscribe.movie_id])
                    .returning(Subscribe.id, Subscribe.movie_id)
                )
                inserted_row = session.execute(stmt).first()
                if inserted_row is None:
                    continue
                subscribe_id, inserted_movie_id = inserted_row
                scheduled_movie_ids.add(inserted_movie_id)
                subscribed_movie_ids.append(inserted_movie_id)
                if library_decision['should_push_completed']:
                    completed_push_payloads.append((
                        _build_subscribe_push_snapshot(
                            subscribe_id=subscribe_id,
                            movie_id=inserted_movie_id,
                            filter_id=cast_subscribe.filter_id,
                            priority_id=cast_subscribe.priority_id,
                            pre_download_enabled=library_decision['pre_download_enabled'],
                            status=library_decision['status'],
                        ),
                        movie,
                    ))

            cast_subscribe.max_page = next_max_page

            skipped_count = len(ordered_movie_ids) - len(subscribed_movie_ids)

            logger.info(
                f"演员订阅执行完成 | cast_id={cast_subscribe.cast_id}, total={len(ordered_movie_ids)}, blocked={blocked_count}, "
                f"subscribed={len(subscribed_movie_ids)}, skipped={skipped_count}, "
                f"used_max_page={used_max_page}, next_max_page={next_max_page}"
            )

            results.append({
                'cast_subscribe_id': cast_subscribe.id,
                'cast_id': cast_subscribe.cast_id,
                'cast_name': cast.name if cast else None,
                'synced_movie_count': synced_movie_count,
                'total_movies': len(ordered_movie_ids),
                'subscribed_count': len(subscribed_movie_ids),
                'blocked_count': blocked_count,
                'skipped_count': skipped_count,
                'subscribed_movie_ids': subscribed_movie_ids,
                'used_max_page': used_max_page,
                'next_max_page': next_max_page,
                'message': f"演员订阅执行完成，新增 {len(subscribed_movie_ids)} 条，黑名单跳过 {blocked_count} 条，已存在或重复跳过 {skipped_count} 条",
            })

    _flush_library_completed_pushes(completed_push_payloads)
    return results
