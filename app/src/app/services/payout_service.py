from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

LISBON = ZoneInfo("Europe/Lisbon")
CENT = Decimal("0.01")

MONTHLY_ARTIST_STREAMS = text(
    """
    WITH monthly_tracks AS (
        SELECT track_id, count(*) AS streams
        FROM play
        WHERE started_at >= :start AND started_at < :end
          AND seconds_played >= 30
        GROUP BY track_id
    ),
    main_artist_counts AS (
        SELECT track_id, count(*) AS artist_count
        FROM track_artist
        WHERE role = 'main'
        GROUP BY track_id
    )
    SELECT ta.artist_id,
           coalesce(sum(mt.streams), 0)::bigint AS stream_count,
           coalesce(
               sum(mt.streams::numeric / mac.artist_count),
               0
           ) AS credited_streams
    FROM track_artist AS ta
    JOIN main_artist_counts AS mac ON mac.track_id = ta.track_id
    LEFT JOIN monthly_tracks AS mt ON mt.track_id = ta.track_id
    WHERE ta.role = 'main'
    GROUP BY ta.artist_id
    ORDER BY ta.artist_id
    """
)

INSERT_PAYOUTS = text(
    """
    INSERT INTO payout (artist_id, month, rate_per_stream, stream_count, amount, status)
    VALUES (:artist_id, :month, :rate_per_stream, :stream_count, :amount, 'computed')
    """
)


def payout_rows(artist_streams, month: date, rate_per_stream: Decimal) -> list[dict]:
    rows = []
    for row in artist_streams:
        credited_streams = Decimal(str(row.credited_streams))
        amount = (rate_per_stream * credited_streams).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        rows.append(
            {
                "artist_id": int(row.artist_id),
                "month": month,
                "rate_per_stream": rate_per_stream,
                "stream_count": int(row.stream_count),
                "amount": amount,
            }
        )
    return rows


def close_month(session: Session, month: date, rate_per_stream: Decimal) -> dict:
    if month.day != 1:
        raise HTTPException(422, "Month must be the first day of a month")
    if rate_per_stream < 0:
        raise HTTPException(422, "Rate per stream cannot be negative")

    start = datetime.combine(month, time.min, LISBON)
    next_month = month.replace(day=28) + timedelta(days=4)
    end_date = next_month.replace(day=1)
    end = datetime.combine(end_date, time.min, LISBON)

    try:
        existing = session.execute(
            text("SELECT 1 FROM payout WHERE month = :month LIMIT 1"),
            {"month": month},
        ).first()
        if existing:
            raise HTTPException(409, f"Payouts for {month:%Y-%m} are already closed")

        artists = session.execute(
            MONTHLY_ARTIST_STREAMS,
            {"start": start, "end": end},
        )
        rows = payout_rows(artists, month, rate_per_stream)
        if not rows:
            raise HTTPException(409, "No main artists are available to close payouts")
        session.execute(INSERT_PAYOUTS, rows)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, f"Payouts for {month:%Y-%m} are already closed") from exc
        raise
    except HTTPException:
        session.rollback()
        raise

    total_amount = sum((row["amount"] for row in rows), Decimal("0.00"))
    return {
        "month": month.strftime("%Y-%m"),
        "payouts_created": len(rows),
        "total_amount": total_amount,
    }
