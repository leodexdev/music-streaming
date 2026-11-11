#!/usr/bin/env python3
"""Upsert deterministic playback-event fixtures in MongoDB."""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, ReplaceOne

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261111
EVENT_COUNT = 50_000
BATCH_SIZE = 5_000
LISTENER_COUNT = 100_000
TRACK_COUNT = 300_000
DEVICES = ("mobile", "desktop", "web", "speaker", "car")
EVENT_TYPES = ("start", "heartbeat", "pause", "seek", "skip", "end")


def event_documents(now: datetime):
    rng = random.Random(SEED + 5)
    window_seconds = 30 * 24 * 60 * 60
    for event_number in range(EVENT_COUNT):
        listener_id = rng.randrange(1, LISTENER_COUNT + 1)
        yield {
            "_id": f"seed-task-1.9-{event_number + 1:06d}",
            "listener_id": listener_id,
            "device_id": f"device-{listener_id:06d}-{event_number % 3 + 1}",
            "device_type": DEVICES[rng.randrange(len(DEVICES))],
            "track_id": rng.randrange(1, TRACK_COUNT + 1),
            "event_type": EVENT_TYPES[rng.randrange(len(EVENT_TYPES))],
            "position_seconds": rng.randrange(0, 3_601),
            "ts": now - timedelta(seconds=rng.randrange(window_seconds)),
        }


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    load_dotenv(ROOT / ".env")
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        print("Missing MONGO_URL in the environment or .env", file=sys.stderr)
        return 1

    client = MongoClient(mongo_url)
    started = time.monotonic()
    try:
        client.admin.command("ping")
        db = client.get_default_database(default="music")
        collection = db["playback_events"]
        now = datetime.now(timezone.utc)
        batch = []
        written = 0
        for document in event_documents(now):
            batch.append(
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
            )
            if len(batch) == BATCH_SIZE:
                collection.bulk_write(batch, ordered=False)
                written += len(batch)
                print(f"  playback_events: upserted {written:,}/{EVENT_COUNT:,}", flush=True)
                batch.clear()
        if batch:
            collection.bulk_write(batch, ordered=False)
            written += len(batch)
        recent_count = collection.count_documents(
            {"_id": {"$regex": "^seed-task-1\\.9-"}, "ts": {"$gte": now - timedelta(days=30)}}
        )
        if recent_count < EVENT_COUNT:
            raise RuntimeError(
                f"expected at least {EVENT_COUNT:,} seeded events in the last 30 days, "
                f"found {recent_count:,}"
            )
        print(
            f"MongoDB playback events ready: {recent_count:,} seeded events "
            f"within 30 days ({time.monotonic() - started:.1f}s).",
            flush=True,
        )
    except Exception as exc:
        print(f"MongoDB event seeding failed: {exc}", file=sys.stderr)
        raise
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
