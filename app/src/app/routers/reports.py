from fastapi import APIRouter, Path, Query

from app.database import mongo_db
from app.services import reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/listeners/{listener_id}/yearly-summary/{year}")
def yearly_listener_report(
    listener_id: int = Path(gt=0),
    year: int = Path(ge=1900, le=9999),
):
    month_prefix = f"{year:04d}-"
    documents = mongo_db["listener_month_stats"].find(
        {
            "listener_id": listener_id,
            "month": {"$gte": f"{month_prefix}01", "$lte": f"{month_prefix}12"},
        },
        {"_id": 0, "plays": 1, "streams": 1, "seconds": 1, "tracks": 1, "days": 1},
    )
    return reports_service.yearly_listener_summary(documents, listener_id, year)


@router.get("/artists/{artist_id}/streams")
def artist_stream_report(
    artist_id: int = Path(gt=0),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    month: str | None = Query(default=None),
):
    return reports_service.artist_streams(
        mongo_db,
        artist_id,
        country,
        month,
    )


@router.get("/genres/top")
def top_genre_report(
    country: str = Query(min_length=2, max_length=2),
    month: str = Query(),
):
    return reports_service.top_genres(mongo_db, country, month)
