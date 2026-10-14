import importlib
import threading

from ...enums import DownloadClientEnum
from ...modules.downloadclient.base import BaseDownloader
from ...core.runtime import get_runtime
from .receipts import submit_once
from ...utils.log import logger


class DownloadManager:
    CLIENTS = {
        DownloadClientEnum.QBITTORRENT.value: ('.qbittorrent', 'QBitTorrentClient'),
        DownloadClientEnum.TRANSMISSION.value: ('.transmission', 'TransmissionClient'),
        DownloadClientEnum.THUNDER.value: ('.thunder', 'Thunder'),
        DownloadClientEnum.CLOUDDRIVE.value: ('.cloudnas.cloudnas', 'CloudNas'),
    }

    def _state(self):
        runtime = get_runtime()
        if not hasattr(runtime, '_download_manager_state'):
            runtime._download_manager_state = {'configs': {}, 'clients': {}, 'lock': threading.RLock()}
        return runtime._download_manager_state

    @property
    def downloaders(self):
        return list(self._state()['clients'].values())

    def register(self, downloader: BaseDownloader):
        state = self._state()
        with state['lock']:
            state['clients'][downloader.name] = downloader

    def _client(self, name):
        state = self._state()
        with state['lock']:
            if name in state['clients']:
                return state['clients'][name]
            config = state['configs'].get(name)
            spec = self.CLIENTS.get(name)
            if not config or not config.get('url') or not spec:
                return None
            try:
                module = importlib.import_module(spec[0], __package__)
                client = getattr(module, spec[1])(dict(config))
            except ImportError as exc:
                raise RuntimeError(f'下载器 {name} 的依赖未安装') from exc
            state['clients'][name] = client
            return client

    def download(self, downloader_name, magnet, save_path) -> tuple[bool, str | None]:
        runtime = get_runtime()
        runtime.require_download()
        runtime.check_cancelled()
        is_edk = isinstance(magnet, str) and magnet.startswith('ed2k://')
        if is_edk and downloader_name not in [DownloadClientEnum.THUNDER.value, DownloadClientEnum.CLOUDDRIVE.value]:
            logger.warning(f'action=download | client={downloader_name} | magnet={magnet} | reason=edk_not_supported')
            return False, 'ed2k 链接不支持该下载器'
        downloader = self._client(downloader_name)
        if downloader is not None:
            return submit_once(downloader_name, downloader.config.get('url', ''), magnet, save_path,
                               lambda: downloader.download(magnet, save_path))
        logger.error(f'action=download | client={downloader_name} | magnet={magnet} | save_path={save_path} | reason=downloader_not_found')
        return False, f'下载器 {downloader_name} 未找到'

    def analyze_size(self, magnet):
        # Never add/delete a torrent just to discover its size.
        get_runtime().check_cancelled()
        downloader = self._client(DownloadClientEnum.THUNDER.value)
        if downloader is not None:
            size = downloader.analyze_size(magnet)
            if size:
                return size
        logger.warning(f'action=analyze_size | magnet={magnet} | reason=all_downloaders_failed')
        return None

    def reload(self, name, config: dict):
        if name not in self.CLIENTS:
            raise ValueError('不支持的下载器')
        state = self._state()
        with state['lock']:
            old = state['clients'].pop(name, None)
            if old is not None and hasattr(old, 'close'):
                old.close()
            state['configs'][name] = dict(config or {})

    def close(self):
        state = self._state()
        with state['lock']:
            for client in state['clients'].values():
                if hasattr(client, 'close'):
                    client.close()
            state['clients'].clear()


downloadManager = DownloadManager()
