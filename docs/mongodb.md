# MongoDB

This project uses MongoDB for append-only playback events and derived read models that do not need strict relational guarantees.

## Collection: `playback_events`

Database: `music` (configured via `MONGO_ROOT_URL` or `MONGO_URL`).

Validation is strict and enforced with `$jsonSchema`.

Required fields:
- `listener_id`: integer/long
- `device_id`: string
- `device_type`: enum (`mobile`, `desktop`, `web`, `speaker`, `car`)
- `track_id`: integer/long
- `event_type`: enum (`start`, `heartbeat`, `pause`, `seek`, `skip`, `end`)
- `position_seconds`: integer/long, minimum 0
- `ts`: date

## Indexes

1. TTL on `ts` with `expireAfterSeconds: 2592000`
   - Purpose: documents expire after 30 days.
2. Compound index `{listener_id: 1, ts: -1}`
   - Purpose: fetch a listener's recent playback history ordered by newest first.

## track_details collection

The project also defines a `track_details` collection as the place for variable track metadata that does not belong in PostgreSQL, for example:
- lyrics
- language
- BPM
- key
- credits
- blocked countries

This collection keeps one document per `track_id` using a unique index on `track_id`.

## Setup command

```bash
cd /workspaces/music-streaming
uv run python mongodb/setup_collections.py
```

## Query-plan evidence

Example query:

```javascript
db.playback_events.find({ listener_id: 777 }).sort({ ts: -1 }).limit(20)
```

This should be measured with `explain("executionStats")` before and after the index is created. The index matters because the app usually reads playback events by listener and time window.

## Role in the architecture

MongoDB is used for event streams and read-optimized derived collections, while PostgreSQL remains the transactional source of truth for all business rules and invariants.
