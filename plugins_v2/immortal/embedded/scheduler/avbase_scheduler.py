from datetime import date, timedelta

from ..core.database import session_scope
from ..modules.crawler.avbase import av_base
from ..scheduler.movie_scheduler import sync_casts, upsert_movie
from ..utils import logger
from ..utils.wrapper import task_monitor


@task_monitor
def sync_avbase_daily(backward_offset_days: int = 0, forward_offset_days: int = 0):
    backward_offset_days = max(int(backward_offset_days or 0), 0)
    forward_offset_days = max(int(forward_offset_days or 0), 0)

    base_date = date.today()
    start_date = base_date - timedelta(days=backward_offset_days)
    end_date = base_date + timedelta(days=forward_offset_days)

    logger.info(
        f'开始同步 AvBase 上新 | base_date={base_date.isoformat()}, '
        f'start_date={start_date.isoformat()}, end_date={end_date.isoformat()}'
    )

    total_movies: list[dict] = []
    total_casts: list[dict] = []
    daily_counts: list[dict] = []

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.isoformat()
        movies, casts = av_base.get_daily(date_str)
        movie_count = len(movies)
        daily_counts.append({
            'date': date_str,
            'count': movie_count,
        })
        total_movies.extend(movies)
        total_casts.extend(casts)
        current_date += timedelta(days=1)

    if not total_movies:
        logger.warning(
            f'AvBase 上新范围为空 | start_date={start_date.isoformat()}, end_date={end_date.isoformat()}'
        )
        return {
            'base_date': base_date.isoformat(),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'count': 0,
            'saved_count': 0,
            'daily_counts': daily_counts,
            'message': 'AvBase 上新范围为空',
        }

    with session_scope() as session:
        sync_casts(session, total_casts)
        for movie in total_movies:
            upsert_movie(session, movie)

    logger.info(
        f'AvBase 上新范围同步完成 | start_date={start_date.isoformat()}, '
        f'end_date={end_date.isoformat()}, count={len(total_movies)}'
    )
    return {
        'base_date': base_date.isoformat(),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'count': len(total_movies),
        'saved_count': len(total_movies),
        'daily_counts': daily_counts,
        'message': 'AvBase 上新范围同步完成',
    }


@task_monitor
def sync_avbase_recent():
    logger.info('开始同步 AvBase 最近上架影片')

    movies, casts = av_base.get_recent()
    if not movies:
        logger.warning('AvBase 最近上架影片为空')
        return {
            'count': 0,
            'saved_count': 0,
            'message': 'AvBase 最近上架影片为空',
        }

    with session_scope() as session:
        sync_casts(session, casts)
        for movie in movies:
            upsert_movie(session, movie)

    logger.info(f'AvBase 最近上架影片同步完成 | count={len(movies)}')
    return {
        'count': len(movies),
        'saved_count': len(movies),
        'message': 'AvBase 最近上架影片同步完成',
    }
