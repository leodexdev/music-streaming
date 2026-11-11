from collections.abc import Iterator

import redis
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# PostgreSQL (role app)
engine = create_engine(settings.sqlalchemy_url, pool_size=20, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


# MongoDB (utilizador readWrite)
mongo_client = MongoClient(settings.mongo_url)
mongo_db = mongo_client[settings.mongo_db]

# Redis (com password no URL)
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)