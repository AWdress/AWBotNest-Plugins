"""
反馈循环服务

为关键操作提供验证和回退机制：
1. 规则变更的 dry-run 验证
2. 下载任务参数验证
3. Page Agent 输出格式验证
4. 配置变更的预检查
"""

import re
from typing import Any

from ...models import Article, Filter, Rule
from ...api.services.article_match_service import matches_article_filter, build_article_features
from ...utils import logger


class FeedbackResult:
    """反馈检查结果"""

    def __init__(self):
        self.passed = True
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add_error(self, message: str):
        self.passed = False
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_filter_regex(regex: str | None) -> FeedbackResult:
    """验证过滤器正则表达式是否有效"""
    result = FeedbackResult()

    if not regex:
        return result

    try:
        re.compile(regex)
    except re.error as e:
        result.add_error(f"正则表达式无效: {e}")

    # 检查常见的潜在问题
    if regex.startswith("^") and regex.endswith("$"):
        result.add_warning("正则同时使用 ^ 和 $，可能无法匹配多行文本")

    if ".*.*" in regex:
        result.add_warning("正则包含连续的 .*，可能匹配过多")

    return result


def validate_filter_consistency(filter_obj: Filter) -> FeedbackResult:
    """验证过滤器的各条件之间是否一致"""
    result = FeedbackResult()

    if not filter_obj:
        return result

    # 检查分辨率、字幕、马赛克是否设置了不可能的值
    valid_resolutions = {"8K", "4K", "1080p", None}
    valid_subtitles = {"中文", None}
    valid_mosaics = {"有码", "无码流出", "无码破解", "新模型", None}

    if filter_obj.resolutions:
        invalid = set(filter_obj.resolutions) - valid_resolutions - {None}
        if invalid:
            result.add_error(f"无效的分辨率值: {invalid}")

    if filter_obj.subtitles:
        invalid = set(filter_obj.subtitles) - valid_subtitles - {None}
        if invalid:
            result.add_error(f"无效的字幕值: {invalid}")

    if filter_obj.mosaic:
        invalid = set(filter_obj.mosaic) - valid_mosaics - {None}
        if invalid:
            result.add_error(f"无效的马赛克值: {invalid}")

    # 检查大小范围是否合理
    if filter_obj.min_size is not None and filter_obj.max_size is not None:
        if filter_obj.min_size > filter_obj.max_size:
            result.add_error(f"最小文件大小 ({filter_obj.min_size}) 大于最大文件大小 ({filter_obj.max_size})")

    return result


def dry_run_filter_on_articles(
    filter_obj: Filter, sample_articles: list[Article], limit: int = 20
) -> FeedbackResult:
    """
    Dry-run: 用过滤器测试一批样例文章，验证过滤器是否按预期工作

    返回:
    - 匹配数量
    - 匹配的文章标题示例
    - 不匹配的常见原因分析
    """
    result = FeedbackResult()

    if not filter_obj:
        result.add_warning("过滤器为空，将匹配所有文章")
        return result

    matched = []
    not_matched_reasons: dict[str, int] = {}

    for article in sample_articles[:limit]:
        if matches_article_filter(article, filter_obj):
            matched.append(article.title[:50] if article.title else "(无标题)")
        else:
            # 分析不匹配的原因
            features = build_article_features(article)
            filter_source = f"{article.website} {article.section} {article.category} {article.title}"

            if filter_obj.keyword and filter_obj.keyword not in filter_source:
                reason = "关键词不匹配"
            elif filter_obj.resolutions and features.get("resolution") not in filter_obj.resolutions:
                reason = f"分辨率不匹配 (期望: {filter_obj.resolutions}, 实际: {features.get('resolution')})"
            elif filter_obj.subtitles and features.get("subtitle") not in filter_obj.subtitles:
                reason = f"字幕不匹配 (期望: {filter_obj.subtitles}, 实际: {features.get('subtitle')})"
            elif filter_obj.mosaic and features.get("mosaic") not in filter_obj.mosaic:
                reason = f"马赛克不匹配 (期望: {filter_obj.mosaic}, 实际: {features.get('mosaic')})"
            elif filter_obj.min_size is not None and (article.size is None or article.size < filter_obj.min_size):
                reason = f"文件太小 (最小: {filter_obj.min_size}, 实际: {article.size})"
            elif filter_obj.max_size is not None and (article.size is None or article.size > filter_obj.max_size):
                reason = f"文件太大 (最大: {filter_obj.max_size}, 实际: {article.size})"
            else:
                reason = "正则不匹配"

            not_matched_reasons[reason] = not_matched_reasons.get(reason, 0) + 1

    result.add_warning(f"匹配 {len(matched)}/{min(len(sample_articles), limit)} 篇文章")

    if matched:
        sample_titles = ", ".join(matched[:3])
        result.add_warning(f"匹配示例: {sample_titles}")

    if not_matched_reasons:
        top_reasons = sorted(not_matched_reasons.items(), key=lambda x: x[1], reverse=True)[:3]
        reason_text = "; ".join(f"{k}({v})" for k, v in top_reasons)
        result.add_warning(f"不匹配原因分布: {reason_text}")

    return result


def validate_download_params(
    torrent_url: str | None = None,
    torrent_content: bytes | None = None,
    save_path: str | None = None,
) -> FeedbackResult:
    """验证下载参数是否有效"""
    result = FeedbackResult()

    if not torrent_url and not torrent_content:
        result.add_error("必须提供 torrent_url 或 torrent_content")

    if save_path and ".." in save_path:
        result.add_error("save_path 不能包含 .. (路径穿越风险)")

    if torrent_url:
        if not (
            torrent_url.startswith("magnet:")
            or torrent_url.startswith("http://")
            or torrent_url.startswith("https://")
            or torrent_url.startswith("bt://")
        ):
            result.add_error(f"不支持的 torrent URL 协议: {torrent_url[:50]}")

    if torrent_content:
        if len(torrent_content) < 100:
            result.add_error("torrent_content 太短，可能无效")
        if not (
            torrent_content.startswith(b"magnet:")
            or b"announce" in torrent_content.lower()
            or torrent_content.startswith(b"d8:")
        ):
            result.add_warning("torrent_content 格式可能不正确")

    return result


def validate_page_agent_response(response: dict[str, Any]) -> FeedbackResult:
    """验证 Page Agent 返回的响应格式是否正确"""
    result = FeedbackResult()

    if not isinstance(response, dict):
        result.add_error("Page Agent 响应必须是 JSON 对象")
        return result

    # 检查常见的必需字段（根据实际 API 而定）
    # 这里做基础验证，具体的根据 Page Agent 实现调整

    if "error" in response:
        result.add_error(f"Page Agent 返回错误: {response.get('error')}")

    # 检查响应是否包含合理的内容
    if "content" not in response and "text" not in response and "message" not in response:
        if "choices" not in response:
            result.add_warning("Page Agent 响应可能缺少 content/text/message 字段")

    # 检查是否包含明显的错误标记
    content_str = str(response).lower()
    error_markers = ["error", "exception", "traceback", "failed"]
    for marker in error_markers:
        if marker in content_str and "error_code" not in content_str:
            result.add_warning(f"响应可能包含错误标记: {marker}")

    return result


def validate_rule_before_activation(rule: Rule) -> FeedbackResult:
    """激活规则前的全面验证"""
    result = FeedbackResult()

    if not rule:
        result.add_error("规则不能为空")
        return result

    # 验证关联的过滤器
    if hasattr(rule, "filter") and rule.filter:
        result.errors.extend(validate_filter_regex(rule.filter.regex).errors)
        result.warnings.extend(validate_filter_regex(rule.filter.regex).warnings)
        result.errors.extend(validate_filter_consistency(rule.filter).errors)
        result.warnings.extend(validate_filter_consistency(rule.filter).warnings)

    # 检查规则是否关联了订阅
    if hasattr(rule, "subscribes"):
        if not rule.subscribes or len(rule.subscribes) == 0:
            result.add_warning("规则没有关联任何订阅，激活后不会产生任何效果")

    return result
