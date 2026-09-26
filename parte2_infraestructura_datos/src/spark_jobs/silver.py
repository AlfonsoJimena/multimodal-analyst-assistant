"""
Silver layer: applies the shared cleaning rules (src/common/cleaning.py)
to Bronze data and splits it into valid trips and quarantined ones.

Bronze is read as a streaming source so the SAME code processes the
historical trips already sitting there (as an initial batch) and any
realtime trips stream_bronze.py keeps appending -- there is no
separate "batch silver" job, by design (Antonio's original proposal:
"reutilizando las mismas reglas para histórico y realtime").

Each micro-batch is handled with foreachBatch because a single
Structured Streaming query can only have one sink, and we need two
(valid trips -> Silver, rejected trips -> quarantine).
"""

import os
import time

from pyspark.sql import DataFrame, SparkSession

from src.common.cleaning import split_valid_quarantine
from src.common.schema import TRIP_SCHEMA, VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

BRONZE_PATH = os.getenv("BRONZE_PATH", "data/lakehouse/bronze")

# Historical (batch) and realtime (streaming) trips live in two separate
# Bronze roots. stream_bronze.py writes with Spark's file sink, which keeps
# a _spark_metadata log in its output directory; any reader of a directory
# with that log (silver.py included) only sees the files the log lists, so
# historical files written next to them by batch_bronze.py would be
# silently ignored. silver.py reads both roots with two separate queries.
HISTORICAL_BRONZE_PATH = f"{BRONZE_PATH}/historical"
REALTIME_BRONZE_PATH = f"{BRONZE_PATH}/realtime"
SILVER_PATH = os.getenv("SILVER_PATH", "data/lakehouse/silver")
QUARANTINE_PATH = os.getenv("QUARANTINE_PATH", "data/lakehouse/quarantine")

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    f"data/checkpoints/silver/{SITE_ID}",
)

TRIGGER_INTERVAL_SECONDS = int(os.getenv("TRIGGER_INTERVAL_SECONDS", "10"))
WAIT_SECONDS = 5

# "continuous" keeps running, picking up new realtime bronze files as
# stream_bronze.py appends them. "once" processes everything currently
# in bronze and stops -- used for local testing/demos without Kafka.
RUN_MODE = os.getenv("RUN_MODE", "continuous")


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


# ============================================================
# Per-micro-batch processing
# ============================================================

def process_batch(batch_df: DataFrame, batch_id: int) -> None:
    batch_df = batch_df.filter(batch_df.site_id == SITE_ID)
    batch_df.persist()

    valid_df, quarantine_df = split_valid_quarantine(batch_df)

    (
        valid_df.write
        .mode("append")
        .partitionBy("site_id", "source")
        .parquet(SILVER_PATH)
    )

    (
        quarantine_df.write
        .mode("append")
        .partitionBy("site_id")
        .parquet(QUARANTINE_PATH)
    )

    valid_count = valid_df.count()
    quarantine_count = quarantine_df.count()

    print(
        f"[batch {batch_id}] site={SITE_ID} "
        f"valid={valid_count:,} quarantined={quarantine_count:,}"
    )

    batch_df.unpersist()


# ============================================================
# Main
# ============================================================

def bronze_query(spark: SparkSession, path: str, name: str):
    """Streaming query from one Bronze root into Silver (+ quarantine)."""
    return (
        spark.readStream.schema(TRIP_SCHEMA).parquet(path)
        .writeStream
        .foreachBatch(process_batch)
        .option("checkpointLocation", f"{CHECKPOINT_PATH}/{name}")
    )


def wait_for_stream_sink(path: str) -> None:
    """
    Waits until stream_bronze.py has committed its first micro-batch at
    `path` (an entry in `_spark_metadata`). Starting earlier breaks in
    Spark 4.2: on a missing directory the query fails at start-up, and on
    a sink whose log is still empty the partition columns (site_id,
    source) are not detected, so the file columns get misaligned against
    TRIP_SCHEMA (CAST_INVALID_INPUT: 'central' cannot be cast to BIGINT).
    Files committed after the query has started are read correctly.
    """
    metadata = os.path.join(path, "_spark_metadata")
    while not (os.path.isdir(metadata) and any(
        not name.startswith(".") for name in os.listdir(metadata)
    )):
        print(f"Waiting for the first realtime batch in {metadata}...")
        time.sleep(WAIT_SECONDS)


def main() -> None:
    validate_configuration()

    spark = (
        SparkSession.builder
        .appName(f"silver-{SITE_ID}")
        .getOrCreate()
    )

    print()
    print("========================================")
    print("Bronze -> Silver (+ quarantine)")
    print("========================================")
    print(f"Site:            {SITE_ID}")
    print(f"Bronze paths:    {HISTORICAL_BRONZE_PATH}, {REALTIME_BRONZE_PATH}")
    print(f"Silver path:     {SILVER_PATH}")
    print(f"Quarantine path: {QUARANTINE_PATH}")
    print(f"Run mode:        {RUN_MODE}")

    # 1) Historical: loaded once by batch_bronze.py, so it is drained
    #    with availableNow and the query ends. Its checkpoint makes a
    #    restart skip what was already processed.
    # 2) Realtime: keeps running, picking up what stream_bronze.py appends.
    # The two run one after the other, never at the same time: two
    # queries appending to the same Silver path concurrently would share
    # its _temporary commit directory. (A single unionByName of both
    # streams is not an option either: Spark 4.2 fails with
    # PLAN_VALIDATION_FAILED_RULE_IN_BATCH when only one side has data.)
    if os.path.isdir(HISTORICAL_BRONZE_PATH):
        bronze_query(spark, HISTORICAL_BRONZE_PATH, "historical").trigger(
            availableNow=True
        ).start().awaitTermination()
    else:
        print(f"No historical data at {HISTORICAL_BRONZE_PATH} -- skipping it.")

    wait_for_stream_sink(REALTIME_BRONZE_PATH)
    realtime = bronze_query(spark, REALTIME_BRONZE_PATH, "realtime")
    if RUN_MODE == "once":
        query = realtime.trigger(availableNow=True).start()
    else:
        query = realtime.trigger(
            processingTime=f"{TRIGGER_INTERVAL_SECONDS} seconds"
        ).start()

    query.awaitTermination()


if __name__ == "__main__":
    main()
