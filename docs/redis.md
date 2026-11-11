# Redis

This project uses Redis for ephemeral state and short-lived counters that must be fast, atomic, and easy to expire.

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

Skip counters and active-device keys are ephemeral. The charts, daily stream
counters and last-play lists below are derived from PostgreSQL, which remains
the source of truth.

## Derived keys rebuilt from PostgreSQL

`redis/rebuild.py` reads the `play` table with the read-only PostgreSQL role.
Streams are plays with `seconds_played >= 30`; day boundaries use
`Europe/Lisbon`. Run `uv run --project app python redis/rebuild.py` to rebuild
these keys. It removes only the `charts:*`, `streams:*` and `last50:*` key
patterns; it does not run `FLUSHALL`.

| Key pattern | Structure and example | TTL and class | Commands |
|---|---|---|---|
| `charts:{YYYYMMDD}:global` | Sorted set; member is a track ID and score is its stream count. Example: `charts:20261111:global` contains `{"1204": 82}`. | Current-day chart expires at the next Lisbon midnight; previous-day chart expires after 7 days. **Derived.** The rebuild uses `ZADD` and `EXPIRE` in one `MULTI/EXEC`. | Rebuild: `ZADD`, `EXPIRE`; read: `ZREVRANGE key 0 49 WITHSCORES`. |
| `charts:{YYYYMMDD}:country:{country}` | Same sorted-set shape, limited to a country. Example: `charts:20261111:country:PT`. | Same as global chart. **Derived.** | Rebuild: `ZADD`, `EXPIRE`; read: `ZREVRANGE key 0 49 WITHSCORES`. |
| `streams:{YYYYMMDD}:track:{track_id}` | String containing today's stream count. Example: `streams:20261111:track:1204` has value `82`. | Expires at the next Lisbon midnight. `SET ... EX` writes value and TTL atomically. **Derived.** | Rebuild: `SET key value EX seconds`; read: `GET`. |
| `last50:{listener_id}` | List of track IDs, newest first. Example: `last50:777` might contain `["1204", "310", "1204"]`. | No TTL; the bounded list can be rebuilt from play history. **Derived.** | Rebuild: transactional `DEL` + `RPUSH`; read: `LRANGE key 0 49`. |

Charts contain at most 50 tracks, ordered by stream count with track ID as the
tie-breaker. Daily stream counters are created only for tracks with one or more
streams. Last-play lists include short plays, since they represent the last
tracks played, not only qualifying streams.
