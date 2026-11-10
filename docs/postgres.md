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
    -- Acquire exclusive row lock on parent subscription row to serialize concurrent joins
    SELECT p.max_members INTO max_allowed
    FROM subscription s 
    JOIN plan p ON p.id = s.plan_id
    WHERE s.id = NEW.subscription_id
    FOR UPDATE OF s;

    -- Count active members
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
* **Maintenance Mechanism:** Maintained automatically via statement-level triggers utilizing transition tables (`REFERENCING NEW TABLE AS new_rows` / `OLD TABLE AS old_rows`). This guarantees strict consistency without application-level race conditions.

---

## 4. Enforcement Layer Matrix

| Business Rule | Enforced By | Mechanism / Implementation |
| :--- | :--- | :--- |
| **Referential Integrity** | PostgreSQL | `FOREIGN KEY` with `RESTRICT` / `CASCADE` / `SET NULL` |
| **Active Subscription Uniqueness** | PostgreSQL | Partial Unique Index on `subscription(owner_id)` |
| **Plan Capacity Limits** | PostgreSQL | `BEFORE INSERT` Trigger with `FOR UPDATE` lock on `subscription` |
| **Playlist 500 Track Upper Bound** | PostgreSQL | `CHECK (track_count BETWEEN 0 AND 500)` + Statement Triggers |
| **Atomic Track Reordering** | PostgreSQL | `DEFERRABLE INITIALLY DEFERRED` Unique Constraint |
| **Invite Code Expiry (7-day TTL)** | Redis / FastAPI | Redis Key Expiry (`EXPIRE`) + API timestamp validation |
| **Free Listener Skip Limits** | Redis / FastAPI | Atomic `redis-py` pipeline counters (`INCR` + `EXPIRE`) |
| **Single Active Device per Listener** | Redis / FastAPI | Heartbeat session keys in Redis (`SET ... EX 60`) |

---

## 5. Performance Indexing & EXPLAIN (ANALYZE, BUFFERS)

*(Note: Query performance execution plans will be recorded here following synthetic data generation via `scripts/seed.sh`)*

    ### Target Queries for Benchmark Analysis:
    1. **Query 1:** Fetching recent playback history for a listener ordered by timestamp (`play.listener_id`, `play.started_at DESC`).
    2. **Query 2:** Retrieval of playlist track listings ordered by position (`playlist_track.playlist_id`, `playlist_track.position`).
    3. **Query 3:** Fuzzy search over track titles utilizing PostgreSQL trigram indexes (`pg_trgm`).

    ---

    ## 6. Database Roles & Security Model

The database strictly enforces the principle of least privilege using three distinct roles created in `scripts/setup.sh`:

1. **Owner Role (`owner`):** Executed during deployment to apply Alembic migrations (`0001_primary_schema`) and modify table definitions.
2. **Application Role (`app`):** Used by the FastAPI backend. Granted `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on operational tables. Has no DDL or superuser privileges.
3. **Read-Only Role (`read_only`):** Used exclusively by analytical export scripts (`mongodb/export.py`). Restricted to `SELECT` operations across transactional tables.