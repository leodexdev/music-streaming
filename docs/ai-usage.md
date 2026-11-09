## Entry 1: repository structure

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** deciding the folder structure of the repository from the course README and the Project C brief: root files, `app/`, `postgres/`, `mongodb/`, `redis/`, `scripts/`, `docs/`.
**Outcome:** The first proposal was a deep tree with many sub-folders and extra files. I rejected it as too much for a 5-day project and asked for only what the README requires. I kept the second version: the six required folders, the four root files, `scripts/setup.sh`, `scripts/seed.sh` and the seven documents in `docs/`. I changed the AI usage notes into a folder `docs/ai-usage/` with one file per member, and put the course README and brief in `project/`.
**Verification:** compared the final tree against the "Repository structure" and "Documentation" sections of the course README. TODO: run the trainer's `git log` commands once we have commits.
**Mistakes caught:** the AI's first tree was over-engineered and went beyond the README. It also reminded me that the README requires a file named `docs/ai-usage.md` with the signed declaration, so the folder alone does not match the required name. We will add that file.

## Entry 2: Docker Compose and Dockerfile

**Who:** Leo.
**Tool:** Claude (Sonnet 5.5), claude.ai.
**For what:** first draft of `compose.yml` (PostgreSQL, MongoDB, Redis, the FastAPI app, DbGate) and `app/Dockerfile`, plus the variables in `.env.example`.
**Outcome:** TODO: write what we kept as it came, what we changed and what we rejected. For example: we chose DbGate as one admin tool for the three databases instead of separate pgAdmin and mongo-express services; passwords are read from `.env`; ports are published on `127.0.0.1`; PostgreSQL runs with `log_statement=all` for the cache evidence.
**Verification:** TODO: `docker compose up -d`, `docker compose build app`, `curl http://127.0.0.1:8000/health`, and a connection to each engine from DbGate.
**Mistakes caught:** TODO: add any error found when running it, or write "none found".

## Entry 1: Task distribution and time budget

**Who:** Tiago.
**Tool:** Gemini (2.5 Flash), gemini.google.com.
**For what:** creating the team task distribution and time budget document (`docs/task-distribution.md`), defining core responsibilities, estimated durations, priorities, and directory mapping for all 3 group members (Tiago, Leandro, and Paulo).
**Outcome:** The initial AI proposal allocated equal technical weights across engines without considering member expertise or Git verification risks. I requested a refined 15-hour budget per member (~12 hours coding, 3 hours buffer/research) where Leandro acts as repo owner (Docker/infrastructure), I handle core database architecture and Python concurrency control, and Paulo handles auxiliary features. I also rejected Lua script proposals, enforcing pure Python, SQL, and FastAPI libraries (`redis-py`, SQLAlchemy transaction locks). I kept the final markdown table structure and the automated bash verification script.
**Verification:** cross-referenced task paths against the four mandatory Git areas (`postgres/`, `mongodb/`, `redis/`, `app/`) to ensure no member receives a 0-commit penalty.
**Mistakes caught:** the AI's early versions assigned Lua scripts (contrary to our stack decisions) and initially forgot to distribute tasks across all 4 mandatory engine directories for every member. I corrected it to guarantee cross-directory compliance for everyone.