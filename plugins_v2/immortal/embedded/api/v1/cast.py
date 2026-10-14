from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import cast_service
from ...core.database import get_db
from ...models import User
from ...schemas.cast import CastSearchParam

router = APIRouter()


@router.post('/search')
def search_casts(
    param: CastSearchParam,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return cast_service.search_casts(param, db)


@router.post('/network-search')
def network_search_casts(
    param: CastSearchParam,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return cast_service.network_search_casts(param, db)
