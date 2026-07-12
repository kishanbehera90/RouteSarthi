-- RouteSarthi engine schema (Step 1). Spatial via PostGIS.
-- Run by backend/etl/load_all.py; kept here as the human-readable reference.

CREATE EXTENSION IF NOT EXISTS postgis;

-- Railway stations (datameet/railways, CC0) -------------------------------
CREATE TABLE IF NOT EXISTS stations (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    state       TEXT,
    zone        TEXT,
    address     TEXT,
    lat         DOUBLE PRECISION,
    lng         DOUBLE PRECISION,
    num_trains  INTEGER DEFAULT 0,        -- "train density" at this station
    geom        geography(Point, 4326)
);
CREATE INDEX IF NOT EXISTS stations_geom_idx ON stations USING GIST (geom);
CREATE INDEX IF NOT EXISTS stations_name_idx ON stations (lower(name));

-- Trains (derived from schedules) -----------------------------------------
CREATE TABLE IF NOT EXISTS trains (
    number      TEXT PRIMARY KEY,
    name        TEXT,
    num_stops   INTEGER DEFAULT 0
);

-- Stops / schedule (datameet/railways) ------------------------------------
CREATE TABLE IF NOT EXISTS stops (
    id            BIGINT PRIMARY KEY,
    train_number  TEXT,
    station_code  TEXT,
    station_name  TEXT,
    arrival       TEXT,        -- 'HH:MM:SS' or NULL (origin/terminus)
    departure     TEXT,
    day           INTEGER,
    seq           INTEGER      -- order along the train's route
);
CREATE INDEX IF NOT EXISTS stops_train_idx   ON stops (train_number, seq);
CREATE INDEX IF NOT EXISTS stops_station_idx ON stops (station_code);

-- City / town gazetteer (GeoNames IN, CC-BY) ------------------------------
CREATE TABLE IF NOT EXISTS cities (
    id            BIGINT PRIMARY KEY,      -- geonameid
    name          TEXT,
    asciiname     TEXT,
    admin1        TEXT,
    population    BIGINT DEFAULT 0,
    feature_code  TEXT,
    lat           DOUBLE PRECISION,
    lng           DOUBLE PRECISION,
    geom          geography(Point, 4326)
);
CREATE INDEX IF NOT EXISTS cities_geom_idx ON cities USING GIST (geom);
CREATE INDEX IF NOT EXISTS cities_name_idx ON cities (lower(asciiname));
-- Both name columns are searched with OR in geocoding; without BOTH indexes
-- Postgres falls back to a 558k-row seq scan (see ENGINEERING_NOTES Layer 3).
CREATE INDEX IF NOT EXISTS cities_name_lower_idx ON cities (lower(name));

-- Auth + per-user personalization (etl/init_auth_tables.py) ----------------
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
    token_hash  TEXT UNIQUE NOT NULL,   -- store only the HASH of the token
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS password_resets_user_idx ON password_resets (user_id);

CREATE TABLE IF NOT EXISTS saved_trips (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(id),
    route_id       TEXT NOT NULL,
    route_json     JSONB NOT NULL,      -- full snapshot: transfer-route ids can't
    schema_version INTEGER DEFAULT 1,   -- be rebuilt stably after a restart (no Redis yet)
    saved_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, route_id)
);

CREATE TABLE IF NOT EXISTS recent_searches (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    from_key     TEXT NOT NULL,         -- normalized (trim+lower) for dedup
    to_key       TEXT NOT NULL,
    from_place   TEXT NOT NULL,         -- display casing, from /api/places
    to_place     TEXT NOT NULL,
    travel_date  TEXT,
    pref         TEXT,
    searched_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, from_key, to_key)
);
