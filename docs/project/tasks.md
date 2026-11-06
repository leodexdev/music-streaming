# Group Project - Task Distribution & Time Budget (15 Hours / Person)

This document details the work split for **Leandro** (Repo Owner), **Tiago**, and **Paulo**. The total budget is **15 hours per person** (45 hours total), structured into:
* **~12 Hours:** Direct hands-on coding/writing per person.
* **3 Hours:** Research, setup, pair programming, debugging, and final review buffer per person.

⚠️ **MANDATORY GIT RULE COMPLIANCE:** To avoid the -2 point penalty per missing area, **every member must produce non-trivial commits in all four paths**: `postgres/`, `mongodb/`, `redis/`, and `app/`. Every member will write code across PostgreSQL, MongoDB, and Redis.

---

## ⏱️ Overall Time Budget Overview

| Member | Primary Focus Area | Development Time | Research, Debugging & Buffer | Total Budget |
| :--- | :--- | :--- | :--- | :--- |
| **Leandro** | Repo Owner, Infrastructure & Export | 12 Hours | 3 Hours | **15 Hours** |
| **Tiago** | Backend Concurrency & Core Transactions | 12 Hours | 3 Hours | **15 Hours** |
| **Paulo** | Auxiliary Features, Pipelines & Caching | 12 Hours | 3 Hours | **15 Hours** |

---

## 1. Leandro (Repo Owner, Infrastructure & Export)

**Total Coding Time:** 12 Hours | **Buffer:** 3 Hours

| Path / Module | Title | Detailed Task Content | Est. Time |
| :--- | :--- | :--- | :--- |
| **Project Root** | Docker Compose & Structure | Create project root structure, `compose.yml` (PostgreSQL, MongoDB, Redis, App), `.env.example`, and write `scripts/setup.sh` to initialize databases and roles. | 2.0 Hours |
| `app/` | Infrastructure Routing | Configure FastAPI application startup, database connection handlers, and base routing structure. | 2.5 Hours |
| `postgres/` | Base Schema & Migrations | Write PostgreSQL migrations for base entities and initial constraints (`NOT NULL`, `FOREIGN KEY`). | 2.0 Hours |
| `mongodb/` | Report Export Script | Write the PostgreSQL-to-MongoDB export script (`mongodb/export.sh`) to synchronize data for reports. | 2.5 Hours |
| `redis/` | Rebuild & Verify Scripts | Write `redis/rebuild.py` (populates Redis from SQL/Mongo after `FLUSHALL`) and `redis/verify.py` (checks consistency). | 3.0 Hours |
| **Buffer** | Repo Maintenance & Testing | Debug environment setup, test Docker builds from clean clones, and review code. | 3.0 Hours |

---

## 2. Tiago (Backend Concurrency & Core Transactions)

**Total Coding Time:** 12 Hours | **Buffer:** 3 Hours

| Path / Module | Title | Detailed Task Content | Est. Time |
| :--- | :--- | :--- | :--- |
| `postgres/` | Core Relational Schema | Design & write SQL migrations for primary transactional tables, adding advanced constraints (`CHECK`, `EXCLUDE`). | 3.0 Hours |
| `app/` | Python Concurrency Control | Implement concurrent flows inside FastAPI using Python/SQLAlchemy transaction isolation levels and row-level locking (`SELECT ... FOR UPDATE`). | 4.0 Hours |
| `mongodb/` | Core Validators | Implement strict MongoDB `$jsonSchema` validation rules and indexes for primary collections. | 2.5 Hours |
| `redis/` | Atomic Session/Counter Handlers | Implement Redis-based rate limiting or token tracking handlers in Python (`redis-py`) using atomic operations. | 2.5 Hours |
| **Buffer** | Concurrency Testing & Fixes | Research transaction isolation bugs, test race conditions via Python scripts, and review code. | 3.0 Hours |

---

## 3. Paulo (Auxiliary Features, Pipelines & Caching)

**Total Coding Time:** 12 Hours | **Buffer:** 3 Hours

| Path / Module | Title | Detailed Task Content | Est. Time |
| :--- | :--- | :--- | :--- |
| `postgres/` | Auxiliary Tables & Indexes | Create secondary tables (e.g., audit logs, lookups) and write performance indexes + `EXPLAIN` analysis documentation. | 2.5 Hours |
| `mongodb/` | Aggregation Pipelines | Build the 3 mandatory MongoDB aggregation pipelines to answer business report questions. | 3.0 Hours |
| `redis/` | Caching & Key Patterns | Implement caching functions in Python for auxiliary lookups using key patterns defined in `docs/redis.md`. | 2.5 Hours |
| `app/` | Auxiliary CRUD & Seed Script | Write auxiliary FastAPI CRUD endpoints and build `scripts/seed.sh` using batch inserts (`COPY`) for deterministic seeding. | 4.0 Hours |
| **Buffer** | Pair Programming & Docs | Pair-program with Leandro and Tiago to understand core flow logic, test API endpoints, and assist with `README.md`. | 3.0 Hours |

---

