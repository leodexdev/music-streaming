from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, mongo_client, redis_client

app = FastAPI(title="Music Streaming")


@app.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    mongo_client.admin.command("ping")
    redis_client.ping()
    return {"status": "ok"}