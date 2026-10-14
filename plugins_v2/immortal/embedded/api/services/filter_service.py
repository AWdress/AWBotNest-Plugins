import re

from sqlalchemy.orm import Session

from ...models import CastSubscribe, Subscribe
from ...models.filter import Filter
from ...schemas.filter import FilterForm, UpdateFilterForm
from ...schemas.response import success
from ...utils.db_lock import acquire_subscribe_write_lock


def _validate_filter_regex(regex: str | None):
    if not regex:
        return
    try:
        re.compile(regex)
    except re.error as exc:
        raise ValueError(f'Invalid filter regex: {exc}') from exc


def list_filter(db: Session):
    filters = (
        db.query(Filter)
        .order_by(Filter.is_default.desc(),Filter.id.asc())
        .all()
    )

    return success(filters)


def add_filter(db: Session, form: FilterForm):
    _validate_filter_regex(form.regex)
    filter_obj = Filter(
        filter_name=form.filter_name,
        keyword=form.keyword,
        regex=form.regex,
        resolutions=form.resolutions,
        subtitles=form.subtitles,
        mosaic=form.mosaic,
        min_size=form.min_size,
        max_size=form.max_size,
        skip_in_library_check=form.skip_in_library_check,
        enable_pre_download=form.enable_pre_download,
        is_default=form.is_default
    )
    if form.is_default:
        db.query(Filter).update({"is_default": False})
    db.add(filter_obj)

    return success()


def update_filter(db: Session, form: UpdateFilterForm):
    _validate_filter_regex(form.regex)
    filter_obj = db.get(Filter, form.id)
    filter_obj.filter_name = form.filter_name
    filter_obj.keyword = form.keyword
    filter_obj.regex = form.regex
    filter_obj.resolutions = form.resolutions
    filter_obj.subtitles = form.subtitles
    filter_obj.mosaic = form.mosaic
    filter_obj.min_size = form.min_size
    filter_obj.max_size = form.max_size
    filter_obj.skip_in_library_check = form.skip_in_library_check
    filter_obj.enable_pre_download = form.enable_pre_download
    filter_obj.is_default = form.is_default
    if form.is_default:
        db.query(Filter).filter(Filter.id != filter_obj.id, Filter.is_default == True).update({"is_default": False})
    return success()


def delete_filter(db: Session, filter_id: int):
    acquire_subscribe_write_lock(db)
    filter_obj = db.get(Filter, filter_id)
    if not filter_obj:
        raise ValueError('Filter not found')

    db.query(Subscribe).filter(Subscribe.filter_id == filter_id).update(
        {"filter_id": None},
        synchronize_session=False,
    )
    db.query(CastSubscribe).filter(CastSubscribe.filter_id == filter_id).update(
        {"filter_id": None},
        synchronize_session=False,
    )
    db.delete(filter_obj)
    return success()
