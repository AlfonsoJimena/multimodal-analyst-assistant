"""
Writes Gold aggregates into Postgres with an idempotent upsert.

Reuses gold.py's compute_*_metrics() functions unchanged -- this
module only replaces gold.py's local Parquet write with the real
destination. Every gold table stores combinable quantities
(trip_count, sum_<column>), so upserting means literally ADDING the
incoming micro-batch's partial numbers to whatever is already in the
row: INSERT ... ON CONFLICT (key columns) DO UPDATE SET
col = table.col + EXCLUDED.col. Without this, Structured Streaming's
foreachBatch would re-run on retries and a plain INSERT (or an
overwrite) would double-count or lose data.

The four gold tables are small (one row per hour/day/zone/payment
type per micro-batch), so each micro-batch is collected to the
driver and written with a handful of psycopg2 calls -- no need for
Spark's JDBC writer, which doesn't support upsert natively.
"""

import os

import psycopg2
import psycopg2.extras
from pyspark.sql import DataFrame, SparkSession

from src.spark_jobs.gold import GOLD_TABLES, SILVER_SCHEMA
from src.common.schema import VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

SILVER_PATH = os.getenv("SILVER_PATH", "data/lakehouse/silver")

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    f"data/checkpoints/sink_postgres/{SITE_ID}",
)

TRIGGER_INTERVAL_SECONDS = int(os.getenv("TRIGGER_INTERVAL_SECONDS", "10"))
RUN_MODE = os.getenv("RUN_MODE", "continuous")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "pids")
POSTGRES_USER = os.getenv("POSTGRES_USER", "pids")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pids")

# Primary key columns for each gold table -- what ON CONFLICT matches
# on. Every other column returned by gold.py's compute_*_metrics()
# is additive and gets summed on conflict.
GOLD_TABLE_KEYS = {
    "hourly_metrics": ["site_id", "trip_hour"],
    "daily_metrics": ["site_id", "trip_date"],
    "zone_metrics": ["site_id", "pu_location_id"],
    "payment_metrics": ["site_id", "payment_type"],
}


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:
    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )

    if RUN_MODE not in ("continuous", "once"):
        raise ValueError(
            f"Invalid RUN_MODE '{RUN_MODE}'. Expected 'continuous' or 'once'."
        )


def get_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


JOB_NAME = "sink_postgres"


def ensure_control_table(connection) -> None:
    """
    Tracks which (job, site, batch_id) combinations have already been
    applied, so a retried micro-batch (foreachBatch is at-least-once,
    not exactly-once) can be detected and skipped instead of double-
    counting its sums. Created here so this job does not depend on
    sql/init.sql (#60) for something that is really its own
    implementation detail, not a shared business table.
    """
    with connection, connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_batches (
                job_name TEXT NOT NULL,
                site_id TEXT NOT NULL,
                batch_id BIGINT NOT NULL,
                processed_at TIMESTAMP NOT NULL DEFAULT now(),
                PRIMARY KEY (job_name, site_id, batch_id)
            )
            """
        )


# ============================================================
# Upsert
# ============================================================

def build_upsert_sql(table_name: str, key_columns: list, all_columns: list) -> str:
    additive_columns = [c for c in all_columns if c not in key_columns]

    columns_sql = ", ".join(all_columns)
    placeholders_sql = ", ".join(["%s"] * len(all_columns))
    conflict_sql = ", ".join(key_columns)
    update_sql = ", ".join(
        f"{column} = {table_name}.{column} + EXCLUDED.{column}"
        for column in additive_columns
    )

    return (
        f"INSERT INTO {table_name} ({columns_sql}) "
        f"VALUES ({placeholders_sql}) "
        f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {update_sql}"
    )


def upsert_dataframe(connection, table_name: str, df: DataFrame) -> int:
    key_columns = GOLD_TABLE_KEYS[table_name]
    all_columns = df.columns

    rows = [tuple(row[column] for column in all_columns) for row in df.collect()]

    if not rows:
        return 0

    sql = build_upsert_sql(table_name, key_columns, all_columns)

    with connection.cursor() as cursor:
        psycopg2.extras.execute_batch(cursor, sql, rows)

    return len(rows)


# ============================================================
# Per-micro-batch processing
# ============================================================

def process_batch(batch_df: DataFrame, batch_id: int) -> None:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO processed_batches (job_name, site_id, batch_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (job_name, site_id, batch_id) DO NOTHING
                RETURNING 1
                """,
                (JOB_NAME, SITE_ID, batch_id),
            )
            is_new_batch = cursor.fetchone() is not None

        if not is_new_batch:
            connection.rollback()
            print(
                f"[batch {batch_id}] site={SITE_ID} "
                "already processed -- skipping (retry-safe)"
            )
            return

        batch_df = batch_df.filter(batch_df.site_id == SITE_ID)
        batch_df.persist()

        summary = []
        for table_name, compute_fn in GOLD_TABLES.items():
            table_df = compute_fn(batch_df)
            written = upsert_dataframe(connection, table_name, table_df)
            summary.append(f"{table_name}={written} rows upserted")

        batch_df.unpersist()

        # Commits the control-table insert and every upsert above as
        # ONE transaction: either the whole batch lands, or none of
        # it does, so a crash mid-batch can never leave a partial
        # (and hard to detect) update behind.
        connection.commit()

        print(f"[batch {batch_id}] site={SITE_ID} " + " | ".join(summary))
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ============================================================
# Main
# ============================================================

def main() -> None:
    validate_configuration()

    spark = (
        SparkSession.builder
        .appName(f"sink-postgres-{SITE_ID}")
        .getOrCreate()
    )

    print()
    print("========================================")
    print("Silver -> Gold -> Postgres (upsert)")
    print("========================================")
    print(f"Site:            {SITE_ID}")
    print(f"Silver path:     {SILVER_PATH}")
    print(f"Postgres:        {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    print(f"Run mode:        {RUN_MODE}")

    ensure_control_table(get_connection())

    silver_stream = spark.readStream.schema(SILVER_SCHEMA).parquet(SILVER_PATH)

    writer = (
        silver_stream.writeStream
        .foreachBatch(process_batch)
        .option("checkpointLocation", CHECKPOINT_PATH)
    )

    if RUN_MODE == "once":
        query = writer.trigger(availableNow=True).start()
    else:
        query = writer.trigger(
            processingTime=f"{TRIGGER_INTERVAL_SECONDS} seconds"
        ).start()

    query.awaitTermination()


if __name__ == "__main__":
    main()
