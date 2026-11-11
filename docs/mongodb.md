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

Example:

```json
{
  "listener_id": 777,
  "device_id": "phone-1",
  "device_type": "mobile",
  "track_id": 1204,
  "event_type": "heartbeat",
  "position_seconds": 30,
  "ts": "2026-11-11T20:30:00Z"
}
```

Listener and track IDs are references to PostgreSQL entities; their complete
records are not embedded because they are stable relational data and can
change independently of an event. Events are append-only, and their retention
is bounded by the TTL index.

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
`track_id` references PostgreSQL; the variable fields are embedded in the
document because they are read together. Example:

```json
{
  "track_id": 1204,
  "lyrics": "...",
  "language": "en",
  "bpm": 120,
  "key": "C major",
  "credits": [{"role": "producer", "name": "Example"}],
  "blocked_countries": ["XX"]
}
```

This collection is a place for optional metadata; the current API does not
read or write it.

## Derived report collections

`mongodb/export.py` rebuilds three collections from PostgreSQL:

- `listener_month_stats`: one document per listener and Lisbon-local month,
  embedding monthly totals, tracks, and daily activity so a yearly report can
  read a small number of documents.
- `artist_country_month`: one document per artist, country, and month, with
  the artist ID/name and stream count needed by the artist report.
- `genre_country_month`: one document per genre, country, and month, with its
  stream count.

These are derived read models, not the source of truth. They are regenerated
from PostgreSQL after seeding or when report data must be refreshed. The event
and report data reference relational entities by ID rather than embedding
mutable listener/catalogue records.

**Validation status:** `mongodb/setup_collections.py` creates strict validators
for `playback_events` and `track_details`. The current export does not install
validators for the three report collections; this remains a setup gap.

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

Measured on the local seeded event collection (the sample listener had two
events):

| Plan | Winning stages | Returned | Documents examined | Keys examined |
|---|---|---:|---:|---:|
| Collection scan, forced with `hint({$natural: 1})` | `COLLSCAN` + `SORT` | 2 | 49,910 | 0 |
| `listener_events_idx` | `IXSCAN` + `FETCH` + `LIMIT` | 2 | 2 | 2 |

The indexed plan examined only the matching listener's two documents and
avoided the in-memory sort. Elapsed times were 8 ms without the index and
under 1 ms with it in this local run; timings vary by machine and cache state.

## Role in the architecture

MongoDB is used for event streams and read-optimized derived collections, while PostgreSQL remains the transactional source of truth for all business rules and invariants.

## F8 report API

The API reads the report collections directly; these requests do not query
PostgreSQL:

- `GET /reports/listeners/{listener_id}/yearly-summary/{year}` combines that
  listener's monthly documents into yearly totals, top tracks and artists,
  top genre, and peak listening day.
- `GET /reports/artists/{artist_id}/streams?country=PT&month=2026-10` reads
  the artist's country/month stream rows. Country and month filters are optional.
- `GET /reports/genres/top?country=PT&month=2026-10` returns the top five
  genres for that country and month.

The yearly endpoint uses `listener_month_stats`; the artist and genre endpoints
use `artist_country_month` and `genre_country_month`, respectively. Run
`uv run --project app python mongodb/export.py` after seeding PostgreSQL to
refresh these collections.
# MongoDB Aggregation Pipelines

`mongodb/export.py` reads PostgreSQL plays from the last 12 calendar months and
rebuilds the derived report collections. Month and day buckets use
`Europe/Lisbon`; a stream is a play with at least 30 seconds played. The
examples below are illustrative and are not output from the currently empty
local seed.

The pipelines operate on the export collections, not on `playback_events`.
`listener_month_stats` contains one document per listener and month, with
monthly totals, track details and daily activity. Each daily activity item
contains `day`, `country`, `device_type`, `plays`, `streams` and `seconds`.
`artist_country_month` contains artist, country, month and stream totals.
`genre_country_month` contains genre, country, month and stream totals.

Run a pipeline by passing its JSON array to `aggregate()` on the collection
listed below. The complete pipeline arrays are saved in the linked JSON files.

## 1. Yearly Listener Summary ("Your Year in Music")

### Question

For each listener and year represented in the export, what were their minutes
listened, top five tracks, top five artists, top genre, and day with the most
listening time?

### Pipeline

[`mongodb/pipelines/yearly_listener_summary.json`](../mongodb/pipelines/yearly_listener_summary.json)
is the complete aggregation array for `listener_month_stats`. It derives the
year from the Lisbon-local `month`, then uses `$facet` to calculate yearly
totals, rank tracks and artists by streams, rank genres by streams, and find
the day with the most listening seconds. Artist IDs and names are paired from
the parallel arrays exported for each track. Ties are resolved by stable
IDs/names or day to make results deterministic.

The rolling export only includes the last 12 calendar months, so a calendar
year in this report may be partial if all of its months are not present in the
export.

### Sample Output

```json
{
  "listener_id": 42,
  "year": 2026,
  "plays": 210,
  "streams": 178,
  "total_minutes": 735.5,
  "top_tracks": [
    {
      "track_id": 1001,
      "title": "Night Walk",
      "streams": 20,
      "seconds": 3600
    }
  ],
  "top_artists": [
    {
      "artist_id": 9,
      "artist": "Mira",
      "streams": 44
    }
  ],
  "top_genre": "Electronic",
  "peak_day": "2026-08-14",
  "peak_day_seconds": 7200
}
```

## 2. Artist Streams by Country and Month

### Question

How many streams did each artist receive in each country and month?

### Pipeline

[`mongodb/pipelines/artist_streams_by_country_month.json`](../mongodb/pipelines/artist_streams_by_country_month.json)
is the complete aggregation array for `artist_country_month`. It groups the
exported artist-country-month rows, sums their stream counts, and orders the
result by month, country and stream count. The export counts a stream for each
main artist on a track.

### Sample Output

```json
{
  "artist_id": 9,
  "artist_name": "Mira",
  "country": "PT",
  "month": "2026-10",
  "stream_count": 482
}
```

## 3. Top Genres by Country and Month

### Question

Which five genres had the most streams in each country and month?

### Pipeline

[`mongodb/pipelines/top_genres_by_country_month.json`](../mongodb/pipelines/top_genres_by_country_month.json)
is the complete aggregation array for `genre_country_month`. It groups
exported genre-country-month rows, sorts genres by stream count (with genre
name as a tie-breaker), and returns the top five for each country and month.
The exported collection has no listener IDs, so it cannot produce a distinct
listener count.

### Sample Output

```json
{
  "country": "PT",
  "month": "2026-10",
  "top_genres": [
    {
      "genre": "Pop",
      "stream_count": 1250
    },
    {
      "genre": "Electronic",
      "stream_count": 980
    }
  ]
}
```
