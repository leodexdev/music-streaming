# AI usage: Leo

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