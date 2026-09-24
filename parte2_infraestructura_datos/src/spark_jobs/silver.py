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

from pyspark.sql import DataFrame, SparkSession

from src.common.cleaning import split_valid_quarantine
from src.common.schema import TRIP_SCHEMA, VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

BRONZE_PATH = os.getenv("BRONZE_PATH", "data/lakehouse/bronze")
SILVER_PATH = os.getenv("SILVER_PATH", "data/lakehouse/silver")
QUARANTINE_PATH = os.getenv("QUARANTINE_PATH", "data/lakehouse/quarantine")

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    f"data/checkpoints/silver/{SITE_ID}",
)

TRIGGER_INTERVAL_SECONDS = int(os.getenv("TRIGGER_INTERVAL_SECONDS", "10"))

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
    print(f"Bronze path:     {BRONZE_PATH}")
    print(f"Silver path:     {SILVER_PATH}")
    print(f"Quarantine path: {QUARANTINE_PATH}")
    print(f"Run mode:        {RUN_MODE}")

    bronze_stream = (
        spark.readStream
        .schema(TRIP_SCHEMA)
        .parquet(BRONZE_PATH)
    )

    writer = (
        bronze_stream.writeStream
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
