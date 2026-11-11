from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
import re

from fastapi import HTTPException


def yearly_listener_summary(
    documents: Iterable[dict],
    listener_id: int,
    year: int,
) -> dict:
    plays = streams = seconds = 0
    tracks: dict[int, dict] = {}
    artists: dict[int, dict] = {}
    genres: dict[str, int] = defaultdict(int)
    days: dict[str, int] = defaultdict(int)
    found = False

    for document in documents:
        found = True
        plays += int(document["plays"])
        streams += int(document["streams"])
        seconds += int(document["seconds"])
        for track in document.get("tracks", []):
            track_id = int(track["track_id"])
            item = tracks.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "title": track["title"],
                    "streams": 0,
                    "seconds": 0,
                },
            )
            item["streams"] += int(track["streams"])
            item["seconds"] += int(track["seconds"])
            for genre in track.get("genres", []):
                genres[genre] += int(track["streams"])
            for artist_id, artist_name in zip(
                track.get("artist_ids", []), track.get("artists", [])
            ):
                artist_id = int(artist_id)
                item = artists.setdefault(
                    artist_id,
                    {"artist_id": artist_id, "artist": artist_name, "streams": 0},
                )
                item["streams"] += int(track["streams"])
        for activity in document.get("days", []):
            days[activity["day"]] += int(activity["seconds"])

    if not found:
        raise HTTPException(404, "No report data found for this listener and year")

    top_tracks = sorted(
        tracks.values(),
        key=lambda item: (-item["streams"], -item["seconds"], item["track_id"]),
    )[:5]
    top_artists = sorted(
        artists.values(), key=lambda item: (-item["streams"], item["artist_id"])
    )[:5]
    top_genre = min(genres, key=lambda genre: (-genres[genre], genre)) if genres else None
    peak_day = min(days, key=lambda day: (-days[day], day)) if days else None
    return {
        "listener_id": listener_id,
        "year": year,
        "plays": plays,
        "streams": streams,
        "total_minutes": round(seconds / 60, 2),
        "top_tracks": top_tracks,
        "top_artists": top_artists,
        "top_genre": top_genre,
        "peak_day": peak_day,
        "peak_day_seconds": days[peak_day] if peak_day else 0,
    }


def _validate_month(month: str) -> None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, "Month must use YYYY-MM format")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(422, "Month must use YYYY-MM format") from exc


def artist_streams(mongo_db, artist_id: int, country: str | None, month: str | None) -> list[dict]:
    if month is not None:
        _validate_month(month)
    query = {"artist_id": artist_id}
    if country is not None:
        query["country"] = country.upper()
    if month is not None:
        query["month"] = month
    cursor = mongo_db["artist_country_month"].find(
        query,
        {"_id": 0, "artist_id": 1, "artist_name": 1, "country": 1, "month": 1, "streams": 1},
    ).sort([("month", -1), ("country", 1)])
    return list(cursor)


def top_genres(mongo_db, country: str, month: str) -> dict:
    _validate_month(month)
    normalized_country = country.upper()
    rows = mongo_db["genre_country_month"].aggregate(
        [
            {"$match": {"country": normalized_country, "month": month}},
            {"$sort": {"streams": -1, "genre": 1}},
            {"$limit": 5},
            {"$project": {"_id": 0, "genre": 1, "stream_count": "$streams"}},
        ]
    )
    return {
        "country": normalized_country,
        "month": month,
        "top_genres": list(rows),
    }
