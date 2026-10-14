import random
import time
from datetime import date, datetime
from ..core.runtime import check_cancelled, sleep

from sqlalchemy import func, select
from ..core.database import insert

from ..core.config import config_manager
from ..core.database import session_scope
from ..models import Article
from ..utils.movie_number import extract_primary_movie_number
from ..utils import logger, safe_post


def _extract_article_match_number(title: str | None) -> str | None:
    return extract_primary_movie_number(title)


def sync_article_common(
        site_name: str,
        section_id: str,
        section_map: dict,
        get_tid_list_func,
        get_detail_func,
        start_page=1,
        max_page=100,
        use_stop_threshold=True
):
    section_id = str(section_id)
    max_page = int(max_page)
    start_page = int(start_page)
    section = section_map[section_id]

    fail_id_list = []
    page = start_page
    success_count = 0
    stop_tid = 0
    if use_stop_threshold:
        with session_scope() as session:
            stop_tid = (
                    session.query(func.max(Article.tid))
                    .filter(Article.section == section)
                    .filter(Article.website == site_name)
                    .scalar() or 0
            )
        logger.info(f"[{site_name}][{section}] 数据库最大TID: {stop_tid}")

    while page <= max_page:
        sleep(1)
        logger.info(f"[{site_name}][{section}] 抓取第 {page} 页")

        tid_list = []
        articles = []

        # 页面级重试
        for retry in range(3):
            try:
                tid_list = get_tid_list_func(section_id, page)
                if tid_list:
                    logger.info(
                        f"[{site_name}][{section}] 抓取到TID列表: {tid_list}"
                    )
                    break
            except Exception:
                logger.exception(
                    f"[{site_name}][{section}] 第{page}页抓取异常 | retry={retry + 1}"
                )
            sleep(5)

        if not tid_list:
            raise RuntimeError(
                f"[{site_name}][{section}] 第{page}页连续3次获取失败，已保存 {success_count} 条"
            )

        min_tid = min(tid_list)
        logger.info(f"[{site_name}][{section}] 当前页最小TID: {min_tid}")

        # 查询已存在
        with session_scope() as session:
            existing_article_tids = set(
                session.execute(
                    select(Article.tid)
                    .filter(Article.tid.in_(tid_list))
                    .filter(Article.website == site_name)
                ).scalars().all()
            )
        un_existing_ids = list(set(tid_list) - existing_article_tids)
        logger.info(f"[{site_name}][{section}] 尚未抓取的TID列表: {un_existing_ids}")

        for tid in tid_list:
            check_cancelled()
            if tid in existing_article_tids:
                continue

            try:
                data = get_detail_func(tid)
                if not data:
                    fail_id_list.append(tid)
                    continue

                data.update({
                    "tid": tid,
                    "section": section,
                    "website": site_name,
                    "match_number": _extract_article_match_number(data.get('title')),
                })

                articles.append(Article(**data))
                sleep(1)

            except Exception:
                logger.exception(
                    f"[{site_name}][{section}] TID:{tid} 抓取异常 | page={page}"
                )
                fail_id_list.append(tid)
        if articles:
            try:
                success_count += save_articles(articles)
            except Exception as exc:
                raise RuntimeError(
                    f"[{site_name}][{section}] 第{page}页入库失败，已保存 {success_count} 条"
                ) from exc

        # 终止条件
        if use_stop_threshold and min_tid <= stop_tid:
            logger.info(
                f"[{site_name}][{section}] 到达历史最大TID，任务结束"
            )
            break

        page += 1

    retry_saved_count, retry_fail_id_list = retry_fail(
        site_name, section_id, section_map, get_detail_func, fail_id_list,
        return_saved_count=True,
    )
    success_count += retry_saved_count
    return success_count, page, retry_fail_id_list


def retry_fail(
        site_name: str,
        section_id: str,
        section_map: dict,
        get_detail_func,
        fail_id_list: list,
        return_saved_count=False,
):
    fail_id_list = list(set(fail_id_list))
    if not fail_id_list:
        return (0, []) if return_saved_count else []

    section_id = str(section_id)
    section = section_map[section_id]

    logger.info(
        f"[{site_name}][{section}] 开始补抓失败ID，共 {len(fail_id_list)} 条"
    )

    articles = []
    remain_fail_ids = []

    for tid in fail_id_list:
        check_cancelled()
        try:
            data = get_detail_func(tid)
            if not data:
                remain_fail_ids.append(tid)
                continue

            data.update({
                "tid": tid,
                "section": section,
                "website": site_name,
                "match_number": _extract_article_match_number(data.get('title')),
            })

            articles.append(Article(**data))
            sleep(random.uniform(2, 3))

        except Exception:
            logger.exception(
                f"[{site_name}][{section}] TID {tid} 二次抓取仍失败"
            )
            remain_fail_ids.append(tid)

    # 批量入库
    saved_count = 0
    if articles:
        try:
            saved_count = save_articles(articles)
        except Exception as exc:
            raise RuntimeError(f"[{site_name}][{section}] 补抓文章入库失败") from exc
    logger.info(
        f"[{site_name}][{section}] 最终失败列表: {remain_fail_ids}"
    )

    return (saved_count, remain_fail_ids) if return_saved_count else remain_fail_ids


def _publish_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) or value is None:
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip()) if value.strip() else None
    raise ValueError('文章发布日期格式无效')


def save_articles(articles):
    check_cancelled()
    if not articles:
        return 0
    with session_scope() as session:
        stmt = insert(Article).values([
            {"tid": a.tid,
             "title": a.title,
             "website": a.website,
             "match_number": a.match_number,
             "publish_date": _publish_date(a.publish_date),
             "magnet":a.magnet,
             "edk":a.edk,
             "preview_images":a.preview_images,
             "detail_url":a.detail_url,
             "size":a.size,
             "section":a.section,
             "category":a.category
             }
            for a in articles
        ])

        stmt = stmt.on_conflict_do_nothing(
            index_elements=["tid", "website"]
        )

        result = session.execute(stmt)
        saved_count = result.rowcount
        if saved_count < 0:
            raise RuntimeError('无法确认文章保存数量')
    return saved_count


def create_session(session):
    if config_manager.get().FLARE_SOLVERR_URL:
        flare_url = config_manager.get().FLARE_SOLVERR_URL.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"
        payload = {
            "cmd": "sessions.create",
            "session": session,
            "proxy": {"url": config_manager.get().PROXY}
        }
        safe_post(flare_url,
                  headers={"Content-Type": "application/json"},
                  json=payload)


def destroy_session(session):
    if config_manager.get().FLARE_SOLVERR_URL:
        flare_url = config_manager.get().FLARE_SOLVERR_URL.rstrip('/')
        flare_url = flare_url if flare_url.endswith("/v1") else f"{flare_url}/v1"
        payload = {
            "cmd": "sessions.destroy",
            "session": session
        }
        safe_post(flare_url,
                  headers={"Content-Type": "application/json"},
                  json=payload)


section_map = {
    '2': "国产原创",
    '36': "亚洲无码原创",
    '38': "欧美无码",
    '37': "亚洲有码原创",
    '103': "高清中文字幕",
    '104': "素人有码系列",
    '151': "4K原版",
    '152': "韩国主播",
    "160": "VR视频区",
    "39": "动漫原创",
    "107": "三级写真",
    "95": "综合讨论区"
}
