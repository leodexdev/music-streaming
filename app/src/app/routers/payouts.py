from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_session
from app.services.payout_service import close_month

router = APIRouter(prefix="/payouts", tags=["payouts"])


class CloseMonthRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    rate_per_stream: Decimal = Field(ge=0, max_digits=10, decimal_places=6)


@router.post("/close", status_code=201)
def close_payout_month(
    body: CloseMonthRequest,
    session: Session = Depends(get_session),
):
    try:
        month = date.fromisoformat(f"{body.month}-01")
    except ValueError as exc:
        raise HTTPException(422, "Month must use YYYY-MM format") from exc
    return close_month(session, month, body.rate_per_stream)
