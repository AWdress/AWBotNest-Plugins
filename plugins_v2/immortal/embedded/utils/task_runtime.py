import threading
from datetime import datetime

_running_tasks_lock = threading.Lock()
_running_tasks: dict[int, dict[str, object]] = {}


def mark_task_running(task_id: int | None):
    if task_id is None:
        return
    with _running_tasks_lock:
        state = _running_tasks.get(task_id)
        if state is None:
            _running_tasks[task_id] = {
                'count': 1,
                'started_at': datetime.now(),
            }
            return
        state['count'] = int(state.get('count', 0)) + 1


def unmark_task_running(task_id: int | None):
    if task_id is None:
        return
    with _running_tasks_lock:
        state = _running_tasks.get(task_id)
        if state is None:
            return
        next_count = int(state.get('count', 0)) - 1
        if next_count <= 0:
            _running_tasks.pop(task_id, None)
            return
        state['count'] = next_count


def is_task_running(task_id: int | None) -> bool:
    if task_id is None:
        return False
    with _running_tasks_lock:
        return task_id in _running_tasks


def list_running_task_ids() -> list[int]:
    with _running_tasks_lock:
        return sorted(_running_tasks.keys())
