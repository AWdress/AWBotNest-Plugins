from datetime import date, timedelta
from typing import Any, List

from sqlalchemy import exists, or_

from ..api.services import article_service
from ..core.database import session_scope
from ..models import Article, DownloadLog, Rule
from ..modules.downloadclient.manager import downloadManager
from ..utils.log import logger
from ..utils.wrapper import task_monitor


def to_number_list(
        value: Any,
        *,
        allow_float: bool = False,
        empty_ok: bool = False
) -> List[int | float]:
    def cast(v: str):
        return float(v) if allow_float else int(v)

    if isinstance(value, list):
        try:
            result = [cast(v) for v in value]
        except Exception:
            raise ValueError('列表中包含非数字元素')

        if not result and not empty_ok:
            raise ValueError('不允许空列表')

        return result

    if isinstance(value, str):
        value = value.strip()
        if not value:
            if empty_ok:
                return []
            raise ValueError('空字符串无法转换为数字列表')

        for sep in [',', '|', ' ']:
            value = value.replace(sep, ',')
        parts = [p for p in value.split(',') if p]

        try:
            result = [cast(p) for p in parts]
        except Exception:
            raise ValueError('字符串中包含非数字内容')

        if not result and not empty_ok:
            raise ValueError('不允许空列表')
        return result

    raise ValueError(f'不支持的类型: {type(value).__name__}')


@task_monitor
def download_by_route(rule_id_list, offset_days):
    offset_days = int(offset_days)
    logger.info(f'开始执行规则入库任务 | rule_id_list={rule_id_list}, offset_days={offset_days}')

    try:
        rule_id_list = to_number_list(rule_id_list)
    except ValueError as e:
        logger.exception(f'规则入库任务执行失败: {e}')
        return None

    results = []
    with session_scope() as session:
        rules = session.query(Rule).filter(Rule.id.in_(rule_id_list)).all()

    if not rules:
        logger.warning(f'规则入库任务未找到有效规则 | rule_id_list={rule_id_list}')
        return results

    logger.info(f'规则入库任务命中规则数 | count={len(rules)}')
    end_date = date.today()
    start_date = end_date - timedelta(days=offset_days - 1)

    for rule in rules:
        success_count = 0
        fail_list = []
        with session_scope() as session:
            articles = session.query(Article).filter(
                Article.publish_date.between(start_date, end_date),
                ~exists().where(DownloadLog.article_id == Article.id)
            ).all()
            articles = [
                article
                for article in articles
                if article_service.calc_score(
                    rule,
                    article.website,
                    article.section,
                    article.category,
                    article.title or '',
                ) > 0
            ]

        logger.info(f'规则待处理文章数量 | rule_id={rule.id}, count={len(articles)}')
        for article in articles:
            is_success, _ = article_service.download_magnet(article, rule.downloader, rule.save_path)
            if is_success:
                success_count += 1
            else:
                fail_list.append(article.tid)

        logger.info(
            f'规则入库执行完成 | rule_id={rule.id}, success_count={success_count}, fail_count={len(fail_list)}'
        )
        results.append({
            'success_count': success_count,
            'fail_list': fail_list,
            'id': rule.id
        })

    logger.info(f'规则入库任务完成 | result_count={len(results)}')
    return results


@task_monitor
def analyze_article_size(offset_days):
    offset_days = int(offset_days)
    logger.info(f'开始执行磁链体积分析任务 | offset_days={offset_days}')

    end_date = date.today()
    start_date = end_date - timedelta(days=offset_days - 1)
    success_count = 0
    fail_count = 0

    with session_scope() as session:
        articles = session.query(Article).filter(
            Article.publish_date.between(start_date, end_date),
            or_(
                Article.size == 0,
                Article.size.is_(None)
            )
        ).order_by(Article.publish_date.desc()).all()

        logger.info(f'待分析文章数量 | count={len(articles)}')
        for article in articles:
            magnets = article.magnet
            if magnets:
                total_size = 0
                for magnet in magnets:
                    size = downloadManager.analyze_size(magnet)
                    if size:
                        total_size += size
                if total_size > 0:
                    article.size = total_size
                    session.commit()
                    success_count += 1
                else:
                    fail_count += 1

    logger.info(f'磁链体积分析任务完成 | success_count={success_count}, fail_count={fail_count}')
    return {
        'success_count': success_count,
        'fail_count': fail_count,
    }
