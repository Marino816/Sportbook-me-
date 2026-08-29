"""Upgrade a d3f3g2d1 database to e4a1b2c3 — not an ORM create_all shortcut."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from api.auth import hash_password

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = "/tmp/sbme_upgrade_d3f3g2d1.sqlite"
SYNC_URL = f"sqlite:///{DB_PATH}"
ASYNC_URL = f"sqlite+aiosqlite:///{DB_PATH}"


def _d3f3g2d1_users_schema(engine) -> None:
    """Users table as it exists at production revision d3f3g2d1."""
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.execute(text("DROP TABLE IF EXISTS user_oauth_identities"))
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.execute(text(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email VARCHAR,
                hashed_password VARCHAR,
                is_pro BOOLEAN,
                is_active BOOLEAN,
                stripe_customer_id VARCHAR,
                active_subscription_id INTEGER,
                created_at DATETIME,
                role VARCHAR NOT NULL DEFAULT 'user',
                is_beta BOOLEAN NOT NULL DEFAULT 0
            )
            """
        ))
        conn.execute(text(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('d3f3g2d1')"))


def _alembic_upgrade(revision: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["DATABASE_URL"] = ASYNC_URL
    env["PYTHONPATH"] = str(BACKEND)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
    )


def test_upgrade_from_d3f3g2d1_preserves_password_user_and_allows_oauth_null_hash():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    engine = create_engine(SYNC_URL)
    _d3f3g2d1_users_schema(engine)

    hashed = hash_password("securepass123")
    with engine.begin() as conn:
        cols = {c["name"]: c for c in inspect(conn).get_columns("users")}
        assert cols["hashed_password"]["nullable"] is True
        conn.execute(
            text(
                "INSERT INTO users (email, hashed_password, is_pro, is_active, role, is_beta) "
                "VALUES ('survivor@example.com', :hp, 0, 1, 'user', 0)"
            ),
            {"hp": hashed},
        )
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "d3f3g2d1"

    result = _alembic_upgrade("e4a1b2c3")
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    with engine.begin() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "e4a1b2c3"
        cols = {c["name"]: c for c in inspect(conn).get_columns("users")}
        assert "username" in cols
        assert cols["username"]["nullable"] is True
        assert cols["hashed_password"]["nullable"] is True
        tables = inspect(conn).get_table_names()
        assert "user_oauth_identities" in tables
        oauth_cols = {c["name"]: c for c in inspect(conn).get_columns("user_oauth_identities")}
        assert oauth_cols["provider_email"]["nullable"] is True
        email, username, stored = conn.execute(
            text("SELECT email, username, hashed_password FROM users WHERE email = 'survivor@example.com'")
        ).one()
        assert email == "survivor@example.com"
        assert username is None
        assert stored == hashed
        conn.execute(
            text(
                "INSERT INTO users (email, hashed_password, username, is_pro, is_active, role, is_beta) "
                "VALUES ('oauthnull@example.com', NULL, 'oauthnull', 0, 1, 'user', 0)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO user_oauth_identities (user_id, provider, provider_subject, provider_email) "
                "VALUES ((SELECT id FROM users WHERE email = 'oauthnull@example.com'), 'google', 'sub-null', NULL)"
            )
        )

    from starlette.testclient import TestClient
    from tests.auth_app import auth_app, override_get_db as shared_override
    from models.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    async_engine = create_async_engine(ASYNC_URL)
    Session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            yield session

    auth_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(auth_app) as client:
            ok = client.post(
                "/api/auth/login",
                json={"email": "survivor@example.com", "password": "securepass123"},
            )
            assert ok.status_code == 200, ok.text
            denied = client.post(
                "/api/auth/login",
                json={"email": "oauthnull@example.com", "password": "securepass123"},
            )
            assert denied.status_code == 401
            assert denied.json()["detail"] == "Invalid username/email or password."
    finally:
        auth_app.dependency_overrides[get_db] = shared_override
