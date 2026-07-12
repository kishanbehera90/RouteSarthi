"""Create the auth + personalization tables (users, password_resets,
saved_trips, recent_searches). Raw DDL, same pattern as etl/load_delays.py —
no migration framework exists in this project yet.

Run:  python -m etl.init_auth_tables      (from backend/, venv active)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import connect  # noqa: E402

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name          TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS password_resets (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    token_hash  TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS password_resets_user_idx ON password_resets (user_id);

CREATE TABLE IF NOT EXISTS saved_trips (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(id),
    route_id       TEXT NOT NULL,
    route_json     JSONB NOT NULL,
    schema_version INTEGER DEFAULT 1,
    saved_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, route_id)
);

CREATE TABLE IF NOT EXISTS recent_searches (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    from_key     TEXT NOT NULL,
    to_key       TEXT NOT NULL,
    from_place   TEXT NOT NULL,
    to_place     TEXT NOT NULL,
    travel_date  TEXT,
    pref         TEXT,
    searched_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, from_key, to_key)
);
"""


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute(DDL)
        conn.commit()
    print("auth tables ready: users, password_resets, saved_trips, recent_searches")


if __name__ == "__main__":
    main()
