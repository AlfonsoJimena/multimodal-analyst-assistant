-- Quarantine: rows rejected by src/common/cleaning.py's quality rules.
-- Auto-executed on first boot of each site's Postgres container via
-- docker-entrypoint-initdb.d (mounted by deploy/docker-compose.site.yml, #47).
--
-- Column set mirrors what split_valid_quarantine() (cleaning.py)
-- returns as quarantine_df: every TRIP_SCHEMA field (schema.py) plus
-- is_cancelled, rejection_reason and rejected_at.
--
-- Unlike TRIP_SCHEMA, the trip-data columns here are all NULLABLE:
-- the "missing_required_field" rule is exactly what sends a row here
-- when pickup_datetime, do_location_id, etc. are null, so the table
-- must be able to store that.

CREATE TABLE IF NOT EXISTS silver_rejected (
    id                     BIGSERIAL PRIMARY KEY,

    -- Metadata (TRIP_SCHEMA)
    trip_id                TEXT,
    site_id                TEXT,
    source                 TEXT,
    schema_version         INTEGER,
    ingest_ts              TIMESTAMP,

    -- Trip information (TRIP_SCHEMA)
    vendor_id              INTEGER,
    pickup_datetime        TIMESTAMP,
    dropoff_datetime       TIMESTAMP,
    passenger_count        INTEGER,
    trip_distance          DOUBLE PRECISION,
    ratecode_id            INTEGER,
    store_and_fwd_flag     TEXT,
    pu_location_id         INTEGER,
    do_location_id         INTEGER,

    -- Payment information (TRIP_SCHEMA)
    payment_type            INTEGER,
    fare_amount             NUMERIC(12, 2),
    extra                   NUMERIC(12, 2),
    mta_tax                 NUMERIC(12, 2),
    tip_amount              NUMERIC(12, 2),
    tolls_amount            NUMERIC(12, 2),
    improvement_surcharge   NUMERIC(12, 2),
    total_amount            NUMERIC(12, 2),
    congestion_surcharge    NUMERIC(12, 2),

    -- Added by cleaning.py
    is_cancelled            BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason        TEXT NOT NULL,
    rejected_at             TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_silver_rejected_site_id ON silver_rejected (site_id);
