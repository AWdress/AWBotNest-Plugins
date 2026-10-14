from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func

from ..core.database import session_scope
from ..enums import SubscribeStatus
from ..models import CastSubscribe, DownloadLog, Movie, Subscribe
from ..models.task_log import TaskLog
from ..modules.notification.manager import pushManager
from ..utils.wrapper import task_monitor

REPORT_LIMIT = 8
REPORT_PERIODS = {
    'daily': {'days': 1, 'title': '🗓️ 订阅日报', 'label': '日报'},
    'weekly': {'days': 7, 'title': '🗓️ 订阅周报', 'label': '周报'},
    'monthly': {'days': 30, 'title': '🗓️ 订阅月报', 'label': '月报'},
}
REPORT_PERIOD_OPTIONS = [
    {'label': item['label'], 'value': key}
    for key, item in REPORT_PERIODS.items()
]


def normalize_report_period(report_period: Any) -> str:
    if isinstance(report_period, (list, tuple, set)):
        values = [str(item).strip().lower() for item in report_period if str(item).strip()]
        if not values:
            return 'weekly'
        if len(values) != 1:
            raise ValueError('报表周期只能选择一个')
        report_period = values[0]
    else:
        report_period = str(report_period or '').strip().lower() or 'weekly'

    if report_period not in REPORT_PERIODS:
        raise ValueError(f'不支持的报表周期: {report_period}')
    return report_period


def _compact_error(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return '执行失败'
    return text.splitlines()[-1]


def _empty_status_summary() -> dict[str, int]:
    return {status.value: 0 for status in SubscribeStatus}


def _collect_status_summary(rows) -> dict[str, int]:
    summary = _empty_status_summary()
    for row in rows:
        status = getattr(row, 'status', None)
        if status in summary:
            summary[status] += 1
    return summary


def _format_status_summary(summary: dict[str, int]) -> str:
    ordered_keys = [
        SubscribeStatus.ACTIVE.value,
        SubscribeStatus.PAUSED.value,
        SubscribeStatus.CANCELED.value,
        SubscribeStatus.COMPLETED.value,
    ]
    return ' / '.join(f'{key}:{summary.get(key, 0)}' for key in ordered_keys)


def _build_period_bounds(days: int) -> tuple[datetime, datetime]:
    end_at = datetime.now()
    start_at = end_at - timedelta(days=days)
    return start_at, end_at


def _build_subscription_report(days: int, title: str) -> str:
    start_at, end_at = _build_period_bounds(days)

    with session_scope() as db:
        movie_subscribes = db.query(Subscribe).all()
        cast_subscribes = db.query(CastSubscribe).all()

        movie_created_count = db.query(Subscribe).filter(Subscribe.create_time >= start_at).count()
        movie_completed_count = (
            db.query(Subscribe)
            .filter(Subscribe.status == SubscribeStatus.COMPLETED.value)
            .filter(Subscribe.update_time >= start_at)
            .count()
        )
        cast_created_count = db.query(CastSubscribe).filter(CastSubscribe.create_time >= start_at).count()

        completed_rows = (
            db.query(Subscribe, Movie)
            .join(Movie, Movie.id == Subscribe.movie_id)
            .filter(Subscribe.status == SubscribeStatus.COMPLETED.value)
            .filter(Subscribe.update_time >= start_at)
            .order_by(Subscribe.update_time.desc())
            .limit(REPORT_LIMIT)
            .all()
        )

        download_count = db.query(DownloadLog).filter(DownloadLog.create_time >= start_at).count()
        top_downloader_rows = (
            db.query(DownloadLog.downloader, func.count(DownloadLog.id))
            .filter(DownloadLog.create_time >= start_at)
            .group_by(DownloadLog.downloader)
            .order_by(func.count(DownloadLog.id).desc(), DownloadLog.downloader.asc())
            .limit(3)
            .all()
        )

        task_total_count = db.query(TaskLog).filter(TaskLog.create_time >= start_at).count()
        failed_task_rows = (
            db.query(TaskLog)
            .filter(TaskLog.create_time >= start_at, TaskLog.success == False)
            .order_by(TaskLog.create_time.desc())
            .limit(REPORT_LIMIT)
            .all()
        )

    movie_summary = _collect_status_summary(movie_subscribes)
    cast_summary = _collect_status_summary(cast_subscribes)
    failed_task_count = len(failed_task_rows)

    lines = [
        title,
        f'统计周期：{start_at.strftime("%Y-%m-%d %H:%M")} ~ {end_at.strftime("%Y-%m-%d %H:%M")}',
        '',
        '影片订阅',
        f'- 当前总量：{len(movie_subscribes)}',
        f'- 状态分布：{_format_status_summary(movie_summary)}',
        f'- 本周期新增：{movie_created_count}',
        f'- 本周期完成：{movie_completed_count}',
        '',
        '演员订阅',
        f'- 当前总量：{len(cast_subscribes)}',
        f'- 状态分布：{_format_status_summary(cast_summary)}',
        f'- 本周期新增：{cast_created_count}',
        '',
        '执行概览',
        f'- 下载记录：{download_count}',
        f'- 执行任务：{task_total_count}',
        f'- 失败任务：{failed_task_count}',
    ]

    if top_downloader_rows:
        downloader_summary = ' / '.join(f"{(name or 'unknown')}:{count}" for name, count in top_downloader_rows)
        lines.append(f'- 下载器分布：{downloader_summary}')

    if completed_rows:
        lines.extend(['', '最近完成订阅'])
        for subscribe, movie in completed_rows:
            label = movie.number or movie.cn_title or movie.title or str(subscribe.movie_id)
            update_time = subscribe.update_time.strftime('%Y-%m-%d %H:%M') if subscribe.update_time else ''
            lines.append(f'- {label} | {update_time}')

    if failed_task_rows:
        lines.extend(['', '最近失败任务'])
        for row in failed_task_rows:
            task_label = row.task_name or row.task_func or '未知任务'
            lines.append(f'- {task_label}: {_compact_error(row.error or row.execute_result)}')

    return '\n'.join(lines)


def build_subscription_digest_text(days: int, title: str) -> str:
    message = _build_subscription_report(days, title)
    return message


def _dispatch_subscription_report(report_period: Any, **_kwargs) -> dict[str, Any]:
    period_key = normalize_report_period(report_period)
    period_config = REPORT_PERIODS[period_key]
    message = _build_subscription_report(period_config['days'], period_config['title'])
    pushManager.send(message, title='📊 订阅报告', parse_mode='text')
    return {
        'report_period': period_key,
        'days': period_config['days'],
        'title': period_config['title'],
        'message': message,
        'channel_scope': 'all_enabled_channels',
    }


@task_monitor
def push_subscription_report(report_period: Any = 'weekly', chat_ids: Any = None, _task_context=None):
    return _dispatch_subscription_report(report_period, chat_ids=chat_ids, _task_context=_task_context)


@task_monitor
def push_daily_subscription_report(chat_ids: Any = None, _task_context=None):
    return _dispatch_subscription_report('daily', chat_ids=chat_ids, _task_context=_task_context)


@task_monitor
def push_weekly_subscription_report(chat_ids: Any = None, _task_context=None):
    return _dispatch_subscription_report('weekly', chat_ids=chat_ids, _task_context=_task_context)


@task_monitor
def push_monthly_subscription_report(chat_ids: Any = None, _task_context=None):
    return _dispatch_subscription_report('monthly', chat_ids=chat_ids, _task_context=_task_context)
