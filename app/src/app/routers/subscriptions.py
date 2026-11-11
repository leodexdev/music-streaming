from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_session
from app.deps import get_actor_id
from app.services.subscription_service import join_subscription

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class JoinRequest(BaseModel):
    invite_code: str


@router.post("/join", status_code=201)
def join(
    body: JoinRequest,
    mode: Literal["real", "naive"] = "real",
    listener_id: int = Depends(get_actor_id),
    session: Session = Depends(get_session),
):
    return join_subscription(session, listener_id, body.invite_code, mode)