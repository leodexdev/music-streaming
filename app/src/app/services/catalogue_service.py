from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def search_tracks(session: Session, query: str, limit: int) -> list[dict]:
    needle = query.strip()
    if not needle:
        raise HTTPException(422, "Search text cannot be empty")
    escaped = needle.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    rows = session.execute(
        text(
            """
            SELECT id, album_id, title, position, duration_seconds, explicit, isrc
            FROM track
            WHERE title ILIKE :pattern ESCAPE '!'
            ORDER BY title, id
            LIMIT :limit
            """
        ),
        {"pattern": f"%{escaped}%", "limit": limit},
    )
    return [dict(row._mapping) for row in rows]


def get_album(session: Session, album_id: int) -> dict:
    album = session.execute(
        text(
            """
            SELECT al.id, al.title, al.type, al.release_date, al.label_id, l.name AS label
            FROM album AS al
            LEFT JOIN label AS l ON l.id = al.label_id
            WHERE al.id = :album_id
            """
        ),
        {"album_id": album_id},
    ).one_or_none()
    if album is None:
        raise HTTPException(404, "Album not found")

    artists = session.execute(
        text(
            """
            SELECT a.id, a.name, aa.position
            FROM album_artist AS aa
            JOIN artist AS a ON a.id = aa.artist_id
            WHERE aa.album_id = :album_id
            ORDER BY aa.position, a.id
            """
        ),
        {"album_id": album_id},
    )
    tracks = session.execute(
        text(
            """
            SELECT id, title, position, duration_seconds, explicit, isrc
            FROM track
            WHERE album_id = :album_id
            ORDER BY position, id
            """
        ),
        {"album_id": album_id},
    )
    result = dict(album._mapping)
    result["artists"] = [dict(row._mapping) for row in artists]
    result["tracks"] = [dict(row._mapping) for row in tracks]
    return result


def get_artist(session: Session, artist_id: int) -> dict:
    artist = session.execute(
        text(
            """
            SELECT id, name, country, label_id, verified
            FROM artist
            WHERE id = :artist_id
            """
        ),
        {"artist_id": artist_id},
    ).one_or_none()
    if artist is None:
        raise HTTPException(404, "Artist not found")

    albums = session.execute(
        text(
            """
            SELECT al.id, al.title, al.type, al.release_date,
                   aa.position AS artist_position, count(t.id) AS track_count
            FROM album_artist AS aa
            JOIN album AS al ON al.id = aa.album_id
            LEFT JOIN track AS t ON t.album_id = al.id
            WHERE aa.artist_id = :artist_id
            GROUP BY al.id, aa.position
            ORDER BY al.release_date DESC, al.id
            """
        ),
        {"artist_id": artist_id},
    )
    result = dict(artist._mapping)
    result["albums"] = [dict(row._mapping) for row in albums]
    return result
