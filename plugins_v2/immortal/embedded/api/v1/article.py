from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ...api.deps import get_current_user, api_key_or_jwt
from ...api.services import article_service
from ...core.database import get_db
from ...models.user import User
from ...schemas.article import ArticleQuery

router = APIRouter()


@router.post("/search")
def get_article_list(query: ArticleQuery, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return article_service.get_article_list(db, query)


@router.get("/categories")
def get_category(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return article_service.get_category(db)


@router.get("/torrents")
def get_torrent(keyword, db: Session = Depends(get_db), auth=Depends(api_key_or_jwt)):
    return article_service.get_torrents(keyword, db)


@router.get("/download")
def download_article(article_id: int, user: User = Depends(get_current_user)):
    return article_service.download_article(article_id)


@router.get("/download/manul")
async def manul_download(article_id: int, downloader, save_path, user: User = Depends(get_current_user)):
    return article_service.manul_download(article_id, downloader, save_path)


@router.get("/download/batch")
def batch_download_article(article_id_list: str, user: User = Depends(get_current_user)):
    return article_service.batch_download(article_id_list.split(','))


@router.get("/download/manul/batch")
def batch_manul_download(article_id_list: str, downloader: str, save_path: str, user: User = Depends(get_current_user)):
    return article_service.batch_manul_download(article_id_list.split(','), downloader, save_path)


@router.post('/import/excel')
async def import_data(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return await article_service.import_excel(file, db)


@router.get('/export/excel')
def export_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return article_service.export_article()
