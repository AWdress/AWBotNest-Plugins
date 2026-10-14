"""Task catalog only; scheduling belongs to AWBotNest, not APScheduler here."""
from importlib import import_module
from ..core.runtime import get_runtime, require_download


def arg(key, label, kind='number', required=False, **extra):
    return {'key': key, 'label': label, 'type': kind, 'required': required, **extra}


MOVIE_RANK_NAME_OPTIONS = [{'label': '图书馆-' + label, 'value': 'library-' + value} for label, value in [('最想要', 'vl_mostwanted'), ('高评分', 'vl_bestrated')]] + [
    {'label': f'JavDB-{kind}{period_label}', 'value': f'javdb-{code}-{period}'}
    for kind, code in [('有码', '0'), ('无码', '1'), ('FC2', '3')]
    for period_label, period in [('日榜', 'daily'), ('周榜', 'weekly'), ('月榜', 'monthly')]]
SHARED_RANK_NAME_OPTIONS = MOVIE_RANK_NAME_OPTIONS + [{'label': '图书馆-演员榜', 'value': 'library-star_mostfav'}]


_TASKS = [
    ('sht_sheduler', 'sync_sht_by_max_page', '色花堂资源抓取', [arg('start_page', '起始页（默认 1）'), arg('max_page', '抓到第几页（默认 1，最多 20）'), arg('section_id_list', '板块', 'multi-select')]),
    ('x1080x_scheduler', 'sync_x1080_by_max_page', '1080X 资源抓取', [arg('start_page', '起始页（默认 1）'), arg('max_page', '抓到第几页（默认 1，最多 20）'), arg('section_id_list', '板块', 'multi-select')]),
    ('download_scheduler', 'download_by_route', '按规则提交下载', [arg('offset_days', '发布日期偏移天数', required=True), arg('rule_id_list', '规则', 'multi-select', True)]),
    ('article_scheduler', 'sync_article', '远程同步资源库', [arg('url', '分享地址', 'string', True), arg('token', '分享令牌', 'string', True)]),
    ('rank_scheduler', 'sync_shared_movie_rank', '远程同步榜单', [arg('url', '分享地址', 'string', True), arg('token', '分享令牌', 'string', True), arg('rank_name_list', '榜单', 'multi-select')]),
    ('rank_scheduler', 'sync_library_top_movie', 'JavLibrary 影片榜单', [arg('max_page', '最大页码（最多 20）', required=True), arg('rank_type_list', '榜单类型', 'multi-select', options=[{'label': '最想要', 'value': 'vl_mostwanted'}, {'label': '高评分', 'value': 'vl_bestrated'}])]),
    ('rank_scheduler', 'sync_javdb_top_movie', 'JavDB 影片榜单', [arg('rank_type_list', '榜单类型', 'multi-select')]),
    ('rank_scheduler', 'sync_library_top_cast', 'JavLibrary 演员榜单', []),
    ('avbase_scheduler', 'sync_avbase_daily', 'AvBase 上新同步', [arg('backward_offset_days', '往前天数'), arg('forward_offset_days', '往后天数')]),
    ('avbase_scheduler', 'sync_avbase_recent', 'AvBase 最近上架', []),
    ('movie_scheduler', 'sync_movies', '完善影片元数据', []),
    ('subscribe_scheduler', 'execute_rank_subscribe', '榜单订阅', [arg('rank_name_list', '榜单', 'multi-select', True), arg('limit', '订阅数量')]),
    ('subscribe_scheduler', 'execute_cast_subscribe', '演员订阅', []),
    ('subscribe_scheduler', 'execute_general_subscribe', '综合订阅', []),
    ('subscribe_scheduler', 'execute_subscribe', '执行订阅下载', []),
    ('report_scheduler', 'push_subscription_report', '发送订阅报表', [arg('report_period', '报表周期', 'select', True, options=[{'label': '日报', 'value': 'daily'}, {'label': '周报', 'value': 'weekly'}, {'label': '月报', 'value': 'monthly'}])]),
]


def _call(module, name, kwargs):
    runtime = get_runtime()
    runtime.check_cancelled()
    if name in {'execute_subscribe', 'download_by_route'}:
        require_download()
    if name in {'sync_sht_by_max_page', 'sync_x1080_by_max_page', 'sync_library_top_movie'}:
        start = int(kwargs.get('start_page') or 1)
        end = int(kwargs.get('max_page') or start)
        if start < 1 or end < start or end - start > 19:
            raise ValueError('一次最多抓取 20 页，起始页必须大于 0')
        kwargs['max_page'] = end
        if name != 'sync_library_top_movie':
            kwargs['start_page'] = start
    return getattr(import_module('.' + module, __package__), name)(**kwargs)


def _lazy(module, name):
    def invoke(**kwargs):
        return _call(module, name, kwargs)
    return invoke


FUNC_MAP = [{'func_name': name, 'func_label': label, 'func_args_rule': rules,
             'func': _lazy(module, name)} for module, name, label, rules in _TASKS]

for item in FUNC_MAP:
    for rule in item['func_args_rule']:
        if rule['key'] == 'rank_name_list':
            rule['options'] = SHARED_RANK_NAME_OPTIONS if item['func_name'] == 'sync_shared_movie_rank' else MOVIE_RANK_NAME_OPTIONS
        if rule['key'] == 'rank_type_list' and item['func_name'] == 'sync_javdb_top_movie':
            rule['options'] = [{'label': x['label'], 'value': x['value'][6:]} for x in MOVIE_RANK_NAME_OPTIONS if x['value'].startswith('javdb-')]
        if rule['key'] == 'section_id_list':
            sections = ([('2', '国产原创'), ('36', '亚洲无码原创'), ('38', '欧美无码'), ('37', '亚洲有码原创'), ('103', '高清中文字幕'), ('104', '素人有码系列'), ('151', '4K原版'), ('152', '韩国主播'), ('160', 'VR视频区'), ('39', '动漫原创'), ('107', '三级写真'), ('95', '综合讨论区'), ('142', '转贴交流区')]
                        if item['func_name'] == 'sync_sht_by_max_page' else [('5212', '国产品牌'), ('5206', '有码HD'), ('5207', '无码HD'), ('5208', 'FC2HD'), ('5216', 'MGSHD'), ('5479', '中文字幕'), ('5213', '探花精选'), ('5217', '主播精选')])
            rule['options'] = [{'label': label, 'value': value} for value, label in sections]


def find_func(name):
    return next((item for item in FUNC_MAP if item['func_name'] == name), None)


def restart_scheduler():
    return get_runtime().reschedule()


def start_scheduler():
    return restart_scheduler()
