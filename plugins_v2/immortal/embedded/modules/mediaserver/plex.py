from urllib.parse import urlencode

import xml.etree.ElementTree as ET
from ...core.runtime import get_runtime

from ...enums import MediaServerEnum
from ...modules.mediaserver.base import BaseMediaServer
from ...utils.log import logger


class PlexMediaServer(BaseMediaServer):
    """
    Plex 媒体服务器
    """

    name = MediaServerEnum.PLEX.value

    def _build_url(self, path: str, query: dict | None = None) -> str:
        base = (self.config.get("url") or "").rstrip("/")
        url = f"{base}{path}"
        if query:
            qs = urlencode(query)
            url = f"{url}?{qs}"
        return url

    def has_movie_by_number(self, number: str) -> bool:
        if not number:
            return False
        if not self.config.get('url') or not self.config.get('token'):
            raise ValueError('Plex 地址或密钥未配置')

        try:
            library_id = self.config.get("library_id")
            query = {
                "query": number,
            }

            if library_id:
                path = f"/library/sections/{library_id}/all"
            else:
                path = "/search"

            url = self._build_url(path, query)
            resp = get_runtime().request('GET', url, use_proxy=False, timeout=10,
                                         headers={'X-Plex-Token': self.config['token']})
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            return any(self.matches_number(number, node.get(key, ''))
                       for node in root.iter() for key in ('title', 'originalTitle', 'file'))
        except Exception as exc:
            raise RuntimeError('Plex 媒体库查询失败') from exc
