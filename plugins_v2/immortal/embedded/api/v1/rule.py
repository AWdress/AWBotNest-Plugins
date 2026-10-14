from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import rule_service
from ...core.database import get_db
from ...models import User
from ...schemas.rule import RuleForm

router = APIRouter()


@router.get('/')
def list_rule(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rule_service.list_rule(db)


@router.get('/options')
def get_rule_options(
    website: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return rule_service.get_rule_options(db, website=website)


@router.post('/')
def add_rule(rule_form: RuleForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rule_service.add_rule(db, rule_form)


@router.put('/')
def update_rule(rule_form: RuleForm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rule_service.update_rule(db, rule_form)


@router.delete('/{rule_id}')
def delete_rule(rule_id, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rule_service.delete_rule(db, rule_id)
