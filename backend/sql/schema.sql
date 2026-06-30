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
