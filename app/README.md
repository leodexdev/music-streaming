# FastAPI app

The application source is under `src/app/`. It connects to PostgreSQL through
SQLAlchemy, MongoDB through PyMongo, and Redis through redis-py. Local settings
are read from the repository `.env`; Compose overrides the database hosts with
service names.

Run the app with the project launcher from the repository root:

```bash
./scripts/run.sh
```

The API is available at <http://localhost:8000>, with interactive OpenAPI docs
at <http://localhost:8000/docs>. Requests acting for a listener use
`X-User-Id`; this project intentionally has no authentication.

Run the focused Python tests and compile the app:

```bash
uv run --project app python -m unittest discover -s app/tests -v
uv run --project app python -m compileall -q app/src/app app/tests
```

Endpoint behavior and project-level setup are documented in the root
[README](../README.md).