"""Logger facade without global loguru sink mutation or token leakage."""
from collections import deque
from datetime import datetime
import logging
import threading

from ...runtime import get_runtime, safe_error

_lines = deque(maxlen=2000)
_lock = threading.Lock()
_line_number = 0


class Logger:
    def _log(self, level, message, *args, **kwargs):
        global _line_number
        message = str(message)
        if args:
            try:
                message = message.format(*args)
            except (ValueError, KeyError, IndexError):
                message = message % args
        message = safe_error(message)
        with _lock:
            _line_number += 1
            _lines.append({'line_no': _line_number, 'text': datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + level.upper() + ' ' + message})
        try:
            target = get_runtime().ctx.log
        except RuntimeError:
            target = logging.getLogger('awbotnest.plugin.immortal')
        getattr(target, level)(message)

    def info(self, message, *args, **kwargs): self._log('info', message, *args, **kwargs)
    def debug(self, message, *args, **kwargs): self._log('debug', message, *args, **kwargs)
    def warning(self, message, *args, **kwargs): self._log('warning', message, *args, **kwargs)
    def error(self, message, *args, **kwargs): self._log('error', message, *args, **kwargs)
    def exception(self, message, *args, **kwargs): self._log('error', message, *args, **kwargs)
    def success(self, message, *args, **kwargs): self._log('info', message, *args, **kwargs)


logger = Logger()


def recent_lines():
    with _lock:
        return [dict(row) for row in _lines]


def total_lines():
    with _lock:
        return _line_number
