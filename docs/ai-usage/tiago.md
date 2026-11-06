# AI usage: Tiago

## Entry 1: Task distribution and time budget

**Who:** Tiago.
**Tool:** Gemini (2.5 Flash), gemini.google.com.
**For what:** creating the team task distribution and time budget document (`docs/task-distribution.md`), defining core responsibilities, estimated durations, priorities, and directory mapping for all 3 group members (Tiago, Leandro, and Paulo).
**Outcome:** The initial AI proposal allocated equal technical weights across engines without considering member expertise or Git verification risks. I requested a refined 15-hour budget per member (~12 hours coding, 3 hours buffer/research) where Leandro acts as repo owner (Docker/infrastructure), I handle core database architecture and Python concurrency control, and Paulo handles auxiliary features. I also rejected Lua script proposals, enforcing pure Python, SQL, and FastAPI libraries (`redis-py`, SQLAlchemy transaction locks). I kept the final markdown table structure and the automated bash verification script.
**Verification:** cross-referenced task paths against the four mandatory Git areas (`postgres/`, `mongodb/`, `redis/`, `app/`) to ensure no member receives a 0-commit penalty.
**Mistakes caught:** the AI's early versions assigned Lua scripts (contrary to our stack decisions) and initially forgot to distribute tasks across all 4 mandatory engine directories for every member. I corrected it to guarantee cross-directory compliance for everyone.