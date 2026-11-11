import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_ROOT_URL") or os.getenv("MONGO_URL")
DB_NAME = "music"


def _create_or_update_collection(db, name: str, validator: dict):
    if name in db.list_collection_names():
        db.command({
            "collMod": name,
            "validator": validator,
            "validationLevel": "strict",
            "validationAction": "error",
        })
    else:
        db.create_collection(
            name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )


def setup_mongodb():
    print(f"Connecting to MongoDB to setup database: {DB_NAME}...")
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    playback_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "listener_id",
                "device_id",
                "device_type",
                "track_id",
                "event_type",
                "position_seconds",
                "ts",
            ],
            "properties": {
                "listener_id": {"bsonType": ["int", "long"]},
                "device_id": {"bsonType": "string"},
                "device_type": {"enum": ["mobile", "desktop", "web", "speaker", "car"]},
                "track_id": {"bsonType": ["int", "long"]},
                "event_type": {"enum": ["start", "heartbeat", "pause", "seek", "skip", "end"]},
                "position_seconds": {"bsonType": ["int", "long"], "minimum": 0},
                "ts": {"bsonType": "date"},
            },
        }
    }

    _create_or_update_collection(db, "playback_events", playback_schema)

    playback = db["playback_events"]
    playback.create_index([("ts", 1)], expireAfterSeconds=2592000, name="ttl_playback_30days")
    playback.create_index([("listener_id", 1), ("ts", -1)], name="listener_events_idx")

    track_details_schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["track_id", "lyrics", "language", "bpm", "key", "credits", "blocked_countries"],
            "properties": {
                "track_id": {"bsonType": ["int", "long"]},
                "lyrics": {"bsonType": "string"},
                "language": {"bsonType": "string"},
                "bpm": {"bsonType": ["int", "double"]},
                "key": {"bsonType": "string"},
                "credits": {"bsonType": "array"},
                "blocked_countries": {"bsonType": "array"},
            },
        }
    }
    _create_or_update_collection(db, "track_details", track_details_schema)
    db["track_details"].create_index([("track_id", 1)], unique=True, name="track_details_track_idx")

    print("MongoDB setup completed successfully!")


if __name__ == "__main__":
    setup_mongodb()