import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ...enums import SystemConfigEnum
from ...models import Config

DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG = {
    'earliest_release_date': None,
    'exclude_vr': False,
    'max_coactors': None,
    'max_page': None,
    'replace_max_page': None,
    'is_single': False,
    'number_prefix_blacklist': [],
    'keyword_blacklist': [],
}


def _int_or_none(value: Any) -> int | None:
    if value in [None, '']:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_prefix(value: Any) -> str | None:
    normalized = str(value or '').strip().upper()
    return normalized or None


def normalize_number_prefix_blacklist(values: Any) -> list[str]:
    if values in [None, '']:
        return []

    if isinstance(values, str):
        candidates = re.split(r'[\s,;，；、]+', values)
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        candidates = [values]

    normalized_values: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_prefix(candidate)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)
    return normalized_values


def _normalize_keyword(value: Any) -> str | None:
    normalized = str(value or '').strip()
    return normalized or None


def normalize_keyword_blacklist(values: Any) -> list[str]:
    if values in [None, '']:
        return []

    if isinstance(values, str):
        candidates = re.split(r'[\s,;，；、]+', values)
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        candidates = [values]

    normalized_values: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_keyword(candidate)
        if not normalized:
            continue
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_values.append(normalized)
    return normalized_values


def normalize_subscribe_preference_config(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    earliest_release_date = str(payload.get('earliest_release_date') or '').strip() or None
    return {
        'earliest_release_date': earliest_release_date,
        'exclude_vr': bool(payload.get('exclude_vr', False)),
        'max_coactors': _int_or_none(payload.get('max_coactors')),
        'max_page': _int_or_none(payload.get('max_page')),
        'replace_max_page': _int_or_none(payload.get('replace_max_page')),
        'is_single': bool(payload.get('is_single', False)),
        'number_prefix_blacklist': normalize_number_prefix_blacklist(payload.get('number_prefix_blacklist')),
        'keyword_blacklist': normalize_keyword_blacklist(payload.get('keyword_blacklist')),
    }


def get_subscribe_preference_config(db: Session) -> dict[str, Any]:
    config = db.query(Config).filter(Config.key == SystemConfigEnum.SUBSCRIBE_PREFERENCE_CONFIG.value).first()
    if not config or not config.content:
        return dict(DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG)
    try:
        payload = json.loads(str(config.content))
    except Exception:
        return dict(DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG)
    normalized = normalize_subscribe_preference_config(payload)
    return {**DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG, **normalized}


def is_movie_number_prefix_blocked(number: str | None, blacklist: list[str] | None) -> bool:
    if not number or not blacklist:
        return False

    normalized_number = str(number).strip().upper()
    compact_number = re.sub(r'[^A-Z0-9]+', '', normalized_number)
    for prefix in blacklist:
        normalized_prefix = _normalize_prefix(prefix)
        if not normalized_prefix:
            continue
        compact_prefix = re.sub(r'[^A-Z0-9]+', '', normalized_prefix)
        if normalized_number.startswith(normalized_prefix):
            return True
        if compact_prefix and compact_number.startswith(compact_prefix):
            return True
    return False
