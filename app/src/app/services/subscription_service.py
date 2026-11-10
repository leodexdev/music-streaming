from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

Mode = Literal["real", "naive"]


def join_subscription(session: Session, listener_id: int, code: str, mode: Mode) -> dict:
    try:
        result = _join(session, listener_id, code, mode)
        session.commit()
        return result
    except IntegrityError as exc:
        session.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "23514":   # trigger: subscription is full
            raise HTTPException(409, "Subscription is full")
        if sqlstate == "23505":   # partial unique index: already a current member
            raise HTTPException(409, "Listener is already a member of a current subscription")
        raise
    except HTTPException:
        session.rollback()
        raise


def _join(session: Session, listener_id: int, code: str, mode: Mode) -> dict:
    # 1. the invite code (parameterised)
    invite = session.execute(
        text("SELECT subscription_id, expires_at FROM invite_code WHERE code = :code"),
        {"code": code},
    ).one_or_none()
    if invite is None:
        raise HTTPException(404, "Invite code not found")
    if invite.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(410, "Invite code expired")
    sub_id = invite.subscription_id

    # 2. the subscription. REAL mode locks the row, so concurrent joins queue here.
    lock = "FOR UPDATE OF s" if mode == "real" else ""
    sub = session.execute(
        text(
            f"""SELECT s.id, s.status, p.max_members
                FROM subscription s JOIN plan p ON p.id = s.plan_id
                WHERE s.id = :sid {lock}"""   # `lock` is a constant above, never request input
        ),
        {"sid": sub_id},
    ).one()
    if sub.status not in ("active", "past_due"):
        raise HTTPException(409, "Subscription is not current")

    # 3. already a member of a current subscription?
    already = session.execute(
        text("SELECT 1 FROM subscription_member WHERE listener_id = :l AND left_at IS NULL"),
        {"l": listener_id},
    ).first()
    if already:
        raise HTTPException(409, "Listener is already a member of a current subscription")

    # 4. count current members (READ COMMITTED: after the lock this sees committed joins)
    members = session.execute(
        text("SELECT count(*) FROM subscription_member WHERE subscription_id = :sid AND left_at IS NULL"),
        {"sid": sub_id},
    ).scalar_one()
    if members >= sub.max_members:
        raise HTTPException(409, "Subscription is full")

    if mode == "naive":
        # widen the check-then-insert window so the race shows up reliably
        session.execute(text("SELECT pg_sleep(0.05)"))

    # 5. insert. In real mode the database trigger is the last guarantee.
    session.execute(
        text("INSERT INTO subscription_member (subscription_id, listener_id) VALUES (:sid, :l)"),
        {"sid": sub_id, "l": listener_id},
    )
    return {"subscription_id": sub_id, "listener_id": listener_id}