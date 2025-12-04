from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import psycopg


@dataclass
class DatabaseConfig:
    url: str


def get_db_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")


def connect() -> psycopg.Connection:
    url = get_db_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(url)
