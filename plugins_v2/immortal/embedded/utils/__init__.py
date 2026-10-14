import json
import re
import secrets
import string
from datetime import date, datetime
from typing import Dict, get_origin, get_args, Union, Any, List
from urllib.parse import urlparse

from ..utils.log import logger
from ..core.runtime import get_runtime

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
)


def _parse_date(value: str, target_type):
    # 先尝试 isoformat（最快）
    try:
        if target_type is date:
            return date.fromisoformat(value)
        if target_type is datetime:
            return datetime.fromisoformat(value)
    except ValueError:
        pass

    # 再兜底 strptime
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date() if target_type is date else dt
        except ValueError:
            continue

    raise ValueError(f"Invalid date format: {value}")


def dict_trans_obj(source: Dict, target: object):
    if not source or not target:
        return

    annotations = getattr(target, "__annotations__", None)
    if not annotations:
        return

    for name, field_type in annotations.items():
        if name not in source:
            continue

        value = source.get(name)
        if value is None:
            setattr(target, name, None)
            continue

        origin = get_origin(field_type)
        args = get_args(field_type)
        if origin is Union and len(args) == 2 and type(None) in args:
            field_type = args[0] if args[1] is type(None) else args[1]

        try:
            if field_type in (date, datetime) and isinstance(value, str):
                value = _parse_date(value.strip(), field_type)

        except ValueError as e:
            raise ValueError(
                f"Invalid date format for field '{name}': {value}"
            ) from e

        if origin in (list, List):
            if isinstance(value, str):
                value = value.strip()

                if not value:
                    value = []
                elif value.startswith("{") and value.endswith("}"):
                    inner = value[1:-1]
                    inner = inner.replace('"', '')
                    value = [v.strip() for v in inner.split(",") if v.strip()]
                else:
                    value = [value]

        setattr(target, name, value)


def get_host_and_port(url):
    parsed_url = urlparse(url)
    host = parsed_url.hostname
    port = parsed_url.port

    # 如果端口号为空，则根据方案设置默认端口
    if port is None:
        if parsed_url.scheme == 'http':
            port = 80
        elif parsed_url.scheme == 'https':
            port = 443

    return host, port


def serialize_result(result: Any) -> str:
    """
    将 dict / list[dict] 安全序列化为字符串，用于数据库存储
    """

    try:
        return json.dumps(
            result,
            ensure_ascii=False,  # 支持中文
            default=str,  # datetime / Decimal 等兜底转字符串
        )
    except Exception as e:
        # 理论上不会发生，但作为最后保险
        return json.dumps(
            {"_serialize_error": str(e)},
            ensure_ascii=False
        )


def generate_secure_random_string(length: int) -> str:
    # 选择字符集（包括字母和数字）
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def get_host_port(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc


def extract_infohash(magnet: str) -> str | None:
    m = re.search(r'urn:btih:([a-fA-F0-9]{40}|[a-zA-Z0-9]{32})', magnet)
    if not m:
        return None
    return m.group(1).lower()


def safe_get(url, **kwargs):
    return safe_request(url, "GET", **kwargs)


def safe_post(url, **kwargs):
    return safe_request(url, "POST", **kwargs)


def safe_request(url, method='GET', **kwargs):
    try:
        if method.upper() not in {'GET', 'POST'}:
            raise ValueError(f"Unsupported method: {method}")
        runtime = get_runtime()
        runtime.check_cancelled()
        kwargs.setdefault('timeout', 20)
        return runtime.request(method.upper(), url, **kwargs)
    except Exception as e:
        # Do not include credentials, query strings or upstream response bodies.
        logger.error(f"网络请求失败：{type(e).__name__}")
    return None


def safe_text(node):
    return node.text().strip() if node else ""

def safe_attr(node, attr):
    return node.attr(attr) if node else ""
