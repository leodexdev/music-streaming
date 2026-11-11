from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.deps import get_actor_id
from app.services import playlist_service

router = APIRouter(prefix="/playlists", tags=["playlists"])
Mode = Literal["real", "naive"]


class AddTrack(BaseModel):
    track_id: int
    position: int


class MoveTrack(BaseModel):
    to_position: int


@router.post("/{playlist_id}/tracks", status_code=201)
def add_track(playlist_id: int, body: AddTrack, mode: Mode = "real",
              actor_id: int = Depends(get_actor_id), session: Session = Depends(get_session)):
    return playlist_service.add_track(session, playlist_id, actor_id, body.track_id, body.position, mode)


@router.delete("/{playlist_id}/tracks/{position}")
def remove_track(playlist_id: int, position: int, mode: Mode = "real",
                 actor_id: int = Depends(get_actor_id), session: Session = Depends(get_session)):
    return playlist_service.remove_track(session, playlist_id, actor_id, position, mode)


@router.patch("/{playlist_id}/tracks/{position}")
def move_track(playlist_id: int, position: int, body: MoveTrack, mode: Mode = "real",
               actor_id: int = Depends(get_actor_id), session: Session = Depends(get_session)):
    return playlist_service.move_track(session, playlist_id, actor_id, position, body.to_position, mode)