# MongoDB Architecture & Playback Events

## Overview
MongoDB is utilized for storing high-frequency event streams, specifically playback events (`playback_events`), leveraging strict JSON schema validation and automated TTL expiration.

## Collection: `playback_events`
- **Database:** `music` (configured via `MONGO_URL`)
- **Validation:** Enforced via MongoDB `$jsonSchema` validator ensuring type safety, required fields, and valid enum states for player actions.

## Indexes
1. **`ttl_playback_30days`**: 
   - Field: `ts` (ascending)
   - Purpose: Automatic document expiration after 30 days (`expireAfterSeconds: 2592000`).
2. **`listener_events_idx`**: 
   - Fields: `listener_id` (ascending), `ts` (descending)
   - Purpose: Optimized query performance for retrieving a listener's recent playback history in chronological order.

## Setup & Verification
To initialize or update the collection schema and indexes:
```bash
uv run python mongodb/setup_collections.py