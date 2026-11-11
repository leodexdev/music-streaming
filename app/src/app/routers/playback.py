from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.deps import get_actor_id
from app.services.playback_service import (
    HeartbeatRequest,
    ReportPlaybackRequest,
    SkipPlaybackRequest,
    StartPlaybackRequest,
    heartbeat_playback,
    report_playback,
    skip_playback,
    start_playback,
)

router = APIRouter(prefix="/playback", tags=["playback"])


@router.post("/start", status_code=201)
def start(
    body: StartPlaybackRequest,
    listener_id: int = Depends(get_actor_id),
    session: Session = Depends(get_session),
):
    return start_playback(session, listener_id, body)


@router.post("/heartbeat")
def heartbeat(
    body: HeartbeatRequest,
    listener_id: int = Depends(get_actor_id),
    session: Session = Depends(get_session),
):
    return heartbeat_playback(session, listener_id, body)


@router.post("/report")
def report(
    body: ReportPlaybackRequest,
    listener_id: int = Depends(get_actor_id),
    session: Session = Depends(get_session),
):
    return report_playback(session, listener_id, body)


@router.post("/skip")
def skip(
    body: SkipPlaybackRequest,
    listener_id: int = Depends(get_actor_id),
    session: Session = Depends(get_session),
):
    return skip_playback(session, listener_id, body)
