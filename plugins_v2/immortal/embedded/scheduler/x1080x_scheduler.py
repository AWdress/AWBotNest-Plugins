from ..modules.crawler.x1080x import x1080x
from ..scheduler.crawler_scheduler import sync_article_common, destroy_session, create_session
from ..utils import logger
from ..utils.wrapper import task_monitor



@task_monitor
def sync_x1080_by_max_page(max_page, section_id_list=None, start_page=None):
    logger.info(f'开始执行 X1080X 抓取任务 | max_page={max_page}, section_id_list={section_id_list}, start_page={start_page}')
    result = sync_x1080(max_page=max_page, section_id_list=section_id_list, start_page=start_page)
    logger.info(f'X1080X 抓取任务完成 | section_count={len(result)}')
    return result


section_map = {
    '5212': "国产品牌",
    '5206': "有码HD",
    '5207': "无码HD",
    '5208': "FC2HD",
    '5216': "MGSHD",
    '5479': "中文字幕",
    '5213': "探花精选",
    '5217': "主播精选"
}

x1080x_section_list = [{"label": v, "value": k} for k, v in section_map.items()]


def sync_x1080(max_page=None, section_id_list=None, start_page=None):
    result = []
    logger.info(f'初始化 X1080X 抓取会话 | max_page={max_page}, section_count={len(section_id_list or section_map)}')
    create_session("x1080x_session")
    try:
        for section_id in (section_id_list or section_map):
            section_id = str(section_id)
            section = section_map[section_id]
            success_count, page, fail_list = sync_article_common('x1080x', section_id, section_map,
                                                                 x1080x.get_tid_from_list, x1080x.get_detail_by_tid, start_page or 1,
                                                                 max_page or 100, False if max_page else True)
            logger.info(f'X1080X 板块抓取完成 | section_id={section_id}, section={section}, success_count={success_count}, page={page - 1}, fail_count={len(fail_list)}')
            result.append(
                {
                    "section": section,
                    "success_count": success_count,
                    "page": page - 1,
                    "fail_list": fail_list,
                }
            )
    finally:
        destroy_session("x1080x_session")
    return result
