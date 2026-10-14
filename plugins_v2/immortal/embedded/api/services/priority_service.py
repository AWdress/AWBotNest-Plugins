from sqlalchemy.orm import Session

from ...models import CastSubscribe, Subscribe
from ...models.priority import Priority
from ...schemas.priority import PriorityForm, UpdatePriorityForm
from ...schemas.response import success
from ...utils.db_lock import acquire_subscribe_write_lock


def list_priority(db: Session):
    priorities = (
        db.query(Priority)
        .order_by(Priority.is_default.desc(),Priority.id.asc())
        .all()
    )

    return success(priorities)


def add_priority(db: Session, form: PriorityForm):
    priority_obj = Priority(
        priority_name=form.priority_name,
        resolutions=form.resolutions,
        subtitles=form.subtitles,
        mosaic=form.mosaic,
        priority_sort=form.priority_sort,
        is_default=form.is_default
    )
    if form.is_default:
        db.query(Priority).update({"is_default": False})
    db.add(priority_obj)
    return success()


def update_priority(db: Session, form: UpdatePriorityForm):
    priority_obj = db.get(Priority, form.id)
    priority_obj.priority_name = form.priority_name
    priority_obj.resolutions = form.resolutions
    priority_obj.subtitles = form.subtitles
    priority_obj.mosaic = form.mosaic
    priority_obj.priority_sort = form.priority_sort
    priority_obj.is_default=form.is_default
    if form.is_default:
        db.query(Priority).filter(Priority.id != priority_obj.id, Priority.is_default == True).update({"is_default": False})
    return success()


def delete_priority(db: Session, priority_id: int):
    acquire_subscribe_write_lock(db)
    priority_obj = db.get(Priority, priority_id)
    if not priority_obj:
        raise ValueError('Priority not found')

    db.query(Subscribe).filter(Subscribe.priority_id == priority_id).update(
        {"priority_id": None},
        synchronize_session=False,
    )
    db.query(CastSubscribe).filter(CastSubscribe.priority_id == priority_id).update(
        {"priority_id": None},
        synchronize_session=False,
    )
    db.delete(priority_obj)
    return success()
