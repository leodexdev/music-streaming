from fastapi import FastAPI

app = FastAPI(title="Music Streaming")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}