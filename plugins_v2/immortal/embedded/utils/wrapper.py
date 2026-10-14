import functools
import json
import re
import time
import traceback
from datetime import datetime
from typing import Any

from jinja2.sandbox import SandboxedEnvironment

_templates = SandboxedEnvironment()


def Template(text):
    return _templates.from_string(text)

from ..core.database import session_scope
from ..models.task_log import TaskLog
from ..modules.notification.manager import pushManager
from ..utils import logger, serialize_result
from ..utils.task_runtime import mark_task_running, unmark_task_running

DEFAULT_PUSH_MESSAGE_TEMPLATE = '''任务: {{ task_name }}
状态: {{ status_text }}
耗时: {{ duration_seconds }}s

{% if count is defined %}数量: {{ count }}
{% endif %}{% if saved_count is defined %}保存数: {{ saved_count }}
{% endif %}{% if completed is defined %}完成数: {{ completed }}
{% endif %}{% if failed is defined %}失败数: {{ failed }}
{% endif %}{% if success_count is defined %}成功数: {{ success_count }}
{% endif %}{% if fail_count is defined %}失败数: {{ fail_count }}
{% endif %}{% if total is defined %}总数: {{ total }}
{% endif %}{% if message is defined and message %}说明: {{ message }}
{% endif %}{% if error_last_line %}错误: {{ error_last_line }}
{% endif %}'''
RESULT_SUMMARY_KEYS = ['count', 'saved_count', 'completed', 'failed', 'success_count', 'fail_count', 'total']


class _TemplateSafeDict(dict):
    def __getitem__(self, key):
        if isinstance(key, slice):
            return []
        return super().__getitem__(key)


def _to_template_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _TemplateSafeDict({k: _to_template_value(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_to_template_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_template_value(item) for item in value)
    if isinstance(value, set):
        return [_to_template_value(item) for item in value]
    return value


def _normalize_task_context(kwargs: dict) -> dict:
    context = kwargs.pop('_task_context', None) or {}
    return context if isinstance(context, dict) else {}


def _resolve_task_meta(func_name: str):
    from ..scheduler import find_func

    func_meta = find_func(func_name) or {}
    return {
        'func_name': func_name,
        'func_label': func_meta.get('func_label') or func_name,
    }


def _build_execute_flag(success: bool, result: Any) -> str:
    if not success:
        return 'failed'
    if result in (None, [], {}, ()):
        return 'empty'
    return 'success'


def _result_failure(result: Any) -> str | None:
    """A returned business rejection is a failure even without an exception."""
    from ...runtime import result_failure
    return result_failure(result)


def _should_push(context: dict) -> bool:
    return bool(context.get('push_enable'))


def _compact_json(value: Any) -> str:
    text = serialize_result(value)
    if len(text) <= 600:
        return text
    return f'{text[:600]}...'


def _normalize_template_key(key: Any) -> str:
    normalized = re.sub(r'[^0-9a-zA-Z_]+', '_', str(key)).strip('_')
    if not normalized:
        return ''
    if normalized[0].isdigit():
        return f'field_{normalized}'
    return normalized


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(serialize_result(value))
    except Exception:
        return serialize_result(value)


def _flatten_mapping(source: dict[str, Any], prefix: str) -> dict[str, Any]:
    flattened: dict[str, Any] = {}

    def visit(value: Any, current_prefix: str):
        if not isinstance(value, dict):
            return
        for key, item in value.items():
            normalized = _normalize_template_key(key)
            if not normalized:
                continue
            flat_key = f'{current_prefix}_{normalized}' if current_prefix else normalized
            flattened.setdefault(flat_key, item)
            visit(item, flat_key)

    visit(source, prefix)
    return flattened


def _extract_error_last_line(error_msg: str | None) -> str:
    if not error_msg:
        return ''
    return error_msg.strip().splitlines()[-1]


def _build_result_summary(result: Any, error_msg: str | None) -> list[str]:
    lines: list[str] = []
    if isinstance(result, dict):
        for key in RESULT_SUMMARY_KEYS:
            if key in result:
                lines.append(f'{key}: {result[key]}')
        if 'message' in result and result['message']:
            lines.append(f'说明: {result["message"]}')
    elif isinstance(result, list):
        lines.append(f'结果数: {len(result)}')
        preview = result[:3]
        if preview:
            lines.append(f'摘要: {_compact_json(preview)}')
    elif result not in (None, '', [], {}):
        lines.append(f'结果: {_compact_json(result)}')

    if error_msg:
        lines.append('错误:')
        lines.append(_extract_error_last_line(error_msg))

    return lines


def _format_push_message(
    meta: dict,
    context: dict,
    success: bool,
    duration: int,
    result: Any,
    error_msg: str | None,
):
    task_name = context.get('task_name') or meta['func_label']
    status_text = '成功' if success else '失败'
    lines = [
        f'任务: {task_name}',
        f'函数: {meta["func_name"]}',
        f'状态: {status_text}',
        f'耗时: {duration}s',
    ]
    lines.extend(_build_result_summary(result, error_msg))
    return '\n'.join(lines)


def _build_template_context(
    meta: dict,
    context: dict,
    start_time: datetime,
    end_time: datetime,
    duration: int,
    result: Any,
    success: bool,
    error_msg: str | None,
) -> dict[str, Any]:
    status = _build_execute_flag(success, result)
    status_text = '成功' if success else '失败'
    task_args_value = _json_safe(context.get('task_args') or {})
    task_args = task_args_value if isinstance(task_args_value, dict) else {}
    task_args_template = _to_template_value(task_args)
    result_value = _json_safe(result)
    result_template_value = _to_template_value(result_value)
    summary_lines = _build_result_summary(result_value, error_msg)
    error_last_line = _extract_error_last_line(error_msg)

    if isinstance(result_value, list):
        result_preview = _compact_json(result_value[:3])
    elif result_value in (None, '', [], {}):
        result_preview = ''
    else:
        result_preview = _compact_json(result_value)

    template_context: dict[str, Any] = {
        'task_id': context.get('task_id'),
        'task_name': context.get('task_name') or meta['func_label'],
        'task_func': context.get('task_func') or meta['func_name'],
        'task_label': meta['func_label'],
        'task_cron': context.get('task_cron') or '',
        'push_enable': bool(context.get('push_enable')),
        'status': status,
        'status_text': status_text,
        'success': success,
        'is_failed': not success,
        'is_empty': status == 'empty',
        'duration_seconds': duration,
        'duration_minutes': round(duration / 60, 2),
        'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
        'start_time_iso': start_time.isoformat(),
        'end_time_iso': end_time.isoformat(),
        'error': error_msg or '',
        'error_last_line': error_last_line,
        'summary_lines': summary_lines,
        'summary_text': '\n'.join(summary_lines),
        'task_args': task_args_template,
        'args': task_args_template,
        'task_args_json': serialize_result(task_args_value),
        'result': result_template_value,
        'result_json': serialize_result(result),
        'result_type': type(result).__name__ if result is not None else 'NoneType',
        'result_size': len(result_value) if isinstance(result_value, (dict, list, tuple, set)) else 0,
        'result_preview': result_preview,
        'task': {
            'id': context.get('task_id'),
            'name': context.get('task_name') or meta['func_label'],
            'func': context.get('task_func') or meta['func_name'],
            'label': meta['func_label'],
            'cron': context.get('task_cron') or '',
            'args': task_args,
        },
        'meta': {
            'func_name': meta['func_name'],
            'func_label': meta['func_label'],
        },
    }

    for key, value in _flatten_mapping(task_args, 'arg').items():
        template_context.setdefault(key, _to_template_value(value))

    if isinstance(result_value, dict):
        for key, value in result_value.items():
            normalized = _normalize_template_key(key)
            if normalized and normalized not in template_context:
                template_context[normalized] = _to_template_value(value)
        for key, value in _flatten_mapping(result_value, 'result').items():
            template_context.setdefault(key, _to_template_value(value))

    return template_context


def _render_template(template_text: str | None, template_context: dict[str, Any], fallback: str) -> str:
    if not template_text:
        return fallback
    try:
        rendered = Template(template_text).render(**template_context).strip()
        return rendered or fallback
    except Exception:
        logger.exception('任务推送模板渲染失败')
        return fallback


def _persist_task_log(
    meta: dict,
    context: dict,
    start_time: datetime,
    end_time: datetime,
    duration: int,
    result: Any,
    success: bool,
    error_msg: str | None,
):
    task_log = TaskLog(
        task_name=context.get('task_name') or meta['func_label'],
        task_func=meta['func_name'],
        start_time=start_time,
        end_time=end_time,
        execute_seconds=duration,
        execute_result=serialize_result(result),
        execute_flag=_build_execute_flag(success, result),
        success=success,
        error=error_msg,
    )

    with session_scope() as session:
        session.add(task_log)


def _handle_push(
    meta: dict,
    context: dict,
    start_time: datetime,
    end_time: datetime,
    success: bool,
    duration: int,
    result: Any,
    error_msg: str | None,
):
    if not _should_push(context):
        return

    template_context = _build_template_context(
        meta=meta,
        context=context,
        start_time=start_time,
        end_time=end_time,
        duration=duration,
        result=result,
        success=success,
        error_msg=error_msg,
    )
    default_message = _render_template(
        DEFAULT_PUSH_MESSAGE_TEMPLATE,
        template_context,
        _format_push_message(meta, context, success, duration, result, error_msg),
    )
    message = _render_template(context.get('push_message_template'), template_context, default_message)
    pushManager.send(message, title='📬 任务通知')


def task_monitor(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        context = _normalize_task_context(kwargs)
        meta = _resolve_task_meta(func.__name__)
        task_id = context.get('task_id')
        start_time = datetime.now()
        start_perf = time.perf_counter()

        result = None
        success = True
        error_msg = None

        mark_task_running(task_id)
        try:
            result = func(*args, **kwargs)
            error_msg = _result_failure(result)
            success = error_msg is None
            return result
        except BaseException:
            success = False
            error_msg = traceback.format_exc()
            raise
        finally:
            end_time = datetime.now()
            duration = int(time.perf_counter() - start_perf)
            try:
                try:
                    _persist_task_log(meta, context, start_time, end_time, duration, result, success, error_msg)
                except Exception:
                    logger.error('任务执行记录保存失败')
                try:
                    _handle_push(meta, context, start_time, end_time, success, duration, result, error_msg)
                except Exception:
                    logger.warning('任务通知发送失败')
            finally:
                unmark_task_running(task_id)

    return wrapper


def task_monitor_async(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        context = _normalize_task_context(kwargs)
        meta = _resolve_task_meta(func.__name__)
        task_id = context.get('task_id')
        start_time = datetime.now()
        start_perf = time.perf_counter()

        result = None
        success = True
        error_msg = None

        mark_task_running(task_id)
        try:
            result = await func(*args, **kwargs)
            error_msg = _result_failure(result)
            success = error_msg is None
            return result
        except BaseException:
            success = False
            error_msg = traceback.format_exc()
            raise
        finally:
            end_time = datetime.now()
            duration = int(time.perf_counter() - start_perf)
            try:
                try:
                    _persist_task_log(meta, context, start_time, end_time, duration, result, success, error_msg)
                except Exception:
                    logger.error('任务执行记录保存失败')
                try:
                    _handle_push(meta, context, start_time, end_time, success, duration, result, error_msg)
                except Exception:
                    logger.warning('任务通知发送失败')
            finally:
                unmark_task_running(task_id)

    return wrapper
