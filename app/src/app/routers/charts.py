from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Path, Query

from app.database import redis_client

router = APIRouter(prefix="/charts", tags=["charts"])
LISBON = ZoneInfo("Europe/Lisbon")


@router.get("")
def get_chart(
    country: str | None = Query(default=None, min_length=2, max_length=2),
):
    day = datetime.now(LISBON).date()
    date_part = day.strftime("%Y%m%d")
    key = (
        f"charts:{date_part}:global"
        if country is None
        else f"charts:{date_part}:country:{country.upper()}"
    )
    ranked = redis_client.zrevrange(key, 0, 49, withscores=True)
    return {
        "date": day.isoformat(),
        "country": country.upper() if country else None,
        "tracks": [
            {"track_id": int(track_id), "streams": int(score)}
            for track_id, score in ranked
        ],
    }


@router.get("/last50/{listener_id}")
def get_last_plays(listener_id: int = Path(gt=0)):
    tracks = redis_client.lrange(f"last50:{listener_id}", 0, 49)
    return {
        "listener_id": listener_id,
        "tracks": [int(track_id) for track_id in tracks],
    }
