from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...api.services import movie_service
from ...core.database import get_db
from ...models import User
from ...schemas.movie import MovieRecommendParam, MovieSearchParam

router = APIRouter()


@router.post('/search')
def search_movies(
    param: MovieSearchParam,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return movie_service.search_movies(param, db)


@router.post('/network-search')
def network_search_movies(
    param: MovieSearchParam,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return movie_service.network_search_movies(param, db)


@router.get('/stats/frequency')
def movie_frequency_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return movie_service.get_movie_frequency_stats(db)


@router.post('/recommend/subscribed')
def recommend_subscribed_movies(
    param: MovieRecommendParam,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return movie_service.recommend_subscribed_movies(param, db)
