# =============================================================================
# auto_subscribe 私有辅助：榜单来源基类 + 注册表
#
# 各来源子类以类属性声明 provider_id / provider_name，用 @register 自注册；
# fetch() 是同步生成器，产出 RankMediaItem（整源抓取失败向上抛，单条失败内部
# try/except continue）。同步 + httpx.Client：整轮跑在 asyncio.to_thread 里，
# 不阻塞事件循环。
# =============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Type

from ._models import RankMediaItem

# 通用请求超时（秒）。
DEFAULT_TIMEOUT = 30


class RankProvider(ABC):
    """榜单来源基类。"""

    provider_id: str = ""
    provider_name: str = ""

    @abstractmethod
    def fetch(self, options: dict) -> Iterator[RankMediaItem]:
        """抓取 + 解析榜单，产出标准化条目（可能未带 tmdb id）。"""
        raise NotImplementedError

    @staticmethod
    def as_list(value) -> List[str]:
        """把多选值统一成字符串列表（兼容逗号分隔字符串）。"""
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    @staticmethod
    def to_int(value, default: int = 0) -> int:
        """安全转 int，失败回退默认值。"""
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default


# 来源注册表：provider_id -> 类。
REGISTRY: Dict[str, Type[RankProvider]] = {}


def register(cls: Type[RankProvider]) -> Type[RankProvider]:
    """把来源类登记到注册表（按 provider_id）。"""
    if cls.provider_id:
        REGISTRY[cls.provider_id] = cls
    return cls


def get_provider(provider_id: str) -> RankProvider | None:
    """按 id 取来源实例；未知返回 None。"""
    cls = REGISTRY.get(provider_id)
    return cls() if cls is not None else None
