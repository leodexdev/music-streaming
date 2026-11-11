import os

import redis
from dotenv import load_dotenv

from active_device import heartbeat, start_on_device
from skips import try_skip

load_dotenv()

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://:change-me-redis@127.0.0.1:6379/0")
)


def check_and_increment_skip(listener_id: int, max_skips: int = 6) -> bool:
    return try_skip(redis_client, listener_id, max_skips=max_skips, ttl_seconds=3600)


def register_device_heartbeat(listener_id: int, device_id: str, ttl_seconds: int = 60) -> bool:
    return heartbeat(redis_client, listener_id, device_id, ttl_seconds=ttl_seconds)


def start_device(listener_id: int, device_id: str, ttl_seconds: int = 60) -> bool:
    return start_on_device(redis_client, listener_id, device_id, ttl_seconds=ttl_seconds)
