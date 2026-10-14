import datetime
import io
import json
import hashlib
import zipfile
import csv
from typing import Dict, List
from sqlalchemy import func, exists, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from ...api.services.subscribe_service import build_article_push_fields
from ...core.database import session_scope
from ...core.runtime import get_runtime
from ...enums import DownloadClientEnum, SubscribeStatus
from ...models import DownloadLog, Rule, Filter, Movie, Subscribe
from ...models.article import Article
from ...utils.db_lock import acquire_subscribe_write_lock
from ...modules.downloadclient.manager import downloadManager
from ...modules.mediaserver import mediaServerManager
from ...modules.notification.manager import pushManager
from ...schemas.article import ArticleQuery
from ...api.services import rule_service
from ...api.services.article_match_service import has_chinese, has_uc, matches_article_filter, has_uhd
from ...schemas.response import success, error
import pandas as pd
import re

from ...utils.movie_number import extract_movie_numbers, extract_primary_movie_number
from ...utils import logger

ARRAY_FIELDS = {"magnet", "edk", "preview_images"}
ARTICLE_SUBSCRIBE_COMPLETED_MESSAGE = '已命中资源并创建下载任务'


def _extract_article_movie_numbers(title: str | None) -> list[str]:
    return extract_movie_numbers((title or '').strip())


def _extract_article_match_number(title: str | None) -> str | None:
    return extract_primary_movie_number(title)


def _hydrate_article_match_number(article: Article) -> None:
    article.match_number = _extract_article_match_number(article.title)


def _hydrate_article_match_number_row(row: dict) -> dict:
    row['match_number'] = _extract_article_match_number(row.get('title'))
    return row


def _update_subscribe_state_after_article_download(article: Article) -> None:
    article_numbers = _extract_article_movie_numbers(article.title)
    if not article_numbers:
        return

    with session_scope() as db:
        acquire_subscribe_write_lock(db)
        rows = (
            db.query(Subscribe, Movie, Filter)
            .join(Movie, Movie.id == Subscribe.movie_id)
            .outerjoin(Filter, Filter.id == Subscribe.filter_id)
            .filter(
                Subscribe.status == SubscribeStatus.ACTIVE.value,
                Movie.number.in_(article_numbers),
            )
            .order_by(Subscribe.id.asc())
            .all()
        )

        completed_push_payloads: list[tuple[int, int]] = []
        for subscribe, movie, filter_obj in rows:
            if matches_article_filter(article, filter_obj):
                subscribe.status = SubscribeStatus.COMPLETED.value
                subscribe.pre_download_enabled = False
                completed_push_payloads.append((subscribe.id, movie.id))
                continue

            if subscribe.pre_download_enabled:
                subscribe.pre_download_enabled = False

    if not rows or not completed_push_payloads:
        return

    from ...api.services.subscribe_service import _push_subscribe_completed

    with session_scope() as db:
        article_in_db = db.get(Article, article.id)
        for subscribe_id, movie_id in completed_push_payloads:
            subscribe = db.get(Subscribe, subscribe_id)
            movie = db.get(Movie, movie_id)
            if not subscribe or not movie:
                continue
            _push_subscribe_completed(
                subscribe,
                movie,
                article=article_in_db,
                completion_source='download',
                db=db,
            )


def _build_article_library_lookup(rows) -> tuple[dict[int, list[str]], dict[str, bool]]:
    article_numbers_map: dict[int, list[str]] = {}
    movie_numbers: set[str] = set()

    for article, _ in rows:
        if not article:
            continue
        numbers = _extract_article_movie_numbers(article.title)
        article_numbers_map[article.id] = numbers
        movie_numbers.update(numbers)

    in_library_map: dict[str, bool] = {}
    if not movie_numbers:
        return article_numbers_map, in_library_map

    for number in movie_numbers:
        get_runtime().check_cancelled()
        in_library_map[number] = mediaServerManager.any_movie_exists_by_number(number)

    return article_numbers_map, in_library_map


def _parse_pg_text_array(value: str) -> list[str | None]:
    text = value.strip()
    if text == '{}':
        return []
    if not (text.startswith('{') and text.endswith('}')):
        raise ValueError('invalid postgres array text')

    items: list[str | None] = []
    token: list[str] = []
    in_quotes = False
    escaped = False

    for ch in text[1:-1]:
        if escaped:
            token.append(ch)
            escaped = False
            continue

        if in_quotes:
            if ch == '\\':
                escaped = True
            elif ch == '"':
                in_quotes = False
            else:
                token.append(ch)
            continue

        if ch == ',':
            raw = ''.join(token).strip()
            items.append(None if raw == 'NULL' else raw)
            token = []
            continue

        if ch == '"':
            in_quotes = True
            continue

        token.append(ch)

    if escaped or in_quotes:
        raise ValueError('unterminated postgres array text')

    raw = ''.join(token).strip()
    items.append(None if raw == 'NULL' else raw)
    return items


def _normalize_array_field(value):
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith('[') and text.endswith(']'):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
        if text.startswith('{') and text.endswith('}'):
            return _parse_pg_text_array(text)
        return [text]
    return value


def _normalize_import_row(row: dict) -> dict:
    allowed = {column.name for column in Article.__table__.columns} - {'id'}
    normalized = {key: value for key, value in row.items() if key in allowed}
    if normalized.get('tid') is not None:
        normalized['tid'] = int(normalized['tid'])
    if normalized.get('size') is not None:
        normalized['size'] = int(normalized['size'])
    for name, kind in [('publish_date', datetime.date), ('create_time', datetime.datetime)]:
        value = normalized.get(name)
        if isinstance(value, str) and value.strip():
            normalized[name] = kind.fromisoformat(value.strip())
    for field in ARRAY_FIELDS:
        if field in normalized:
            normalized[field] = _normalize_array_field(normalized[field])
    return _hydrate_article_match_number_row(normalized)


def get_article_list(db: Session, query: ArticleQuery) -> Dict:
    in_stock_expr = exists().where(
        DownloadLog.article_id == Article.id
    )
    q = db.query(Article, in_stock_expr.label("in_stock"))
    if query.website:
        q = q.filter(Article.website == query.website)
    if query.keyword:
        q = q.filter(Article.title.ilike(f"%{query.keyword}%"))
    if query.section:
        q = q.filter(Article.section == query.section)
    if query.category:
        q = q.filter(Article.category == query.category)
    if query.date_range and query.date_range.get('from') and query.date_range.get('to'):
        q = q.filter(Article.publish_date.between(query.date_range.get('from'), query.date_range.get('to')))
    total = q.count()
    page = query.page
    offset = (page - 1) * query.page_size
    rows = (
        q.order_by(Article.publish_date.desc(), Article.create_time.desc(), Article.id.desc())
        .offset(offset)
        .limit(query.page_size)
        .all()
    )
    article_numbers_map, in_library_map = _build_article_library_lookup(rows)
    items = []
    for article, in_stock in rows:
        setattr(article, "in_stock", in_stock)
        article_numbers = article_numbers_map.get(article.id, [])
        setattr(article, "in_library", any(in_library_map.get(number, False) for number in article_numbers))
        setattr(article, 'img_list', article.preview_images)
        items.append(article)
    has_more = len(items) == query.page_size
    return success({
        "page": page,
        "pageSize": query.page_size,
        "total": total,
        "items": items,
        "hasMore": has_more
    })


def get_torrents(keyword, db: Session) -> Dict:
    articles = db.query(Article).filter(Article.title.ilike(f"%{keyword}%")).all()
    torrents = []
    for article in articles:
        magnet_list = article.magnet or []
        edk_list = article.edk or []
        download_url = magnet_list[0] if magnet_list else (edk_list[0] if edk_list else '')

        torrent = {
            'id': article.tid,
            'site': article.website,
            'size_mb': article.size or 0,
            'seeders': 66,
            'title': article.title,
            'download_url': download_url,
            'free': True,
            'chinese': has_chinese(f"{article.title}{article.section}"),
            'uc': has_uc(f"{article.title}{article.section}"),
            'uhd': has_uhd(f"{article.title}{article.section}")
        }
        torrents.append(torrent)
    return success(torrents)


def get_category(db: Session):
    item_count = func.count(Article.id).label("item_count")
    result = (
        db.query(Article.website, Article.section, Article.category, item_count)
        .filter(Article.website.isnot(None), Article.website != '', Article.section.isnot(None), Article.section != '')
        .group_by(Article.website, Article.section, Article.category)
        .order_by(item_count.desc())
        .all()
    )

    websites = {}
    for website, section, category, count in result:
        website_key = website or ''
        if website_key not in websites:
            websites[website_key] = {
                "name": website_key,
                "count": 0,
                "sections": {},
            }

        website_item = websites[website_key]
        section_map = website_item["sections"]
        if section not in section_map:
            section_map[section] = {
                "name": section,
                "count": 0,
                "categories": [],
            }

        section_item = section_map[section]
        if category:
            section_item["categories"].append({
                "name": category,
                "count": count,
            })

        section_item["count"] += count
        website_item["count"] += count

    items = []
    for website_name, website_item in sorted(websites.items(), key=lambda item: (-item[1]["count"], item[0])):
        sections = []
        for section_name, section_item in sorted(
                website_item["sections"].items(), key=lambda item: (-item[1]["count"], item[0])
        ):
            section_item["categories"] = sorted(
                section_item["categories"], key=lambda item: (-item["count"], item["name"])
            )
            sections.append(section_item)
        items.append({
            "name": website_name,
            "count": website_item["count"],
            "sections": sections,
        })

    return success(items)


def calc_score(rule, website, section, category, title):
    score = 0

    if rule_service.rule_matches_option(rule.website, website):
        website_values = rule_service.normalize_rule_values(rule.website)
        score += 10 if rule_service.ALL_VALUE not in website_values else 1
    else:
        return 0

    if rule_service.rule_matches_option(rule.section, section):
        section_values = rule_service.normalize_rule_values(rule.section)
        score += 10 if rule_service.ALL_VALUE not in section_values else 1
    else:
        return 0

    if rule_service.rule_matches_option(rule.category, category):
        category_values = rule_service.normalize_rule_values(rule.category)
        score += 5 if rule_service.ALL_VALUE not in category_values else 1
    else:
        return 0

    rule_regex = rule.regex

    if rule_regex:
        try:
            if re.search(rule_regex, title):
                score += 20
            else:
                return 0
        except re.error as e:
            # 脏数据兜底：跳过该 rule，避免一条坏 regex 把整批订阅搞挂
            from ...utils import logger
            logger.warning(
                f"Rule 正则无效，已跳过该规则 | rule_id={getattr(rule, 'id', '?')}, regex={rule_regex!r}, err={e}"
            )
            return 0
    else:
        score += 1
    return score


def match_best_rules(rules, website, section, category, title):
    best_score = 0
    best_rules = []

    for rule in rules:
        score = calc_score(rule, website, section, category, title)
        if score == 0:
            continue

        if score > best_score:
            best_score = score
            best_rules = [rule]
        elif score == best_score:
            best_rules.append(rule)

    return best_rules


def convert_save_path(article: Article, original_save_path):
    current_date = datetime.date.today()
    save_path = original_save_path.format(section=article.section,
                                          category=article.category or '未分类',
                                          publish_date=article.publish_date,
                                          current_date=current_date
                                          )
    return save_path


def download_magnet(article: Article, downloader, save_path):
    runtime = get_runtime()
    runtime.require_download()
    save_path = convert_save_path(article, save_path)
    success_count = 0
    errors = []
    if article.magnet:
        for magnet in article.magnet:
            runtime.check_cancelled()
            is_success, err = downloadManager.download(f'Downloader.{downloader}', magnet, save_path)
            if is_success:
                success_count += 1
            else:
                errors.append(err or '磁链提交失败')
    if article.edk and f'Downloader.{downloader}' in [DownloadClientEnum.THUNDER.value,
                                                      DownloadClientEnum.CLOUDDRIVE.value]:
        for edk in article.edk:
            runtime.check_cancelled()
            is_success, err = downloadManager.download(f'Downloader.{downloader}', edk, save_path)
            if is_success:
                success_count += 1
            else:
                errors.append(err or 'ed2k 提交失败')

    # Record article-level completion only when every supported resource has
    # been accepted. Per-link receipts prevent resubmission after partial success.
    if article.edk and f'Downloader.{downloader}' not in [DownloadClientEnum.THUNDER.value,
                                                         DownloadClientEnum.CLOUDDRIVE.value]:
        errors.append('此下载器不支持文章中的 ed2k 资源')
    if success_count > 0 and not errors:
        with session_scope() as db:
            existing = db.query(DownloadLog).filter_by(article_id=article.id, save_path=save_path,
                                                       downloader=downloader).first()
            if existing is None:
                db.add(DownloadLog(article_id=article.id, save_path=save_path, downloader=downloader))
        return True, None
    error_msg = errors[0] if errors else '下载失败'
    return False, error_msg


def convert_message_data(article: Article, downloader: str, save_path: str):
    payload = {
        'download_client': downloader,
        'download_save_path': save_path,
        'image': article.preview_images[0] if article.preview_images else None

    }
    payload.update(build_article_push_fields(article))
    return payload


def _normalize_article_id(article_id) -> int:
    try:
        return int(article_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'Invalid article id: {article_id}') from exc


def download_article(article_id: int, update_subscribe_state: bool = True):
    runtime = get_runtime()
    runtime.require_download()
    article_id = _normalize_article_id(article_id)
    if not runtime.in_job:
        job = runtime.submit('文章下载', download_article, article_id, update_subscribe_state,
                             task_key=f'article-download:{article_id}')
        return success(job, message='文章下载已加入任务队列')
    with session_scope() as db:
        article = db.get(Article, article_id)
        rules = db.query(Rule).all()

    if not article:
        return error('文章不存在')

    if not rules:
        return error('未配置下载规则')

    success_count = 0
    website = article.website
    section = article.section
    category = article.category
    best_rules = match_best_rules(rules, website, section, category, article.title)
    if not best_rules:
        return error("未匹配到合适的下载路径")

    last_error = None
    for rule in best_rules:
        is_success, err = download_magnet(article, rule.downloader, rule.save_path)
        if is_success:
            pushManager.send_event('download', convert_message_data(article, rule.downloader, rule.save_path))
            success_count += 1
        else:
            last_error = err

    if success_count > 0:
        if update_subscribe_state:
            _update_subscribe_state_after_article_download(article)
        return success(message="成功创建下载任务")
    return error(last_error or "创建下载任务失败")


def manul_download(article_id, downloader, save_path, update_subscribe_state: bool = True):
    runtime = get_runtime()
    runtime.require_download()
    article_id = _normalize_article_id(article_id)
    if not runtime.in_job:
        key = hashlib.sha256(json.dumps([article_id, downloader, save_path], ensure_ascii=False).encode()).hexdigest()
        job = runtime.submit('手动文章下载', manul_download, article_id, downloader, save_path,
                             update_subscribe_state, task_key=f'article-manual:{key}')
        return success(job, message='文章下载已加入任务队列')
    with session_scope() as db:
        article = db.get(Article, article_id)

    if not article:
        return error('文章不存在')

    is_success, err = download_magnet(article, downloader, save_path)
    if is_success:
        pushManager.send_event('download', convert_message_data(article, downloader, save_path))
        if update_subscribe_state:
            _update_subscribe_state_after_article_download(article)
        return success(message="成功创建下载任务")
    return error(err or "创建下载任务失败")


def _batch_download_worker(article_id_list):
    results = []
    success_count = 0
    fail_count = 0

    for raw_article_id in article_id_list:
        get_runtime().check_cancelled()
        try:
            article_id = _normalize_article_id(raw_article_id)
            resp = download_article(article_id)
            item_success = isinstance(resp, dict) and resp.get('code') == 0
            if item_success:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                'article_id': article_id,
                'success': item_success,
                'message': resp.get('message') if isinstance(resp, dict) else None,
            })
        except Exception as exc:
            fail_count += 1
            logger.exception(f'批量下载失败 | article_id={raw_article_id}')
            results.append({
                'article_id': raw_article_id,
                'success': False,
                'message': str(exc),
            })

    logger.info(
        f'批量下载处理完成 | total={len(results)}, success_count={success_count}, fail_count={fail_count}'
    )
    return {
        'total': len(results),
        'success_count': success_count,
        'fail_count': fail_count,
        'items': results,
    }


def batch_download(article_id_list):
    runtime = get_runtime()
    runtime.require_download()
    article_ids = [str(article_id).strip() for article_id in (article_id_list or []) if str(article_id).strip()]
    if not article_ids:
        return error('article_id_list is empty')

    if len(article_ids) > 200:
        return error('每次最多提交 200 篇文章')
    key = hashlib.sha256(json.dumps(sorted(set(article_ids))).encode()).hexdigest()
    job = runtime.submit('批量文章下载', _batch_download_worker, article_ids,
                         task_key=f'article-batch:{key}')
    return success({
        'total': len(article_ids),
        'job': job,
    }, message='批量下载任务已提交，正在后台处理')


def _batch_manul_download_worker(article_id_list, downloader, save_path):
    results = []
    success_count = 0
    fail_count = 0

    for raw_article_id in article_id_list:
        get_runtime().check_cancelled()
        try:
            article_id = _normalize_article_id(raw_article_id)
            resp = manul_download(article_id, downloader, save_path)
            item_success = isinstance(resp, dict) and resp.get('code') == 0
            if item_success:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                'article_id': article_id,
                'success': item_success,
                'message': resp.get('message') if isinstance(resp, dict) else None,
            })
        except Exception as exc:
            fail_count += 1
            logger.exception(f'批量手动下载失败 | article_id={raw_article_id}')
            results.append({
                'article_id': raw_article_id,
                'success': False,
                'message': str(exc),
            })

    logger.info(
        f'批量手动下载处理完成 | total={len(results)}, success_count={success_count}, fail_count={fail_count}, downloader={downloader}'
    )
    return {
        'total': len(results),
        'success_count': success_count,
        'fail_count': fail_count,
        'items': results,
    }


def batch_manul_download(article_id_list, downloader, save_path):
    runtime = get_runtime()
    runtime.require_download()
    article_ids = [str(article_id).strip() for article_id in (article_id_list or []) if str(article_id).strip()]
    if not article_ids:
        return error('article_id_list is empty')

    if len(article_ids) > 200:
        return error('每次最多提交 200 篇文章')
    key = hashlib.sha256(json.dumps([sorted(set(article_ids)), downloader, save_path], ensure_ascii=False).encode()).hexdigest()
    job = runtime.submit('批量手动下载', _batch_manul_download_worker, article_ids, downloader, save_path,
                         task_key=f'article-batch-manual:{key}')
    return success({
        'total': len(article_ids),
        'downloader': downloader,
        'save_path': save_path,
        'job': job,
    }, message='批量手动下载任务已提交，正在后台处理')


CHUNK_SIZE = 5000


async def import_excel(file, db: Session):
    contents = await file.read()
    if len(contents) > 8 * 1024 * 1024:
        return error('导入文件不能超过 8 MiB')
    filename = file.filename.lower()
    try:
        if filename.endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                entries = archive.infolist()
                if len(entries) > 3000 or sum(item.file_size for item in entries) > 64 * 1024 * 1024:
                    return error('表格解压后超过安全限制，请拆分后导入')
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl", nrows=50001)
        elif filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(contents), engine="xlrd", nrows=50001)
        elif filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents), nrows=50001)
        else:
            logger.info("不支持的文件格式")
            return error("不支持的文件格式")
    except Exception as e:
        logger.exception("")
        return error(f"解析文件失败: {e}")

    df = df.astype(object).where(pd.notnull(df), None)

    cols = ["publish_date", "size", "category"]
    for col in cols:
        if col in df.columns:
            df[col] = df[col].where(pd.notna(df[col]), None)

    rows = df.to_dict(orient="records")
    if len(rows) > 50000:
        return error('每次最多导入 50000 行')
    del df

    total_inserted = 0
    total_skipped = 0

    for i in range(0, len(rows), CHUNK_SIZE):
        get_runtime().check_cancelled()
        chunk = rows[i: i + CHUNK_SIZE]

        valid_chunk = [
            row for row in chunk
            if row.get("tid") is not None and row.get("website") is not None
        ]
        total_skipped += len(chunk) - len(valid_chunk)

        if not valid_chunk:
            continue

        pairs = list({(int(row["tid"]), str(row["website"])) for row in valid_chunk})

        try:
            tid_list = list({p[0] for p in pairs})
            result = db.execute(
                select(Article.tid, Article.website).where(
                    Article.tid.in_(tid_list)
                )
            )
            existing = {(row[0], row[1]) for row in result}
        except Exception as e:
            db.rollback()
            logger.exception("")
            return error(f"查询失败: {e}")

        new_rows = []
        for row in valid_chunk:
            identity = (int(row['tid']), str(row['website']))
            if identity not in existing:
                existing.add(identity)
                new_rows.append(row)
        total_skipped += len(valid_chunk) - len(new_rows)
        logger.info(f"已完成同步 {i + len(chunk)}/{len(rows)}")
        if not new_rows:
            continue

        objects = [
            Article(**{key: value for key, value in _normalize_import_row(row).items() if key != "id"})
            for row in new_rows
        ]
        db.bulk_save_objects(objects)
        total_inserted += len(objects)

    logger.info(f"插入: {total_inserted} 条，跳过: {total_skipped} 条")
    return success({
        "inserted": total_inserted,
        "skipped": total_skipped,
    })


def row_to_safe_list(row):
    safe_row = []
    for value in row:
        if isinstance(value, (list, dict)):
            # ARRAY 或 JSON 序列化成 JSON 字符串
            safe_row.append(json.dumps(value, ensure_ascii=False))
        else:
            safe_row.append(value)
    return safe_row


def generate_csv():
    columns = [column.name for column in Article.__table__.columns]
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(columns)
    yield buffer.getvalue().encode('utf-8-sig')
    buffer.seek(0)
    buffer.truncate(0)
    with session_scope() as db:
        for article in db.query(Article).order_by(Article.id).yield_per(500):
            get_runtime().check_cancelled()
            writer.writerow(row_to_safe_list([getattr(article, name) for name in columns]))
            if buffer.tell() >= 8192:
                yield buffer.getvalue().encode('utf-8')
                buffer.seek(0)
                buffer.truncate(0)
    if buffer.tell():
        yield buffer.getvalue().encode('utf-8')


def export_article():
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=article.csv"
        }
    )
