from ...core.runtime import get_runtime

from ...enums import MediaServerEnum
from ...modules.mediaserver.base import BaseMediaServer
from ...utils.log import logger


class JellyfinMediaServer(BaseMediaServer):
    """
    Jellyfin 媒体服务器
    """

    name = MediaServerEnum.JELLYFIN.value

    def _build_url(self, path: str) -> str:
        base = (self.config.get("url") or "").rstrip("/")
        return f"{base}{path}"

    def has_movie_by_number(self, number: str) -> bool:
        if not number:
            return False
        if not self.config.get('url') or not self.config.get('api_key'):
            raise ValueError('Jellyfin 地址或密钥未配置')

        try:
            user_id = self.config.get("user_id")
            if user_id:
                url = self._build_url(f"/Users/{user_id}/Items")
            else:
                url = self._build_url("/Items")

            params = {
                "SearchTerm": number,
                "Limit": 20,
                "Recursive": True,
                "Fields": "Path,OriginalTitle",
            }

            resp = get_runtime().request('GET', url, use_proxy=False, params=params, timeout=10,
                                         headers={'X-Emby-Token': self.config['api_key']})
            resp.raise_for_status()

            data = resp.json() or {}
            if not isinstance(data, dict) or not isinstance(data.get('Items', data.get('items')), list):
                raise ValueError('Jellyfin 返回了无效的媒体列表')
            items = data.get("Items") or data.get("items") or []
            target = number.lower()

            for item in items:
                values = [
                    item.get("Name") or item.get("name") or "",
                    item.get("OriginalTitle") or item.get("originalTitle") or "",
                    item.get("Path") or item.get("path") or "",
                    item.get("FileName") or item.get("fileName") or "",
                ]
                combined = " ".join(str(value) for value in values if value).lower()
                if self.matches_number(number, combined):
                    return True
            return False
        except Exception as exc:
            raise RuntimeError('Jellyfin 媒体库查询失败') from exc
