# Redis

This project uses Redis for ephemeral state and short-lived counters that must be fast, atomic, and easy to expire.

## Current status

The Tiago-side implementation is in place for the required Redis rules:

- key builders in `redis/keys.py`
- skip counter logic in `redis/skips.py`
- single active device tracking in `redis/active_device.py`
- compatibility wrappers in `redis/cache_service.py`

The key patterns currently used by the app are consistent with the task brief: `skips:{listener_id}:{YYYYMMDDHH}` and `active_device:{listener_id}`.

## Key conventions

All keys follow a single naming scheme so the team can reason about them and reuse the same pattern everywhere.

- `skips:{listener_id}:{YYYYMMDDHH}`
  - Stores the number of skips for a free listener in the current hour.
  - Example: `skips:777:2026111116`
  - TTL: 3600 seconds
  - Reason: limit free listeners to 6 skips per hour before a 409 is returned.

- `active_device:{listener_id}`
  - Stores the current active device for a listener while playback is in progress.
  - Example: `active_device:777 -> phone_1`
  - TTL: 60 seconds
  - Reason: enforce a single active device at a time and refuse non-active devices with 409.

## Skip logic

The skip counter is controlled by a Redis pipeline with atomic writes:

```python
pipe = r.pipeline(transaction=True)
pipe.set(key, 0, ex=3600, nx=True)
pipe.incr(key)
set_result, count = pipe.execute()
```

Rules:
- The first request creates the counter and sets a 1-hour TTL.
- Each subsequent skip increments the counter.
- If the value is `<= 6`, the skip is allowed.
- On the 7th skip, the app should return `409 Conflict` and the track keeps playing.
- This applies only to free listeners.

## Device logic

The active device key is used to ensure only one device can own playback at a time.

- `start_on_device(listener_id, device_id)` sets the current device with TTL 60 seconds.
- `heartbeat(listener_id, device_id)` uses `WATCH` and `MULTI` to atomically compare the existing device and renew the same lock.
- If the stored device differs from the caller, the operation is refused with `409 Conflict`.
- A stale key expires automatically after 60 seconds.

## Example commands

```bash
redis-cli -u redis://:change-me-redis@127.0.0.1:6379/0 ping
redis-cli -u redis://:change-me-redis@127.0.0.1:6379/0 GET active_device:777
redis-cli -u redis://:change-me-redis@127.0.0.1:6379/0 TTL active_device:777
```

## Class

Redis data here is ephemeral by design: it is session-like, short-lived and not the source of truth for the relational database.
