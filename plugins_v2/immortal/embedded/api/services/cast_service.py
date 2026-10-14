import json
import re

import requests
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...api.services.page_agent_service import load_page_agent_config
from ...core.portable_types import array_any_ilike, array_member
from ...models import Cast, CastSubscribe, Movie
from ...modules.crawler.avbase import av_base
from ...schemas.cast import CastSearchParam
from ...schemas.response import success
from ...utils.db_lock import acquire_cast_movie_write_lock
from ...utils.log import logger
from ...utils.proxy import build_requests_proxies


def _build_cast_search_items(rows):
    items = []
    for cast, subscribe in rows:
        cast_data = {
            'id': cast.id,
            'name': cast.name,
            'cn_name': cast.cn_name,
            'avatar': cast.avatar,
            'photo': cast.photo,
            'former_name': cast.former_name or [],
        }
        subscribe_data = None
        if subscribe:
            subscribe_data = {
                'id': subscribe.id,
                'cast_id': subscribe.cast_id,
                'status': subscribe.status,
                'max_coactors': subscribe.max_coactors,
                'max_page': subscribe.max_page,
                'replace_max_page': subscribe.replace_max_page,
                'is_single': bool(subscribe.is_single),
                'earliest_release_date': subscribe.earliest_release_date.isoformat() if subscribe.earliest_release_date else None,
                'exclude_vr': bool(subscribe.exclude_vr),
                'filter_id': subscribe.filter_id,
                'priority_id': subscribe.priority_id,
                'create_time': subscribe.create_time.strftime('%Y-%m-%d %H:%M:%S') if subscribe.create_time else '',
            }
        cast_data['subscribe'] = subscribe_data
        items.append(cast_data)
    return items



def _load_cast_rows(db: Session, cast_id: int):
    if not cast_id:
        return []
    return (
        db.query(Cast, CastSubscribe)
        .outerjoin(CastSubscribe, CastSubscribe.cast_id == Cast.id)
        .filter(Cast.id == cast_id)
        .all()
    )



def _find_local_cast(db: Session, aliases: list[str]) -> Cast | None:
    aliases = _unique_nonempty_strings(aliases)
    if not aliases:
        return None
    return (
        db.query(Cast)
        .filter(
            or_(
                Cast.name.in_(aliases),
                Cast.cn_name.in_(aliases),
                Cast.former_name.overlap(aliases),
            )
        )
        .order_by(Cast.id.asc())
        .first()
    )



def _upsert_cast_from_network(db: Session, talent: dict):
    if not talent:
        return None

    name = (talent.get('name') or '').strip()
    if not name:
        return None

    acquire_cast_movie_write_lock(db)

    aliases = []
    seen = set()
    for value in [talent.get('name'), *(talent.get('former_name') or [])]:
        alias = (value or '').strip()
        if not alias:
            continue
        lowered = alias.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        aliases.append(alias)

    cast = (
        db.query(Cast)
        .filter(
            or_(
                Cast.name.in_(aliases),
                Cast.former_name.overlap(aliases),
            )
        )
        .order_by(Cast.id.asc())
        .first()
    )
    if cast is None:
        cast = Cast(
            name=name,
            former_name=list(talent.get('former_name') or aliases),
            avatar=talent.get('avatar'),
        )
        db.add(cast)
        db.flush()
        return cast

    if talent.get('avatar'):
        cast.avatar = talent.get('avatar')

    former_names = list(cast.former_name or [])
    for former_name in aliases:
        if former_name and former_name not in former_names:
            former_names.append(former_name)
    cast.former_name = former_names
    db.flush()
    return cast



def _page_agent_enabled(config: dict) -> bool:
    return bool(
        config.get('enabled')
        and config.get('base_url')
        and config.get('api_key')
        and config.get('model')
    )



def _extract_json_object(content: str) -> dict:
    raw = str(content or '').strip()
    if not raw:
        return {}
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}



def _unique_nonempty_strings(values) -> list[str]:
    items = []
    seen = set()
    for value in values:
        normalized = str(value or '').strip()
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(normalized)
    return items



def _resolve_cast_name_candidates(keyword: str, db: Session) -> list[str]:
    normalized_keyword = str(keyword or '').strip()
    if not normalized_keyword:
        return []

    model_config = load_page_agent_config(db)
    if not _page_agent_enabled(model_config):
        return []

    try:
        response = requests.post(
            f"{str(model_config['base_url']).rstrip('/')}/chat/completions",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {model_config['api_key']}",
            },
            json={
                'model': model_config['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            '你是日本成人影片演员名字规范化助手。'
                            '当用户提供中文译名、昵称或不准确写法时，给出最可能用于资料库检索的准确日文名字。'
                            '只返回 JSON 对象，不要 markdown，不要解释。'
                            'JSON 格式固定为 {"exact_name":"","candidates":[""],"confidence":"high|medium|low"}。'
                            'candidates 按可能性排序，最多 3 个；无法判断时返回空字符串和空数组。'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': f'请把这个演员名字规范化为可用于检索的准确日文名字：{normalized_keyword}',
                    },
                ],
                'temperature': 0.1,
            },
            proxies=build_requests_proxies(),
            timeout=60,
        )
        try:
            response.raise_for_status()
            payload = response.json()
        finally:
            response.close()

        content = (((payload.get('choices') or [{}])[0].get('message') or {}).get('content') or '').strip()
        parsed = _extract_json_object(content)
        if not isinstance(parsed, dict):
            return []
        return _unique_nonempty_strings([
            parsed.get('exact_name'),
            *((parsed.get('candidates') or []) if isinstance(parsed.get('candidates'), list) else []),
        ])[:3]
    except Exception:
        logger.exception(f'演员名 AI 解析失败 | keyword={normalized_keyword}')
        return []



def search_casts(param: CastSearchParam, db: Session):
    query = db.query(Cast, CastSubscribe).outerjoin(CastSubscribe, CastSubscribe.cast_id == Cast.id)

    if param.keyword:
        keyword = (param.keyword or '').strip()
        like_keyword = f'%{keyword}%'

        movie_cast_subquery = (
            select(Cast.id)
            .select_from(Cast)
            .join(Movie, array_member(Movie.casts, Cast.id))
            .filter(Movie.number.ilike(like_keyword))
        )

        query = query.filter(
            or_(
                Cast.name.ilike(like_keyword),
                Cast.cn_name.ilike(like_keyword),
                array_any_ilike(Cast.former_name, like_keyword),
                Cast.id.in_(movie_cast_subquery),
            )
        )
    query = query.distinct()
    total = query.count()
    offset = (param.page - 1) * param.page_size
    rows = query.order_by(Cast.id.desc()).offset(offset).limit(param.page_size).all()
    items = _build_cast_search_items(rows)

    return success({
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': items,
        'hasMore': offset + len(rows) < total,
    })



def network_search_casts(param: CastSearchParam, db: Session):
    keyword = (param.keyword or '').strip()
    if not keyword:
        raise ValueError('Keyword is required')

    used_keyword = keyword
    attempted_keywords = [keyword]
    source = None
    saved_count = 0
    local_cast = None

    talent = av_base.get_talent(keyword)
    if talent:
        source = 'avbase'
    else:
        resolved_candidates = [
            candidate
            for candidate in _resolve_cast_name_candidates(keyword, db)
            if candidate.casefold() != keyword.casefold()
        ]
        attempted_keywords.extend(resolved_candidates)

        for candidate in resolved_candidates:
            local_cast = _find_local_cast(db, [candidate])
            if local_cast is not None:
                used_keyword = candidate
                source = 'local'
                break

        if local_cast is None:
            for candidate in resolved_candidates:
                talent = av_base.get_talent(candidate)
                if not talent:
                    continue
                used_keyword = candidate
                source = 'avbase'
                break

    cast = local_cast or _upsert_cast_from_network(db, talent)
    if cast is not None and source == 'avbase':
        saved_count = 1

    rows = _load_cast_rows(db, cast.id) if cast is not None else []
    items = _build_cast_search_items(rows)
    total = len(items)
    offset = (param.page - 1) * param.page_size
    paged_items = items[offset: offset + param.page_size]

    return success({
        'keyword': keyword,
        'usedKeyword': used_keyword,
        'attemptedKeywords': _unique_nonempty_strings(attempted_keywords),
        'found': total > 0,
        'savedCount': saved_count,
        'source': source if total > 0 else None,
        'page': param.page,
        'pageSize': param.page_size,
        'total': total,
        'items': paged_items,
        'hasMore': offset + len(paged_items) < total,
    })
