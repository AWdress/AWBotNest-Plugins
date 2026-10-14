from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import priority_service
from ...core.database import get_db
from ...models import User
from ...schemas.priority import PriorityForm, UpdatePriorityForm

router = APIRouter()


@router.get('/')
def list_priority(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return priority_service.list_priority(db)


@router.post('/')
def add_priority(form: PriorityForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return priority_service.add_priority(db, form)


@router.put('/')
def update_priority(form: UpdatePriorityForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return priority_service.update_priority(db, form)


@router.delete('/{priority_id}')
def delete_priority(priority_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return priority_service.delete_priority(db, priority_id)
