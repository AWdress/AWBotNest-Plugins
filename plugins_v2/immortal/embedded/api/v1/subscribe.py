from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import subscribe_service
from ...core.database import get_db
from ...models import User
from ...schemas.subscribe import (
    CastSubscribePageParam,
    CastSubscribeParam,
    CastSubscribeUpdateParam,
    GeneralSubscribePageParam,
    GeneralSubscribeParam,
    GeneralSubscribeUpdateParam,
    SubscribeCleanupDiagnosticParam,
    SubscribePageParam,
    SubscribeParam,
    SubscribeUpdateParam,
)

router = APIRouter()


@router.post('/sub')
def sub_movie(param: SubscribeParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.sub_movie(param, db)


@router.put('/cancel')
def cancel_subscribe(subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.cancel_subscribe(subscribe_id, db)


@router.put('/pause')
def pause_subscribe(subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.pause_subscribe(subscribe_id, db)


@router.put('/resume')
def resume_subscribe(subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.resume_subscribe(subscribe_id, db)


@router.put('/execute')
def execute_subscribe_download(subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.execute_subscribe_download(subscribe_id, db)


@router.put('/update')
def update_subscribe(param: SubscribeUpdateParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.update_subscribe(param, db)

@router.post('/search')
def list_subscribe(param: SubscribePageParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.list_subscribe(param, db)


@router.post('/cast/sub')
def sub_cast(param: CastSubscribeParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.sub_cast(param, db)


@router.post('/general/sub')
def sub_general(param: GeneralSubscribeParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.sub_general(param, db)


@router.post('/general/search')
def list_general_subscribe(param: GeneralSubscribePageParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.list_general_subscribe(param, db)


@router.post('/cleanup/diagnose')
def diagnose_subscription_cleanup(param: SubscribeCleanupDiagnosticParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.diagnose_subscription_cleanup_candidates(param, db)


@router.get('/general/options')
def get_general_subscribe_options(
    publisher: str | None = Query(default=None),
    series: str | None = Query(default=None),
    producer: str | None = Query(default=None),
    genres: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return subscribe_service.get_general_subscribe_options(
        db,
        publisher=publisher,
        series=series,
        producer=producer,
        genres=genres,
    )


@router.put('/general/update')
def update_general_subscribe(param: GeneralSubscribeUpdateParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.update_general_subscribe(param, db)


@router.put('/general/cancel')
def cancel_general_subscribe(general_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.cancel_general_subscribe(general_subscribe_id, db)


@router.put('/general/pause')
def pause_general_subscribe(general_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.pause_general_subscribe(general_subscribe_id, db)


@router.put('/general/resume')
def resume_general_subscribe(general_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.resume_general_subscribe(general_subscribe_id, db)


@router.put('/cast/update')
def update_cast_subscribe(param: CastSubscribeUpdateParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.update_cast_subscribe(param, db)


@router.put('/cast/cancel')
def cancel_cast_subscribe(cast_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.cancel_cast_subscribe(cast_subscribe_id, db)


@router.put('/cast/pause')
def pause_cast_subscribe(cast_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.pause_cast_subscribe(cast_subscribe_id, db)


@router.put('/cast/resume')
def resume_cast_subscribe(cast_subscribe_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.resume_cast_subscribe(cast_subscribe_id, db)


@router.post('/cast/search')
def list_cast_subscribe(param: CastSubscribePageParam, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return subscribe_service.list_cast_subscribe(param, db)
