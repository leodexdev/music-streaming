from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import mongo_db, redis_client

DeviceType = Literal["mobile", "desktop", "web", "speaker", "car"]
EventType = Literal["pause", "seek", "end"]


class StartPlaybackRequest(BaseModel):
    track_id: int
    device_id: str
    device_type: DeviceType
    country: str


class HeartbeatRequest(BaseModel):
    track_id: int
    device_id: str
    position_seconds: int = 0
    device_type: DeviceType | None = None


class ReportPlaybackRequest(BaseModel):
    track_id: int
    device_id: str
    position_seconds: int = 0
    seconds_played: int = 0
    event_type: EventType = "end"
    device_type: DeviceType | None = None


class SkipPlaybackRequest(BaseModel):
    track_id: int
    device_id: str
    position_seconds: int = 0
    device_type: DeviceType | None = None


def _active_device_key(listener_id: int) -> str:
    return f"active_device:{listener_id}"


def _skip_key(listener_id: int) -> str:
    now = datetime.now(timezone.utc)
    return f"skips:{listener_id}:{now.strftime('%Y%m%d%H')}"


def _track_exists(session: Session, track_id: int) -> bool:
    row = session.execute(
        text("SELECT 1 FROM track WHERE id = :track_id"),
        {"track_id": track_id},
    ).first()
    return row is not None


def _ensure_device_active(listener_id: int, device_id: str) -> None:
    current = redis_client.get(_active_device_key(listener_id))
    if current != device_id:
        raise HTTPException(409, "Device is not active for this listener")


def start_playback(session: Session, listener_id: int, body: StartPlaybackRequest) -> dict:
    if not _track_exists(session, body.track_id):
        raise HTTPException(404, "Track not found")

    key = _active_device_key(listener_id)
    redis_client.set(key, body.device_id, ex=60)

    session.execute(
        text(
            """
            INSERT INTO play (listener_id, track_id, started_at, seconds_played, device_type, country)
            VALUES (:listener_id, :track_id, now(), 0, :device_type, :country)
            """
        ),
        {
            "listener_id": listener_id,
            "track_id": body.track_id,
            "device_type": body.device_type,
            "country": body.country,
        },
    )
    session.commit()

    mongo_db.playback_events.insert_one(
        {
            "listener_id": listener_id,
            "device_id": body.device_id,
            "device_type": body.device_type,
            "track_id": body.track_id,
            "event_type": "start",
            "position_seconds": 0,
            "ts": datetime.now(timezone.utc),
        }
    )

    return {
        "listener_id": listener_id,
        "track_id": body.track_id,
        "device_id": body.device_id,
        "status": "playing",
    }


def heartbeat_playback(session: Session, listener_id: int, body: HeartbeatRequest) -> dict:
    _ensure_device_active(listener_id, body.device_id)
    if not _track_exists(session, body.track_id):
        raise HTTPException(404, "Track not found")

    redis_client.set(_active_device_key(listener_id), body.device_id, ex=60)
    mongo_db.playback_events.insert_one(
        {
            "listener_id": listener_id,
            "device_id": body.device_id,
            "device_type": body.device_type or "mobile",
            "track_id": body.track_id,
            "event_type": "heartbeat",
            "position_seconds": body.position_seconds,
            "ts": datetime.now(timezone.utc),
        }
    )
    return {"status": "ok", "listener_id": listener_id, "device_id": body.device_id}


def report_playback(session: Session, listener_id: int, body: ReportPlaybackRequest) -> dict:
    _ensure_device_active(listener_id, body.device_id)
    if not _track_exists(session, body.track_id):
        raise HTTPException(404, "Track not found")

    session.execute(
        text(
            """
            UPDATE play
            SET seconds_played = :seconds_played
            WHERE listener_id = :listener_id
              AND track_id = :track_id
              AND started_at = (
                  SELECT MAX(started_at) FROM play WHERE listener_id = :listener_id AND track_id = :track_id
              )
            """
        ),
        {
            "seconds_played": body.seconds_played,
            "listener_id": listener_id,
            "track_id": body.track_id,
        },
    )
    session.commit()

    mongo_db.playback_events.insert_one(
        {
            "listener_id": listener_id,
            "device_id": body.device_id,
            "device_type": body.device_type or "mobile",
            "track_id": body.track_id,
            "event_type": body.event_type,
            "position_seconds": body.position_seconds,
            "ts": datetime.now(timezone.utc),
        }
    )
    return {
        "listener_id": listener_id,
        "track_id": body.track_id,
        "seconds_played": body.seconds_played,
        "status": "reported",
    }


def skip_playback(session: Session, listener_id: int, body: SkipPlaybackRequest) -> dict:
    _ensure_device_active(listener_id, body.device_id)
    if not _track_exists(session, body.track_id):
        raise HTTPException(404, "Track not found")

    key = _skip_key(listener_id)
    pipe = redis_client.pipeline(transaction=True)
    pipe.set(key, 0, ex=3600, nx=True)
    pipe.incr(key)
    _, count = pipe.execute()
    current = int(count)
    if current > 6:
        raise HTTPException(409, "Skip limit reached for this hour")

    session.execute(
        text(
            """
            UPDATE play
            SET seconds_played = :seconds_played
            WHERE listener_id = :listener_id
              AND track_id = :track_id
              AND started_at = (
                  SELECT MAX(started_at) FROM play WHERE listener_id = :listener_id AND track_id = :track_id
              )
            """
        ),
        {
            "seconds_played": body.position_seconds,
            "listener_id": listener_id,
            "track_id": body.track_id,
        },
    )
    session.commit()

    mongo_db.playback_events.insert_one(
        {
            "listener_id": listener_id,
            "device_id": body.device_id,
            "device_type": body.device_type or "mobile",
            "track_id": body.track_id,
            "event_type": "skip",
            "position_seconds": body.position_seconds,
            "ts": datetime.now(timezone.utc),
        }
    )

    return {
        "listener_id": listener_id,
        "track_id": body.track_id,
        "skip_count": current,
        "status": "skipped",
    }
