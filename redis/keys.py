from __future__ import annotations

from datetime import datetime, timezone


def skip_key(listener_id: int, bucket: datetime | None = None) -> str:
    now = (bucket or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return f"skips:{listener_id}:{now.strftime('%Y%m%d%H')}"


def active_device_key(listener_id: int) -> str:
    return f"active_device:{listener_id}"
