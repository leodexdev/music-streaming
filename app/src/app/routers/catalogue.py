from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.services import catalogue_service

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.get("/tracks/search")
def search_tracks(
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    return catalogue_service.search_tracks(session, q, limit)


@router.get("/albums/{album_id}")
def get_album(
    album_id: int = Path(gt=0),
    session: Session = Depends(get_session),
):
    return catalogue_service.get_album(session, album_id)


@router.get("/artists/{artist_id}")
def get_artist(
    artist_id: int = Path(gt=0),
    session: Session = Depends(get_session),
):
    return catalogue_service.get_artist(session, artist_id)
