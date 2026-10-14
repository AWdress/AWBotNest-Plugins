"""Explicit plugin settings; never read or modify the host environment."""
from pathlib import Path
from types import SimpleNamespace
import threading

root_path = str(Path(__file__).resolve().parents[2])
data_path = ''


class ConfigManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._settings = SimpleNamespace(PROXY=None, FLARE_SOLVERR_URL=None, JAVDB_API_HOST=None)

    def get(self):
        with self._lock:
            return self._settings

    def reload(self, data):
        if not isinstance(data, dict):
            raise ValueError("系统配置必须是对象")
        forbidden = set(data) - {'PROXY', 'FLARE_SOLVERR_URL', 'JAVDB_API_HOST'}
        if forbidden:
            raise ValueError("数据库、机器人和服务监听由平台管理，不能在内置页面设置")
        values = {key: (str(data.get(key) or '').strip() or None) for key in ('PROXY', 'FLARE_SOLVERR_URL', 'JAVDB_API_HOST')}
        from urllib.parse import urlsplit
        for key, value in values.items():
            if value and urlsplit(value).scheme not in ({'http', 'https', 'socks5', 'socks5h'} if key == 'PROXY' else {'http', 'https'}):
                raise ValueError("系统配置中的地址格式无效")
        with self._lock:
            self._settings = SimpleNamespace(**values)


config_manager = ConfigManager()


def configure(path):
    global data_path
    data_path = str(Path(path).resolve())
    config_manager.reload({})
