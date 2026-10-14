import asyncio
import copy
import json
import os
import re
import string
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Iterable, Tuple

from croniter import croniter
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ...models import Rule
from ...models.task import Task
from ...models.task_log import TaskLog
from ...scheduler import restart_scheduler, FUNC_MAP, find_func
from ...schemas.response import success, error
from ...schemas.task import TaskForm, TaskLogFilter
from ...utils.log import logger
from ...utils.task_runtime import is_task_running, mark_task_running, unmark_task_running, list_running_task_ids


def list_task(db: Session):
    task_list = db.query(Task).order_by(Task.enable.desc(), Task.id.asc()).all()
    return success(task_list)


def _normalize_arg_rule(rule: dict) -> dict:
    normalized_rule = dict(rule)
    if 'required' not in normalized_rule:
        normalized_rule['required'] = bool(normalized_rule.get('require'))
    normalized_rule.pop('require', None)
    return normalized_rule


def _list_root_directories() -> list[dict[str, str]]:
    roots = []
    if os.name == 'nt':
        for drive in string.ascii_uppercase:
            drive_path = f'{drive}:\\'
            if os.path.isdir(drive_path):
                roots.append({'name': drive_path, 'path': drive_path})
    else:
        roots.append({'name': '/', 'path': '/'})
    return roots


def browse_directories(path: str | None = None):
    return error('内置插件不开放服务器目录浏览，请手动填写下载器保存路径')


def _legacy_browse_directories(path: str | None = None):
    requested_path = (path or '').strip()
    if not requested_path:
        if os.name == 'nt':
            return success({
                'current_path': '',
                'parent_path': None,
                'items': _list_root_directories(),
            })
        requested_path = '/'

    current_path = Path(requested_path).expanduser()
    if not current_path.exists() or not current_path.is_dir():
        return error('目录不存在或不可访问')

    try:
        directories = []
        for child in sorted(current_path.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                directories.append({'name': child.name or str(child), 'path': str(child)})
    except OSError as exc:
        return error(f'读取目录失败: {exc}')

    parent_path = None
    if current_path.parent != current_path:
        parent_path = str(current_path.parent)

    return success({
        'current_path': str(current_path),
        'parent_path': parent_path,
        'items': directories,
    })


def validate_func_args(args: Any, args_list: Iterable[str]) -> Tuple[bool, str]:
    if not args_list:
        return True, ''
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as exc:
            return False, f'args 不是合法 JSON：{exc}'

    if not isinstance(args, dict):
        return False, 'args 必须是 JSON 对象（dict）'

    missing_fields = [field for field in args_list if field not in args]
    if missing_fields:
        return False, f'缺少必要字段：{missing_fields}'

    return True, ''


def _parse_task_args(raw_args: Any) -> tuple[dict[str, Any], str | None]:
    if raw_args in (None, ''):
        return {}, None
    if isinstance(raw_args, dict):
        return raw_args, None
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            return {}, f'args 不是合法 JSON：{exc}'
        if not isinstance(parsed, dict):
            return {}, 'args 必须是 JSON 对象（dict）'
        return parsed, None
    return {}, 'args 必须是 JSON 对象（dict）'


REPORT_PERIOD_VALUES = {'daily', 'weekly', 'monthly'}


def _validate_subscription_report_args(args: dict[str, Any], func_name: str) -> str | None:
    if func_name != 'push_subscription_report':
        return None

    report_period = args.get('report_period')
    if isinstance(report_period, list):
        values = [str(item).strip().lower() for item in report_period if str(item).strip()]
        if len(values) != 1:
            return '报表周期只能选择一个'
        report_period = values[0]
    else:
        report_period = str(report_period or '').strip().lower()

    if report_period not in REPORT_PERIOD_VALUES:
        return '报表周期必须是 daily、weekly 或 monthly'

    return None


def _get_required_arg_keys(func_meta: dict | None) -> list[str]:
    if not func_meta:
        return []
    required_keys = []
    for rule in func_meta.get('func_args_rule') or []:
        normalized_rule = _normalize_arg_rule(rule)
        if normalized_rule.get('required'):
            required_keys.append(normalized_rule['key'])
    return required_keys


def _validate_task_form(task_form: TaskForm) -> str | None:
    if not CRON_BASIC.fullmatch(task_form.task_cron or '') or not croniter.is_valid(task_form.task_cron):
        return '定时表达式应包含 5 个字段'
    if not validate_cron_min_interval(task_form.task_cron):
        return '定时任务间隔不能少于 1 小时'
    if len(task_form.task_name) > 100 or len(task_form.task_args or '') > 20000:
        return '任务名称或参数过长'
    func_meta = find_func(task_form.task_func)
    if not func_meta:
        return f'未找到任务函数: {task_form.task_func}'

    parsed_args, parse_error = _parse_task_args(task_form.task_args)
    if parse_error:
        return parse_error

    is_valid, message = validate_func_args(parsed_args, _get_required_arg_keys(func_meta))
    if not is_valid:
        return message

    report_error = _validate_subscription_report_args(parsed_args, task_form.task_func)
    if report_error:
        return report_error

    return None

CRON_BASIC = re.compile(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$')


def validate_cron_min_interval(
        cron_expr: str,
        min_interval_seconds: int = 3600,
        horizon_hours: int = 48
) -> bool:
    base = datetime.now()
    end_time = base + timedelta(hours=horizon_hours)

    try:
        itr = croniter(cron_expr, base)
    except Exception:
        logger.error('非法的cron表达式')
        return False

    prev_time = itr.get_next(datetime)

    while True:
        next_time = itr.get_next(datetime)

        if next_time > end_time:
            break

        interval = (next_time - prev_time).total_seconds()
        if interval < min_interval_seconds:
            return False

        prev_time = next_time

    return True


def add_task(db: Session, task_form: TaskForm):
    validation_error = _validate_task_form(task_form)
    if validation_error:
        return error(validation_error)
    if task_form.enable and db.query(Task).filter(Task.enable.is_(True)).count() >= 64:
        return error('最多启用 64 个定时任务')
    task = Task(**task_form.model_dump(exclude={'id'}))
    db.add(task)
    db.flush()
    db.commit()
    restart_scheduler()
    return success(task)


def update_task(db: Session, task_form: TaskForm):
    validation_error = _validate_task_form(task_form)
    if validation_error:
        return error(validation_error)
    task = db.query(Task).filter_by(id=task_form.id).first()
    if not task:
        return error('任务不存在')
    if task_form.enable and not task.enable and db.query(Task).filter(Task.enable.is_(True)).count() >= 64:
        return error('最多启用 64 个定时任务')

    task.task_name = task_form.task_name
    task.task_func = task_form.task_func
    task.task_args = task_form.task_args
    task.task_cron = task_form.task_cron
    task.enable = task_form.enable
    task.push_enable = task_form.push_enable
    task.push_title_template = task_form.push_title_template
    task.push_message_template = task_form.push_message_template
    db.flush()
    db.commit()
    restart_scheduler()
    return success(task)


def delete_task(db: Session, task_id):
    task = db.get(Task, task_id)
    if task:
        from ...core.runtime import get_runtime
        get_runtime().cancel(task_key='task:' + str(task.id))
        db.delete(task)
        db.commit()
        restart_scheduler()
    return success()


def run_async_in_thread(async_func, **kwargs):
    """
    在线程中运行 async 函数
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func(**kwargs))
    loop.close()


def _run_task_in_thread(func, kwargs: dict[str, Any], task_id: int | None):
    mark_task_running(task_id)
    try:
        func(**kwargs)
    finally:
        unmark_task_running(task_id)


def _run_async_task_in_thread(async_func, kwargs: dict[str, Any], task_id: int | None):
    mark_task_running(task_id)
    try:
        run_async_in_thread(async_func=async_func, **kwargs)
    finally:
        unmark_task_running(task_id)


def get_running_tasks():
    from ...core.runtime import get_runtime
    runtime = get_runtime()
    with runtime.lock:
        keys = tuple(runtime.active_keys)
    task_ids = [int(key[5:]) for key in keys if isinstance(key, str) and key.startswith('task:') and key[5:].isdigit()]
    return success({
        'task_ids': sorted(set(task_ids)),
    })


def run_task(db: Session, task_id: int):
    task = db.get(Task, task_id)
    if not task:
        return error('任务不存在')

    if is_task_running(task.id):
        return error('任务正在执行中，请稍后再试')

    kwargs, parse_error = _parse_task_args(task.task_args)
    if parse_error:
        return error(parse_error)

    func = find_func(task.task_func)
    if not func:
        return error(f'未找到任务函数: {task.task_func}')

    task_args = copy.deepcopy(kwargs)
    kwargs['_task_context'] = {
        'task_id': task.id,
        'task_name': task.task_name,
        'task_func': task.task_func,
        'task_cron': task.task_cron,
        'task_args': task_args,
        'push_enable': bool(task.push_enable),
        'push_title_template': task.push_title_template,
        'push_message_template': task.push_message_template,
    }
    from ...core.runtime import get_runtime
    try:
        job = get_runtime().submit(task.task_name, func['func'], task_key='task:' + str(task.id), **kwargs)
    except ValueError as exc:
        return error(str(exc))
    return success({
        'running': True,
        'task_id': task.id,
        'job_id': job['id'],
    })


def page_task(db: Session, params: TaskLogFilter):
    stmt = select(TaskLog)

    if params.task_func:
        stmt = stmt.where(TaskLog.task_func.like(f'%{params.task_func}%'))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(total_stmt).scalar_one()

    offset = (params.page - 1) * params.page_size

    items_stmt = (
        stmt
        .order_by(TaskLog.id.desc())
        .offset(offset)
        .limit(params.page_size)
    )

    items = db.execute(items_stmt).scalars().all()
    return success({
        'total': total,
        'items': items
    })


def list_func(db: Session):
    rules = db.query(Rule).all()
    options = [{'label': str(rule.id), 'value': str(rule.id)} for rule in rules]
    func_map = copy.deepcopy(FUNC_MAP)

    serialized_func_map = []
    for item in func_map:
        serialized_item = {key: value for key, value in item.items() if key != 'func'}
        serialized_item['func_args_rule'] = [
            _normalize_arg_rule(rule) for rule in serialized_item.get('func_args_rule') or []
        ]

        if serialized_item['func_name'] == 'download_by_route':
            for arg in serialized_item['func_args_rule']:
                if arg['key'] == 'rule_id_list':
                    arg['options'] = options
                    break

        serialized_func_map.append(serialized_item)

    return success(serialized_func_map)
