"""SQLAlchemy engine. DATABASE_URL (from .env) is the only thing that changes between
Docker Postgres and a local Postgres install."""

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine

import mandipulse.config  # noqa: F401  (loads .env)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
    return url


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)
