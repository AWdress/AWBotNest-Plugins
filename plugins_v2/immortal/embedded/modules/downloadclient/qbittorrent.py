"""Bounded qBittorrent API adapter; never creates temporary probe torrents."""
from ...core.runtime import get_runtime
from ...enums import DownloadClientEnum
from .base import BaseDownloader


class QBitTorrentClient(BaseDownloader):
    name = DownloadClientEnum.QBITTORRENT.value

    def __init__(self, conf):
        self.config = dict(conf or {})
        self.cookies = {}

    def _request(self, method, path, **kwargs):
        runtime = get_runtime()
        runtime.check_cancelled()
        response = runtime.request(method, self.config['url'].rstrip('/') + path,
                                   use_proxy=False, cookies=self.cookies, timeout=20, **kwargs)
        response.raise_for_status()
        return response

    def login_qb(self, force=False):
        if self.cookies and not force:
            return True
        if not self.config.get('url'):
            return False
        response = self._request('POST', '/api/v2/auth/login', data={
            'username': self.config.get('username', ''),
            'password': self.config.get('password', ''),
        })
        if response.text.strip() != 'Ok.':
            return False
        self.cookies = dict(response.cookies)
        return True

    def download(self, magnet, save_path):
        get_runtime().require_download()
        if not self.login_qb():
            return False, 'qBittorrent 认证失败'
        response = self._request('POST', '/api/v2/torrents/add', data={
            'urls': magnet, 'savepath': save_path,
        })
        if response.text.strip() == 'Ok.':
            return True, None
        return False, 'qBittorrent 拒绝了下载请求'

    def analyze_size(self, magnet):
        # Existing metadata only: never add, pause or remove torrents.
        from ...utils import extract_infohash
        torrent_hash = extract_infohash(magnet)
        if not torrent_hash or not self.login_qb():
            return None
        data = self._request('GET', '/api/v2/torrents/info', params={'hashes': torrent_hash}).json()
        if isinstance(data, list) and data:
            size = data[0].get('total_size')
            return int(size / 1024 / 1024) if isinstance(size, (int, float)) and size > 0 else None
        return None

    def close(self):
        self.cookies.clear()
