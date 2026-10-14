from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import download_log_service
from ...core.database import get_db
from ...models import User
from ...schemas.download_log import DownloadLogFilter

router = APIRouter()


@router.post('/search')
def page_task_log(params: DownloadLogFilter, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return download_log_service.get_download_log_page(db, params)


@router.get('/state')
def get_download_state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return download_log_service.get_download_state(db)
