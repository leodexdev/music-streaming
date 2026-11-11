from typing import Literal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

Mode = Literal["real", "naive"]
MAX_TRACKS = 500


def _run(session: Session, work):
    """One transaction: commit at the end, translate database errors to 4xx."""
    try:
        result = work()
        session.commit()   # the deferred unique constraint is checked here
        return result
    except IntegrityError as exc:
        session.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "23514":   # CHECK: more than 500 tracks / position out of range
            raise HTTPException(409, "Playlist is full")
        if sqlstate == "23505":   # unique: two tracks in the same position
            raise HTTPException(409, "Position conflict")
        raise
    except HTTPException:
        session.rollback()
        raise


def _open_playlist(session: Session, playlist_id: int, actor_id: int, mode: Mode):
    """Read the playlist and check that the actor may edit it.
    REAL mode locks the row, so concurrent editors of the same playlist queue here."""
    lock = "FOR UPDATE" if mode == "real" else ""
    playlist = session.execute(
        text(
            f"""SELECT id, owner_id, is_collaborative, track_count
                FROM playlist WHERE id = :p {lock}"""   # `lock` is a constant, never request input
        ),
        {"p": playlist_id},
    ).one_or_none()
    if playlist is None:
        raise HTTPException(404, "Playlist not found")
    if playlist.owner_id != actor_id:
        is_collaborator = playlist.is_collaborative and session.execute(
            text("SELECT 1 FROM playlist_collaborator WHERE playlist_id = :p AND listener_id = :l"),
            {"p": playlist_id, "l": actor_id},
        ).first()
        if not is_collaborator:
            raise HTTPException(403, "Only the owner or a collaborator can edit this playlist")
    return playlist


def _log(session, playlist_id, actor_id, action, track_id, position, new_position=None):
    session.execute(
        text(
            """INSERT INTO playlist_change (playlist_id, actor_id, action, track_id, position, new_position)
               VALUES (:p, :a, :act, :t, :pos, :new)"""
        ),
        {"p": playlist_id, "a": actor_id, "act": action, "t": track_id, "pos": position, "new": new_position},
    )
    session.execute(text("UPDATE playlist SET updated_at = now() WHERE id = :p"), {"p": playlist_id})


def add_track(session: Session, playlist_id: int, actor_id: int, track_id: int, position: int, mode: Mode) -> dict:
    def work():
        playlist = _open_playlist(session, playlist_id, actor_id, mode)
        n = playlist.track_count
        if position < 1 or position > n + 1:
            raise HTTPException(422, f"Position must be between 1 and {n + 1}")
        if n >= MAX_TRACKS:
            raise HTTPException(409, "Playlist is full")
        if session.execute(text("SELECT 1 FROM track WHERE id = :t"), {"t": track_id}).first() is None:
            raise HTTPException(404, "Track not found")

        if mode == "naive":
            # widen the check-then-write window so the race shows up reliably
            session.execute(text("SELECT pg_sleep(0.05)"))

        session.execute(
            text("UPDATE playlist_track SET position = position + 1 WHERE playlist_id = :p AND position >= :pos"),
            {"p": playlist_id, "pos": position},
        )
        session.execute(
            text(
                """INSERT INTO playlist_track (playlist_id, position, track_id, added_by)
                   VALUES (:p, :pos, :t, :a)"""
            ),
            {"p": playlist_id, "pos": position, "t": track_id, "a": actor_id},
        )
        _log(session, playlist_id, actor_id, "add", track_id, position)
        return {"playlist_id": playlist_id, "track_id": track_id, "position": position}

    return _run(session, work)


def remove_track(session: Session, playlist_id: int, actor_id: int, position: int, mode: Mode) -> dict:
    def work():
        _open_playlist(session, playlist_id, actor_id, mode)
        row = session.execute(
            text("SELECT id, track_id FROM playlist_track WHERE playlist_id = :p AND position = :pos"),
            {"p": playlist_id, "pos": position},
        ).one_or_none()
        if row is None:
            raise HTTPException(404, "No track at that position")
        session.execute(text("DELETE FROM playlist_track WHERE id = :id"), {"id": row.id})
        session.execute(
            text("UPDATE playlist_track SET position = position - 1 WHERE playlist_id = :p AND position > :pos"),
            {"p": playlist_id, "pos": position},
        )
        _log(session, playlist_id, actor_id, "remove", row.track_id, position)
        return {"playlist_id": playlist_id, "removed_position": position}

    return _run(session, work)


def move_track(session: Session, playlist_id: int, actor_id: int, position: int, to_position: int, mode: Mode) -> dict:
    def work():
        playlist = _open_playlist(session, playlist_id, actor_id, mode)
        if to_position < 1 or to_position > playlist.track_count:
            raise HTTPException(422, f"Position must be between 1 and {playlist.track_count}")
        row = session.execute(
            text("SELECT id, track_id FROM playlist_track WHERE playlist_id = :p AND position = :pos"),
            {"p": playlist_id, "pos": position},
        ).one_or_none()
        if row is None:
            raise HTTPException(404, "No track at that position")
        if position == to_position:
            return {"playlist_id": playlist_id, "position": to_position}

        if position < to_position:   # the tracks in between move one up
            session.execute(
                text(
                    """UPDATE playlist_track SET position = position - 1
                       WHERE playlist_id = :p AND position > :a AND position <= :b"""
                ),
                {"p": playlist_id, "a": position, "b": to_position},
            )
        else:                        # the tracks in between move one down
            session.execute(
                text(
                    """UPDATE playlist_track SET position = position + 1
                       WHERE playlist_id = :p AND position >= :b AND position < :a"""
                ),
                {"p": playlist_id, "a": position, "b": to_position},
            )
        session.execute(
            text("UPDATE playlist_track SET position = :b WHERE id = :id"),
            {"b": to_position, "id": row.id},
        )
        _log(session, playlist_id, actor_id, "move", row.track_id, position, to_position)
        return {"playlist_id": playlist_id, "position": to_position}

    return _run(session, work)