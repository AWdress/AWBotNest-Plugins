import re
from typing import Any

from ...models import Article, Filter
from ...utils import logger

cn_keywords = ['中字', '中文字幕', '色花堂', '字幕']
uc_keywords = ['UC', 'uc', '无码', '步兵']
new_model_keywords = ['新模型', 'lada', 'LADA']
uhd_keywords = ['4k', '8k', '2160p', '4K', '8K', '2160P']


def has_chinese(title: str):
    chinese = False
    for keyword in cn_keywords:
        if title.find(keyword) > -1:
            chinese = True
            break
    return chinese


def has_uc(title: str):
    uc = False
    for keyword in uc_keywords:
        if title.find(keyword) > -1:
            uc = True
            break
    return uc

def has_uhd(title: str):
    uhd = False
    for keyword in uhd_keywords:
        if title.find(keyword) > -1:
            uhd = True
            break
    return uhd


def is_new_model(title: str):
    new_model = False
    for keyword in new_model_keywords:
        if title.find(keyword) > -1:
            new_model = True
            break
    return new_model


def detect_resolution(title: str) -> str | None:
    text = (title or '').lower()
    if '8k' in text or '4320p' in text:
        return '8K'
    if '4k' in text or '2160p' in text:
        return '4K'
    return '1080p'


def detect_subtitle(title: str) -> str | None:
    if has_chinese(title):
        return '中文'
    return None


def detect_mosaic(title: str) -> str | None:
    if '流出' in title:
        return '无码流出'
    if is_new_model(title):
        return '新模型'
    if has_uc(title):
        return '无码破解'
    return '有码'


def build_article_filter_source(article: Article) -> str:
    return ' '.join(
        part for part in [article.website, article.section, article.category, article.title] if part
    )


def build_article_features(article: Article) -> dict[str, Any]:
    feature_source = build_article_filter_source(article)
    return {
        'resolution': detect_resolution(feature_source),
        'subtitle': detect_subtitle(feature_source),
        'mosaic': detect_mosaic(feature_source),
        'size': article.size,
    }


def matches_filter_regex(article: Article, regex: str | None) -> bool:
    if not regex:
        return True

    target = build_article_filter_source(article)
    try:
        return re.search(regex, target) is not None
    except re.error as exc:
        logger.warning(f'过滤器正则无效，已跳过该过滤器匹配 | regex={regex}, error={exc}')
        return False


def matches_article_filter(article: Article, filter_obj: Filter | None) -> bool:
    if not filter_obj:
        return True

    filter_source = build_article_filter_source(article)
    features = build_article_features(article)

    if filter_obj.keyword and filter_obj.keyword not in filter_source:
        return False

    if not matches_filter_regex(article, filter_obj.regex):
        return False

    if filter_obj.resolutions and features['resolution'] not in filter_obj.resolutions:
        return False

    if filter_obj.subtitles and features['subtitle'] not in filter_obj.subtitles:
        return False

    if filter_obj.mosaic and features['mosaic'] not in filter_obj.mosaic:
        return False

    if filter_obj.min_size is not None:
        if article.size is None or article.size < filter_obj.min_size:
            return False

    if filter_obj.max_size is not None:
        if article.size is None or article.size > filter_obj.max_size:
            return False

    return True
