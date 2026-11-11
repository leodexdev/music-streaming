# PostgreSQL Database Architecture & Technical Specification (`docs/postgres.md`)

This document details the relational schema, constraints, triggers, indexes, enforcement rules, deliberate denormalisation, and role privileges implemented for PostgreSQL in Project C (Music Streaming Platform).

---

## 1. Schema Overview & Relational Design (3rd Normal Form)

The primary database schema is designed in Third Normal Form (3NF) to eliminate data redundancy and ensure transactional integrity.

| Table Name | Description & Entity Rationale |
| :--- | :--- |
| `label` | Music record labels (`name`, `country`). |
| `artist` | Performing artists, linked to record labels via `label_id` (`ON DELETE SET NULL`). |
| `album` | Release entities (`album`, `single`, `ep`). |
| `album_artist` | N:N join table associating artists with albums, maintaining multi-artist order (`position >= 1`). |
| `track` | Audio tracks belonging to an album. Enforces explicit constraints on durations and ISRC format. |
| `track_artist` | N:N join table mapping artists to tracks with specific roles (`main`, `featured`, `producer`, `songwriter`). |
| `listener` | Registered user platform accounts containing authentication metadata and country information. |
| `plan` | Subscription plan offerings (`free`, `premium_individual`, `premium_duo`, `premium_family`) with member limits and prices. |
| `subscription` | Active or historic subscriptions owned by a listener, bound to a specific plan. |
| `subscription_member` | N:N association tracking listeners joining a shared family/duo subscription. |
| `invite_code` | Temporary invite tokens linking new members to an active subscription with explicit expiry checks (`expires_at > created_at`). |
| `play` | Append-only event/transaction log tracking stream play counts, listening durations, and device metadata. |
| `playlist` | User-created playlists tracking ownership, visibility (`public`, `private`), and a denormalised `track_count`. |
| `playlist_collaborator` | N:N join table granting collaborative edit rights to playlists. |
| `playlist_track` | N:N join table mapping tracks to playlists with explicit position ordering (`position BETWEEN 1 AND 500`). |

---

## 2. Advanced Integrity Constraints & Indexing Strategy

### A. Check Constraints & Data Types
* **Primary Keys:** Uses 64-bit integer identity columns (`sa.BigInteger`, `sa.Identity()`) across all primary entities.
* **Timestamps:** Uses timezone-aware timestamps (`TIMESTAMP WITH TIME ZONE`) for precise time-series logging (`joined_at`, `created_at`, `updated_at`, `expires_at`).
* **Format & Range Checks:**
  * `track.isrc`: Validated using POSIX regular expression matching (`CHECK (isrc ~ '^[A-Za-z0-9]{12}$')`).
  * `track.duration_seconds`: Enforces positive non-zero durations (`CHECK (duration_seconds > 0)`).
  * `plan.name` & `plan.monthly_price`: Restricted to valid plan tiers and non-negative pricing.
  * `play.device_type`: Restricted to valid platforms (`mobile`, `desktop`, `web`, `speaker`, `car`).

### B. Foreign Key Delete Cascades
* **`ON DELETE CASCADE`:** Applied to dependent entities that cannot exist without their parent (e.g., `album_artist` $\rightarrow$ `album`, `track` $\rightarrow$ `album`, `playlist_track` $\rightarrow$ `playlist`, `invite_code` $\rightarrow$ `subscription`).
* **`ON DELETE RESTRICT`:** Applied to core transactional entities to prevent accidental deletion of historical data (e.g., deleting a `listener` or `track` referenced in `play`, `subscription`, or `subscription_member`).
* **`ON DELETE SET NULL`:** Applied to optional metadata links (e.g., `artist.label_id`, `playlist_track.added_by`).

### C. Partial Unique Indexes & Deferred Constraints
1. **Single Active Subscription per Owner:**
   ```sql
   CREATE UNIQUE INDEX subscription_one_current_per_owner 
   ON subscription (owner_id) 
   WHERE status IN ('active', 'past_due');
   ```
2. **Single Active Membership per Listener:**
   ```sql
   CREATE UNIQUE INDEX member_one_current_per_listener 
   ON subscription_member (listener_id) 
   WHERE left_at IS NULL;
   ```
3. **Deferrable Playlist Track Positioning:**
   ```sql
   ALTER TABLE playlist_track 
   ADD CONSTRAINT playlist_track_pos_uq 
   UNIQUE (playlist_id, position) 
   DEFERRABLE INITIALLY DEFERRED;
   ```
   *Rationale:* Deferring unique position checks to transaction commit allows atomic reordering of playlist items (shifting positions) within a single transaction without triggering immediate unique key collision errors.

---

## 3. Concurrency Control & Database Triggers

### A. Subscription Member Capacity Enforcement (`enforce_max_members`)
To prevent over-subscribing shared plans (Family/Duo) during simultaneous HTTP requests, capacity checks are enforced directly at the database layer via a PL/pgSQL trigger function:

```sql
CREATE FUNCTION enforce_max_members() RETURNS trigger AS $$
DECLARE 
    max_allowed int; 
    current_count int;
BEGIN
    SELECT p.max_members INTO max_allowed
    FROM subscription s 
    JOIN plan p ON p.id = s.plan_id
    WHERE s.id = NEW.subscription_id
    FOR UPDATE OF s;

    SELECT count(*) INTO current_count 
    FROM subscription_member
    WHERE subscription_id = NEW.subscription_id AND left_at IS NULL;

    IF current_count >= max_allowed THEN
        RAISE EXCEPTION 'subscription is full' USING ERRCODE = '23514';
    END IF;
    
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER subscription_member_limit 
BEFORE INSERT ON subscription_member
FOR EACH ROW EXECUTE FUNCTION enforce_max_members();
```

### B. Deliberate Denormalisation & Automatic Counter Maintenance
* **Denormalised Attribute:** `playlist.track_count` (bounded between 0 and 500 via `CHECK (track_count BETWEEN 0 AND 500)`).
* **Architectural Rationale:** Calculating `COUNT(*)` over `playlist_track` on every playlist fetch creates significant overhead under heavy read traffic.
* **Maintenance Mechanism:** Maintained automatically via statement-level triggers utilizing transition tables.

---

## 4. Enforcement Layer Matrix

| Business Rule | Enforced By | Mechanism / Implementation |
| :--- | :--- | :--- |
| **Referential Integrity** | PostgreSQL | `FOREIGN KEY` with `RESTRICT` / `CASCADE` / `SET NULL` |
| **Active Subscription Uniqueness** | PostgreSQL | Partial Unique Index on `subscription(owner_id)` |
| **Plan Capacity Limits** | PostgreSQL | `BEFORE INSERT` Trigger with `FOR UPDATE` lock on `subscription` |
| **Playlist 500 Track Upper Bound** | PostgreSQL | `CHECK (track_count BETWEEN 0 AND 500)` + Statement Triggers |
| **Atomic Track Reordering** | PostgreSQL | `DEFERRABLE INITIALLY DEFERRED` Unique Constraint |
| **Invite Code Expiry (7-day TTL)** | PostgreSQL / FastAPI | `invite_code.expires_at` plus an API timestamp check; no Redis invite key is used |
| **Free Listener Skip Limits** | Redis / FastAPI | Atomic `redis-py` pipeline counters (`INCR` + `EXPIRE`) |
| **Single Active Device per Listener** | Redis / FastAPI | Heartbeat session keys in Redis (`SET ... EX 60`) |

---

## 5. Performance indexing and EXPLAIN evidence

The following plans were measured on the seeded local database (300,000 tracks
and 2,100,000 plays). For each “without index” measurement, the named index was
dropped inside a transaction and restored with `ROLLBACK`; no index was left
dropped. Timings are one local run and will vary by machine and cache state.

Queries measured:

```sql
SELECT id, started_at FROM play
WHERE listener_id = 1
ORDER BY started_at DESC LIMIT 10;

SELECT id, started_at FROM play
WHERE track_id = 1 AND started_at >= now() - interval '30 days';

SELECT id, title FROM track
WHERE title ILIKE '%beautiful%' LIMIT 20;
```

For the no-index measurements, the corresponding index was dropped and the
same query explained in a transaction, followed by `ROLLBACK`, for example:

```sql
BEGIN;
DROP INDEX play_listener_started_desc_idx;
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, started_at FROM play
WHERE listener_id = 1
ORDER BY started_at DESC LIMIT 10;
ROLLBACK;
```

| Query and index | With index | Without index |
|---|---|---|
| Listener 1's newest plays; `play_listener_started_desc_idx` | Index Scan, 10 rows, 0.118 ms, 13 buffers | Parallel Seq Scan + sort, 10 rows, 47.587 ms, 19,738 buffers |
| Track 1 plays in the last 30 days; `play_track_started_idx` | Index Scan, 125 rows, 0.336 ms, 128 buffers | Parallel Seq Scan, 125 rows, 42.045 ms, 19,664 buffers |
| Title contains “beautiful”; `track_title_trgm_idx` | Bitmap Index/Heap Scan, 20 returned, 1.984 ms, 39 buffers | Parallel Seq Scan, 20 returned, 5.986 ms, 61 buffers |

Example indexed plans:

```text
Index Scan using play_listener_started_desc_idx on play
  Index Cond: (listener_id = 1)
  Execution Time: 0.118 ms

Index Scan using play_track_started_idx on play
  Index Cond: ((track_id = 1) AND (started_at >= (now() - '30 days'::interval)))
  Execution Time: 0.336 ms

Bitmap Heap Scan on track
  Recheck Cond: (title ~~* '%beautiful%'::text)
  -> Bitmap Index Scan on track_title_trgm_idx
       Index Cond: (title ~~* '%beautiful%'::text)
  Execution Time: 1.984 ms
```

In this dataset the listener-history and track/month indexes avoided scanning
the full 2.1M-row play table. The trigram index also reduced buffers and
elapsed time for the title search.

---

## 6. Tiago Implementation Status and Validation Notes

The Tiago-side relational work is implemented around the core invariants of the platform:

- `0001_primary_tables.py` defines the relational schema, the partial unique indexes, the `subscription_member_limit` trigger, and the playlist denormalisation triggers.
- `0003_indexes.py` adds the query-specific index strategy for listener history, track stream history, and trigram matching on track titles.
- `app/src/app/services/subscription_service.py` and `app/src/app/services/playlist_service.py` enforce the business rules in transaction-safe code using `SELECT ... FOR UPDATE` when required.
- `app/src/app/services/playback_service.py` keeps the playback rules aligned with the Redis device/skip guard and records the playback events as required by the Mongo task.

### Validated concurrency check

The collaborative playlist scenario was executed in real mode with the project script and passed:

```text
Requests: 50 | accepted: 10 | refused: 40 | 5xx/errors: 0
Tracks in PostgreSQL: 500 (limit 500) | distinct positions: 500 | min: 1 | max: 500 | track_count: 500
Positions are exactly 1..500 with no duplicates: True -> rule HOLDS
```

This result confirms the playlist logic is holding the invariant under concurrent inserts while preserving the 500-track maximum and the no-gap/no-duplicate ordering rule.

## 7. Database roles and security model

The database uses three roles created by `scripts/setup.sh`:

1. **`music_owner`:** owns the schema and runs Alembic migrations.
2. **`music_app`:** used by the API; it receives only the table grants described
   by the migrations. It cannot run DDL or act as a superuser.
3. **`music_ro`:** read-only access for analytical export scripts such as
   `mongodb/export.py`.

## Catalogue and payout API (F1, F7)

- `GET /catalogue/tracks/search?q=...` searches for a title fragment using
  parameterized `ILIKE`; the query is compatible with the `pg_trgm` index.
- `GET /catalogue/albums/{album_id}` returns an album, its ordered artists,
  and ordered tracks.
- `GET /catalogue/artists/{artist_id}` returns an artist and their albums.
- `POST /payouts/close` accepts `{"month":"YYYY-MM","rate_per_stream":0.004}`.
  Month boundaries are Lisbon-local. Plays shorter than 30 seconds are
  excluded. Each stream's value is divided by the number of main artists on
  its track, then each artist's monthly amount is rounded half-up to cents.
  The payout `stream_count` is the count of qualifying plays on that artist's
  main tracks; `amount` records the artist's allocated share. A payout row is
  created for each main artist, including zero-stream artists, so the unique
  artist/month constraint makes a second close fail with HTTP 409.
- Migration `0005_application_core_grants.py` gives `music_app` read access to
  the catalogue, listeners and plans, and write access to subscription and
  playlist tables used by the app. `play` remains protected by its existing
  SELECT/INSERT-only grant.
- **Known F4 issue:** `playback_service.py` currently issues `UPDATE play` in
  its report and skip paths, but `music_app` has no UPDATE privilege on `play`.
  The resulting database permission error means those operations are not
  working. The fix must preserve the project rule that app writes to `play`
  are append-only; do not solve it by granting unrestricted UPDATE.