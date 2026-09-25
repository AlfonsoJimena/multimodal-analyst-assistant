-- Gold layer: business aggregates, identical schema on the three sites
-- (Central, Chamartin, Atocha). Auto-executed on first boot of each
-- site's Postgres container via docker-entrypoint-initdb.d (mounted
-- by deploy/docker-compose.site.yml, #47).
--
-- Every non-key column is a COMBINABLE aggregate (trip_count, sum_*),
-- never an average -- see gold.py's module docstring for why. The
-- primary key on each table is exactly what sink_postgres.py upserts
-- on: INSERT ... ON CONFLICT (key columns) DO UPDATE SET
-- col = table.col + EXCLUDED.col (see GOLD_TABLE_KEYS there).
--
-- sum_* columns use unconstrained NUMERIC (no precision/scale) so
-- they never overflow as a site's totals accumulate over the life of
-- the table -- source amounts are DECIMAL(12,2), but the running sum
-- is not.

CREATE TABLE IF NOT EXISTS hourly_metrics (
    site_id           TEXT NOT NULL CHECK (site_id IN ('central', 'chamartin', 'atocha')),
    trip_hour         TIMESTAMP NOT NULL,
    trip_count        BIGINT NOT NULL DEFAULT 0,
    sum_fare_amount   NUMERIC NOT NULL DEFAULT 0,
    sum_trip_distance DOUBLE PRECISION NOT NULL DEFAULT 0,
    sum_tip_amount    NUMERIC NOT NULL DEFAULT 0,
    sum_total_amount  NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id, trip_hour)
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    site_id           TEXT NOT NULL CHECK (site_id IN ('central', 'chamartin', 'atocha')),
    trip_date         DATE NOT NULL,
    trip_count        BIGINT NOT NULL DEFAULT 0,
    sum_fare_amount   NUMERIC NOT NULL DEFAULT 0,
    sum_trip_distance DOUBLE PRECISION NOT NULL DEFAULT 0,
    sum_tip_amount    NUMERIC NOT NULL DEFAULT 0,
    sum_total_amount  NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id, trip_date)
);

CREATE TABLE IF NOT EXISTS zone_metrics (
    site_id           TEXT NOT NULL CHECK (site_id IN ('central', 'chamartin', 'atocha')),
    pu_location_id    INTEGER NOT NULL,
    trip_count        BIGINT NOT NULL DEFAULT 0,
    sum_fare_amount   NUMERIC NOT NULL DEFAULT 0,
    sum_trip_distance DOUBLE PRECISION NOT NULL DEFAULT 0,
    sum_tip_amount    NUMERIC NOT NULL DEFAULT 0,
    sum_total_amount  NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id, pu_location_id)
);

CREATE TABLE IF NOT EXISTS payment_metrics (
    site_id           TEXT NOT NULL CHECK (site_id IN ('central', 'chamartin', 'atocha')),
    payment_type      INTEGER NOT NULL,
    trip_count        BIGINT NOT NULL DEFAULT 0,
    sum_fare_amount   NUMERIC NOT NULL DEFAULT 0,
    sum_trip_distance DOUBLE PRECISION NOT NULL DEFAULT 0,
    sum_tip_amount    NUMERIC NOT NULL DEFAULT 0,
    sum_total_amount  NUMERIC NOT NULL DEFAULT 0,
    PRIMARY KEY (site_id, payment_type)
);
