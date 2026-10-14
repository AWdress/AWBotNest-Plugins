"""Transmission RPC with explicit rejected-session retry and bounded requests."""
from ...core.runtime import get_runtime
from ...enums import DownloadClientEnum
from .base import BaseDownloader


class TransmissionClient(BaseDownloader):
    name = DownloadClientEnum.TRANSMISSION.value

    def __init__(self, conf):
        self.config = dict(conf or {})
        self.session_id = ''

    def _rpc(self, method, arguments):
        runtime = get_runtime()
        runtime.check_cancelled()
        base = self.config.get('url', '').rstrip('/')
        if not base:
            raise ValueError('Transmission 地址未配置')
        url = base if base.endswith('/transmission/rpc') else base + '/transmission/rpc'
        for attempt in range(2):
            response = runtime.request('POST', url, use_proxy=False, timeout=20,
                                      auth=(self.config.get('username', ''), self.config.get('password', '')),
                                      headers={'X-Transmission-Session-Id': self.session_id},
                                      json={'method': method, 'arguments': arguments})
            if response.status_code == 409 and attempt == 0:
                self.session_id = response.headers.get('X-Transmission-Session-Id', '')
                if not self.session_id:
                    raise RuntimeError('Transmission 缺少会话标识')
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get('result') != 'success':
                raise RuntimeError('Transmission 拒绝了请求')
            return data.get('arguments') or {}
        raise RuntimeError('Transmission 会话认证失败')

    def download(self, magnet, save_path):
        get_runtime().require_download()
        result = self._rpc('torrent-add', {'filename': magnet, 'download-dir': save_path})
        if result.get('torrent-added') or result.get('torrent-duplicate'):
            return True, None
        return False, 'Transmission 未返回下载任务'

    def analyze_size(self, magnet):
        from ...utils import extract_infohash
        torrent_hash = extract_infohash(magnet)
        if not torrent_hash:
            return None
        data = self._rpc('torrent-get', {'ids': [torrent_hash], 'fields': ['totalSize']})
        torrents = data.get('torrents') or []
        size = torrents[0].get('totalSize') if torrents else None
        return int(size / 1024 / 1024) if isinstance(size, (int, float)) and size > 0 else None

    def close(self):
        self.session_id = ''
