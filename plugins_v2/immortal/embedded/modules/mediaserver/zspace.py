import time
from http.cookies import SimpleCookie
from urllib.parse import quote

from ...core.runtime import get_runtime

from ...enums import MediaServerEnum
from ...modules.mediaserver.base import BaseMediaServer
from ...utils.log import logger


class ZSpaceMediaServer(BaseMediaServer):
    """
    极影视（ZSpace）媒体服务器
    """

    name = MediaServerEnum.ZSPACE.value

    def _build_url(self, path: str) -> str:
        base = (self.config.get("url") or "").rstrip("/")
        return f"{base}{path}"

    @staticmethod
    def _extract_cookie_value(cookie: str, key: str) -> str:
        parsed = SimpleCookie()
        try:
            parsed.load(cookie or "")
            if key in parsed:
                return parsed[key].value
        except Exception:
            # Fallback to manual parsing for non-standard cookie formats.
            pass

        parts = (cookie or "").split(";")
        for part in parts:
            part = part.strip()
            prefix = f"{key}="
            if part.startswith(prefix):
                return part[len(prefix):]
        return ""

    @staticmethod
    def _normalize_cookie_header(cookie: str) -> str:
        # requests rejects header values with leading whitespace or line breaks.
        if not cookie:
            return ""
        normalized = cookie.replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()
        return normalized

    @staticmethod
    def _generate_rnd() -> str:
        return f"{time.time() * 1000:.3f}".replace(".", "_", 1)

    def has_movie_by_number(self, number: str) -> bool:
        url = self.config.get("url")
        cookie = self._normalize_cookie_header(self.config.get("cookie") or "")
        if not url or not cookie or not number:
            if not number:
                return False
            raise ValueError('极影视地址或 Cookie 未配置')

        try:
            req_url = self._build_url(f"/zvideo/search/index?&rnd={self._generate_rnd()}&webagent=v2")
            nasid = self._extract_cookie_value(cookie, "nas_id") or self._extract_cookie_value(cookie, "nasid")
            data = {
                "key_word": number,
                "plat": self._extract_cookie_value(cookie, "plat"),
                "version": self._extract_cookie_value(cookie, "version"),
                "device_id": self._extract_cookie_value(cookie, "device_id"),
                "device": self._extract_cookie_value(cookie, "device"),
                "_l": "zh_cn",
                "token": self._extract_cookie_value(cookie, "token"),
                "nasid": nasid,
            }
            referrer = self._build_url(
                f"/apphome_video/video/search?keyword={quote(number)}&classification_id=&from=sideBar"
            )
            headers = {
                "Cookie": cookie,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN",
                "Referer": referrer,
                "Referrer-Policy": "strict-origin-when-cross-origin",
            }

            resp = get_runtime().request('POST', req_url, use_proxy=False, data=data, headers=headers, timeout=10)
            resp.raise_for_status()

            payload = resp.json() or {}
            if str(payload.get("code") or "") != "200":
                raise ValueError('极影视拒绝了媒体库查询')

            data_node = payload.get("data") or {}
            collection_items = data_node.get("collection") or []
            video_items = data_node.get("video") or []
            target = number.lower()

            for item in [*collection_items, *video_items]:
                values = [
                    item.get("title") or "",
                    item.get("file_name") or "",
                    item.get("file_path") or "",
                    item.get("encrypted_path") or "",
                ]
                combined = " ".join(str(value) for value in values if value).lower()
                if self.matches_number(number, combined):
                    return True
            return False
        except Exception as exc:
            raise RuntimeError('极影视媒体库查询失败') from exc
