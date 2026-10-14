from collections import Counter
from collections.abc import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import Article, Rule
from ...schemas.response import success
from ...schemas.rule import RuleForm

ALL_VALUE = 'ALL'


def _validate_rule_regex(regex: str | None) -> None:
    """校验 Rule.regex 语法，避免坏正则入库后把整批订阅任务搞挂。"""
    if not regex:
        return
    try:
        import re as _re
        _re.compile(regex)
    except _re.error as exc:
        raise ValueError(f'Invalid rule regex: {exc}') from exc


def normalize_rule_values(value, *, include_all_when_empty: bool = True) -> list[str]:
    if value is None:
        return [ALL_VALUE] if include_all_when_empty else []

    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        values: list[str] = []
    else:
        values = [str(item).strip() for item in value if str(item or '').strip()]

    unique_values: list[str] = []
    for item in values:
        if item not in unique_values:
            unique_values.append(item)

    if not unique_values:
        return [ALL_VALUE] if include_all_when_empty else []
    if ALL_VALUE in unique_values:
        return [ALL_VALUE]
    return unique_values


def rule_matches_option(options, current_value: str | None) -> bool:
    normalized_options = normalize_rule_values(options)
    if ALL_VALUE in normalized_options:
        return True
    value = str(current_value or '').strip()
    return value in normalized_options


def serialize_rule(rule: Rule) -> dict:
    return {
        'id': rule.id,
        'website': normalize_rule_values(rule.website),
        'section': normalize_rule_values(rule.section),
        'category': normalize_rule_values(rule.category),
        'regex': rule.regex or '',
        'downloader': rule.downloader,
        'save_path': rule.save_path,
    }


def list_rule(db: Session):
    rules = db.query(Rule).order_by(Rule.id.desc()).all()
    return success([serialize_rule(rule) for rule in rules])


def add_rule(db: Session, rule_form: RuleForm):
    _validate_rule_regex(rule_form.regex)
    rule = Rule(
        website=normalize_rule_values(rule_form.website),
        section=normalize_rule_values(rule_form.section),
        category=normalize_rule_values(rule_form.category),
        regex=rule_form.regex or '',
        downloader=rule_form.downloader,
        save_path=rule_form.save_path,
    )
    db.add(rule)
    db.flush()
    return success(serialize_rule(rule))


def update_rule(db: Session, rule_form: RuleForm):
    _validate_rule_regex(rule_form.regex)
    rule = db.get(Rule, rule_form.id)
    if rule:
        rule.website = normalize_rule_values(rule_form.website)
        rule.section = normalize_rule_values(rule_form.section)
        rule.category = normalize_rule_values(rule_form.category)
        rule.regex = rule_form.regex or ''
        rule.downloader = rule_form.downloader
        rule.save_path = rule_form.save_path
    return success()


def delete_rule(db: Session, rule_id):
    rule = db.get(Rule, rule_id)
    db.delete(rule)
    return success()


def get_rule_options(db: Session, website: list[str] | None = None):
    selected_websites = [item for item in normalize_rule_values(website) if item != ALL_VALUE]

    website_rows = (
        db.query(Article.website, func.count(Article.id).label('count'))
        .filter(Article.website.isnot(None), Article.website != '')
        .group_by(Article.website)
        .all()
    )

    section_query = (
        db.query(Article.section, Article.category, func.count(Article.id).label('count'))
        .filter(Article.section.isnot(None), Article.section != '')
    )
    if selected_websites:
        section_query = section_query.filter(Article.website.in_(selected_websites))
    section_rows = section_query.group_by(Article.section, Article.category).all()

    websites = [
        {'name': name, 'count': count}
        for name, count in sorted(website_rows, key=lambda item: (-item[1], item[0]))
    ]

    section_counter: Counter[str] = Counter()
    category_map: dict[str, Counter[str]] = {}
    for section, category, count in section_rows:
        if not section:
            continue
        section_counter[section] += count
        if category:
            category_map.setdefault(section, Counter())[category] += count

    sections = []
    for section_name, count in sorted(section_counter.items(), key=lambda item: (-item[1], item[0])):
        categories = [
            {'name': category_name, 'count': category_count}
            for category_name, category_count in sorted(
                category_map.get(section_name, {}).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        sections.append({
            'name': section_name,
            'count': count,
            'categories': categories,
        })

    return success({
        'websites': websites,
        'sections': sections,
    })
