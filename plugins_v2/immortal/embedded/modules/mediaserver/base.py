from abc import ABC, abstractmethod
import re


class BaseMediaServer(ABC):
    """
    媒体服务器基础类
    """

    config: dict
    name: str

    def __init__(self, conf: dict):
        self.config = conf or {}

    @staticmethod
    def matches_number(number, text):
        # Prefixes such as ABC-12 must not match ABC-123 or XABC-12.
        pattern = re.escape(str(number)).replace(r'\-', r'[-_\s]?')
        return bool(re.search(r'(?<![A-Za-z0-9])' + pattern + r'(?![A-Za-z0-9])',
                              str(text), re.IGNORECASE))

    @abstractmethod
    def has_movie_by_number(self, number: str) -> bool:
        """
        根据番号查询影片是否存在

        :param number: 影片番号
        :return: 存在返回 True，否则 False
        """
        raise NotImplementedError
