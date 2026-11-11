from __future__ import annotations

import redis

from keys import skip_key


def try_skip(r: redis.Redis, listener_id: int, max_skips: int = 6, ttl_seconds: int = 3600) -> bool:
    """Allow up to 6 skips in one hour for a free listener.

    Redis pattern:
      SET key 0 EX 3600 NX
      INCR key
    """
    key = skip_key(listener_id)
    pipe = r.pipeline(transaction=True)
    pipe.set(key, 0, ex=ttl_seconds, nx=True)
    pipe.incr(key)
    set_result, count = pipe.execute()

    current = int(count)
    if current > max_skips:
        return False
    return True
