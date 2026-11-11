from __future__ import annotations

import redis

from keys import active_device_key


def start_on_device(r: redis.Redis, listener_id: int, device_id: str, ttl_seconds: int = 60) -> bool:
    key = active_device_key(listener_id)
    r.set(key, device_id, ex=ttl_seconds)
    return True


def heartbeat(r: redis.Redis, listener_id: int, device_id: str, ttl_seconds: int = 60) -> bool:
    """Atomically renew the current device lock only if the current device matches."""
    key = active_device_key(listener_id)

    while True:
        try:
            with r.pipeline() as pipe:
                pipe.watch(key)
                current = pipe.get(key)

                current_device = current.decode("utf-8") if isinstance(current, bytes) else current
                if current_device is None or current_device == device_id:
                    pipe.multi()
                    pipe.set(key, device_id, ex=ttl_seconds)
                    pipe.execute()
                    return True

                return False
        except redis.WatchError:
            continue
