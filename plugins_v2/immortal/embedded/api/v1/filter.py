from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import filter_service
from ...core.database import get_db
from ...models import User
from ...schemas.filter import FilterForm, UpdateFilterForm

router = APIRouter()


@router.get('/')
def list_filter(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return filter_service.list_filter(db)


@router.post('/')
def add_filter(form: FilterForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return filter_service.add_filter(db, form)


@router.put('/')
def update_filter(form: UpdateFilterForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return filter_service.update_filter(db, form)


@router.delete('/{filter_id}')
def delete_filter(filter_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return filter_service.delete_filter(db, filter_id)
