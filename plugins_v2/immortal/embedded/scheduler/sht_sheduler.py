from ..scheduler.crawler_scheduler import sync_article_common, destroy_session, create_session
from ..modules.crawler.sht import sht
from ..utils import logger
from ..utils.wrapper import task_monitor


@task_monitor
def sync_sht_by_max_page(max_page=None, section_id_list=None, start_page=None):
    logger.info(f'开始执行色花堂爬虫任务 | max_page={max_page}, section_id_list={section_id_list}, start_page={start_page}')
    result = sync_sht(max_page=max_page, section_id_list=section_id_list, start_page=start_page)
    logger.info(f'色花堂爬虫任务完成 | section_count={len(result)}')
    return result


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
    "95": "综合讨论区",
    "142":"转贴交流区"
}

sht_section_list = [{"label": v, "value": k} for k, v in section_map.items()]


def sync_sht(max_page=None, section_id_list=None, start_page=None):
    sht.mode = 'direct'
    result = []
    logger.info(f'初始化色花堂抓取会话 | max_page={max_page}, section_count={len(section_id_list or section_map)}')
    create_session("sht_session")
    try:
        for section_id in (section_id_list or section_map):
            section_id = str(section_id)
            section = section_map[section_id]
            success_count, page, fail_list = sync_article_common('sehuatang', section_id, section_map, sht.crawler_tid_list,
                                                                 sht.crawler_detail, start_page or 1, max_page or 100,
                                                                 False if max_page else True)
            logger.info(f'色花堂板块抓取完成 | section_id={section_id}, section={section}, success_count={success_count}, page={page - 1}, fail_count={len(fail_list)}')
            result.append(
                {
                    "section": section,
                    "success_count": success_count,
                    "page": page - 1,
                    "fail_list": fail_list,
                }
            )
    finally:
        destroy_session("sht_session")
    return result
