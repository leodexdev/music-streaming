# Group Project - Task Distribution & Time Budget (15 Hours / Person)

This document provides a comprehensive, file-by-file action plan for **Leandro** (Repo Owner & Infrastructure Lead) and **Tiago** (Concurrency & Core Architecture Lead) following the transition to a 2-member team. 

The total workload of 45 project hours has been redistributed into **~22.5 hours per person** (~18 hours of hands-on coding/scripting + 4.5 hours of testing, debugging, and documentation).

---

## 🛑 MANDATORY GIT COMPLIANCE RULE

To avoid losing **2 points per missing directory** on the individual grade modifier, **both Leandro and Tiago must write non-trivial code in all four target directories**:
- `postgres/`
- `mongodb/`
- `redis/`
- `app/`

---

## ⏱️ Budget & Effort Allocation Overview

| Member | Primary Focus | Dev & Coding Time | Buffer, Debug & Review | Total Budget |
| :--- | :--- | :--- | :--- | :--- |
| **Leandro** | Infrastructure, Exports, Verification, Auxiliary Features | 18.0 Hours | 4.5 Hours | **22.5 Hours** |
| **Tiago** | Relational Schemas, Concurrency Locks, Caching & API Endpoints | 18.0 Hours | 4.5 Hours | **22.5 Hours** |

---

## 1. Leandro (Infrastructure, Reports & Export Lead)

**Total Development Time:** 18.0 Hours | **Buffer & Debug:** 4.5 Hours

### 📁 Root & Infrastructure Tasks
* **Task 1.1: Docker Compose Configuration**
  * **File:** `compose.yml`
  * **Details:** Define services for PostgreSQL (port 5432), MongoDB (port 27017), Redis (port 6379), and the FastAPI application (`app/`). Ensure environment variables are loaded from `.env`.
  * **Est. Time:** 1.5 Hours

* **Task 1.2: Environment Configuration Template**
  * **File:** `.env.example`
  * **Details:** Define placeholder variables for database credentials: `DATABASE_URL` (app role), `MIGRATION_DATABASE_URL` (owner role), `READONLY_DATABASE_URL`, `MONGO_URL`, `MONGO_ROOT_URL`, and `REDIS_URL`.
  * **Est. Time:** 0.5 Hours

* **Task 1.3: Environment Setup Script**
  * **File:** `scripts/setup.sh`
  * **Details:** Write shell execution script to:
    1. Connect as PostgreSQL superuser to create the database, roles (`owner`, `app`, `read_only`), and extensions (`btree_gist`, `pg_trgm`).
    2. Run migrations as `owner` and apply privileges/default privileges for `app` and `read_only`.
    3. Connect to MongoDB as root to create the app user, collections, `$jsonSchema` validators, and indexes.
  * **Est. Time:** 2.0 Hours

---

### 📁 `postgres/` Tasks (Leandro)
* **Task 1.4: Secondary Schemas & Audit Tables**
  * **Files:** `postgres/migrations/0002_secondary_tables.sql` (or Alembic migration file under `postgres/migrations/versions/`)
  * **Details:** Write SQL migration for secondary entities (e.g., audit/event logs, system configuration, lookup categories). Include `NOT NULL`, `DEFAULT` values, foreign keys with explicit `ON DELETE` rules, and grant privileges to the `app` and `read_only` roles.
  * **Est. Time:** 2.5 Hours

---

### 📁 `mongodb/` Tasks (Leandro)
* **Task 1.5: Report Export Script**
  * **File:** `mongodb/export.py` (or `mongodb/export.sh`)
  * **Details:** Write a Python script using `psycopg2`/`SQLAlchemy` and `pymongo` that connects to PostgreSQL using the `read_only` role, extracts report-relevant transactional data, transforms it, and populates the MongoDB reporting collections. Make it idempotent so it can be re-run at any time.
  * **Est. Time:** 3.0 Hours

* **Task 1.6: Analytical Aggregation Pipelines**
  * **Files:** `mongodb/pipeline_1.json`, `mongodb/pipeline_2.json`, `mongodb/pipeline_3.json`
  * **Details:** Write 3 distinct MongoDB aggregation pipelines to answer the complex business report questions required by the project brief. Save each pipeline query and include sample JSON outputs.
  * **Est. Time:** 3.0 Hours

---

### 📁 `redis/` Tasks (Leandro)
* **Task 1.7: Cache Rebuild Script**
  * **File:** `redis/rebuild.py`
  * **Details:** Write a Python script using `redis-py` that queries PostgreSQL/MongoDB and completely populates derived Redis keys (e.g., entity lookup caches, counters) from scratch after a `FLUSHALL`.
  * **Est. Time:** 1.5 Hours

* **Task 1.8: Cache Verification Script**
  * **File:** `redis/verify.py`
  * **Details:** Write a Python script that compares data stored in Redis against the source of truth in PostgreSQL/MongoDB. The script must output discrepancies and exit with `0` if all keys match, or `1` if there is a mismatch.
  * **Est. Time:** 1.5 Hours

---

### 📁 `app/` Tasks (Leandro)
* **Task 1.9: Seed Orchestration Script & Data Generator**
  * **Files:** `scripts/seed.sh` and `postgres/seed.py`
  * **Details:** Write a deterministic Python seed script using batch inserts (`COPY` in PostgreSQL or bulk execution) that populates realistic volumes of seed data in under 5 minutes. `seed.sh` must run PostgreSQL seed, run `export.py`, and execute `rebuild.py`.
  * **Est. Time:** 2.5 Hours

---

## 2. Tiago (Core Architecture, Concurrency & API Lead)

**Total Development Time:** 18.0 Hours | **Buffer & Debug:** 4.5 Hours

### 📁 `postgres/` Tasks (Tiago)
* **Task 2.1: Primary Database Schema & Constraints**
  * **Files:** `postgres/migrations/0001_initial_schema.sql` (or Alembic equivalent)
  * **Details:** Write core migrations for main business tables in Third Normal Form (3NF). Implement `CHECK` constraints, `EXCLUDE` constraints (e.g., over-booking interval overlap check via `btree_gist`), and custom `ENUM` types. Define foreign keys with explicit `ON DELETE` rules.
  * **Est. Time:** 4.0 Hours

* **Task 2.2: Performance Indexing & EXPLAIN Evidence**
  * **File:** `docs/postgres.md` (and index definitions in `postgres/migrations/`)
  * **Details:** Add indexes for high-frequency queries. Execute `EXPLAIN (ANALYZE, BUFFERS)` queries on seeded data before and after dropping indexes (inside a rolled-back transaction) and document performance comparisons in `docs/postgres.md`.
  * **Est. Time:** 2.0 Hours

---

### 📁 `mongodb/` Tasks (Tiago)
* **Task 2.3: Collection Setup & Schema Validation**
  * **File:** `mongodb/setup_collections.py`
  * **Details:** Write Python script using `pymongo` to initialize mandatory MongoDB collections. Define strict `$jsonSchema` validators (`validationLevel: "strict"`, `validationAction: "error"`) for document structures, data types, and required fields. Add TTL indexes for expiring documents.
  * **Est. Time:** 2.5 Hours

---

### 📁 `redis/` Tasks (Tiago)
* **Task 2.4: Atomic Redis Operations & Caching Patterns**
  * **File:** `app/services/cache_service.py` (or `redis/redis_operations.py`)
  * **Details:** Implement `redis-py` helper functions for reading/writing temporary data. Implement atomic fixed-window rate limiting or reservation holds using `pipeline()` / `MULTI-EXEC` with `INCR` and `EXPIRE` set atomically.
  * **Est. Time:** 2.5 Hours

---

### 📁 `app/` Tasks (Tiago)
* **Task 2.5: Application Core & Database Connections**
  * **Files:** `app/main.py`, `app/database.py`, `app/config.py`
  * **Details:** Create the main FastAPI application structure. Set up SQLAlchemy engines connecting to PostgreSQL with the `app` role (no superuser), PyMongo client connecting with the `readWrite` app user, and Redis client authenticated via password.
  * **Est. Time:** 2.5 Hours

* **Task 2.6: High-Concurrency Transactional Endpoints**
  * **Files:** `app/routers/concurrency.py`, `app/services/booking_service.py`
  * **Details:** Build API routes that handle high-contention business logic. Enforce strict isolation in PostgreSQL (`SERIALIZABLE` or `READ COMMITTED` with explicit `SELECT ... FOR UPDATE` row-level locks) to prevent race conditions during concurrent requests.
  * **Est. Time:** 4.5 Hours

---

## 🛡️ Git Verification Script

Before tagging the final release (`v1.0.0`), both team members must run this script from the root of the repository to confirm that neither author has 0 commits in any area:

```bash
#!/bin/bash
# Run this script to verify commit count across all mandatory paths

AUTHORS=("leandro" "tiago") # Replace with exact emails or names in your git config
AREAS=("postgres/" "mongodb/" "redis/" "app/")

echo "=== MANDATORY GIT COMMIT CHECK ==="
for author in "${AUTHORS[@]}"; do
  echo "------------------------------------------"
  echo "Checking commits for: $author"
  echo "------------------------------------------"
  for area in "${AREAS[@]}"; do
    COUNT=$(git log v1.0.0 --no-merges --author="$author" --oneline -- "$area" | wc -l)
    printf "%-12s : %d commits\n" "$area" "$COUNT"
  done
done
echo "=========================================="
```