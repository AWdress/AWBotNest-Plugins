from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user, api_key_or_jwt
from ...api.services import rank_service
from ...core.database import get_db
from ...models import User

router = APIRouter()


@router.get('/movie')
def rank_movie(
    rank_name: str,
    page: int = 1,
    library_filter: str = 'all',
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return rank_service.rank_movie(db, rank_name, page=page, library_filter=library_filter)


@router.get('/share')
def share_rank(rank_name: str | None = None, rank_type: str | None = None, db: Session = Depends(get_db), auth=Depends(api_key_or_jwt)):
    return rank_service.share_rank(db, rank_name, rank_type)


@router.get('/movie/share')
def share_rank_movie(rank_name: str, db: Session = Depends(get_db), auth=Depends(api_key_or_jwt)):
    return rank_service.share_rank(db, rank_name, rank_type='movie')


@router.get('/cast')
def rank_cast(rank_name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return rank_service.rank_cast(db, rank_name)


@router.get('/cast/share')
def share_rank_cast(rank_name: str, db: Session = Depends(get_db), auth=Depends(api_key_or_jwt)):
    return rank_service.share_rank(db, rank_name, rank_type='cast')
