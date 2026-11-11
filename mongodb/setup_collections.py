import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_ROOT_URL") or os.getenv("MONGO_URL")
DB_NAME = "music"

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
                "ts"
            ],
            "properties": {
                "listener_id": {
                    "bsonType": "long"
                },
                "device_id": {
                    "bsonType": "string"
                },
                "device_type": {
                    "enum": ["mobile", "desktop", "web", "speaker", "car"]
                },
                "track_id": {
                    "bsonType": "long"
                },
                "event_type": {
                    "enum": ["start", "heartbeat", "pause", "seek", "skip", "end"]
                },
                "position_seconds": {
                    "bsonType": ["int", "long"],
                    "minimum": 0
                },
                "ts": {
                    "bsonType": "date"
                }
            }
        }
    }

    collection_name = "playback_events"

    if collection_name in db.list_collection_names():
        print(f"Collection '{collection_name}' already exists. Updating validator...")
        db.command({
            "collMod": collection_name,
            "validator": playback_schema,
            "validationLevel": "strict",
            "validationAction": "error"
        })
    else:
        print(f"Creating collection '{collection_name}' with strict schema validation...")
        db.create_collection(
            collection_name,
            validator=playback_schema,
            validationLevel="strict",
            validationAction="error"
        )

    print("Creating indexes on playback_events collection...")
    
    db[collection_name].create_index(
        [("ts", 1)],
        expireAfterSeconds=2592000,
        name="ttl_playback_30days"
    )

    db[collection_name].create_index(
        [("listener_id", 1), ("ts", -1)],
        name="listener_events_idx"
    )

    print("MongoDB setup completed successfully!")

if __name__ == "__main__":
    setup_mongodb()