"""
Batch ingestion of historical trips into the Bronze layer.

Reads the historical CSV prepared for one site (already in canonical
column names, per scripts/prepare_data.py), casts it to the canonical
Spark schema, stamps ingest_ts (the only field prepare_data.py does
NOT generate) and writes it to the Bronze layer as Parquet.

Columns are matched BY NAME (header=True, no positional schema) and
then cast one by one to the canonical types. This is deliberate:
prepare_data.py's CSV column order does not match TRIP_SCHEMA's
order, and Spark's CSV reader matches an explicit `.schema(...)`
positionally by default, silently misaligning columns instead of
failing loudly. Matching by name avoids that trap entirely.

Bronze is stored as plain Parquet on local/mounted disk, partitioned
by site_id and source. No lakehouse table format (Iceberg/Delta) is
used yet -- this keeps the proof of concept simple; it can be added
later without changing this job's logic, only its write path/format.
"""

import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from src.common.schema import TRIP_SCHEMA, VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

HISTORICAL_FILE = Path(
    os.getenv(
        "HISTORICAL_FILE",
        f"data/prepared/{SITE_ID}/historical.csv",
    )
)

BRONZE_PATH = os.getenv("BRONZE_PATH", "data/lakehouse/bronze")

# Historical (batch) and realtime (streaming) trips live in two separate
# Bronze roots. stream_bronze.py writes with Spark's file sink, which keeps
# a _spark_metadata log in its output directory; any reader of a directory
# with that log (silver.py included) only sees the files the log lists, so
# historical files written next to them by batch_bronze.py would be
# silently ignored. silver.py reads both roots with two separate queries.
HISTORICAL_BRONZE_PATH = f"{BRONZE_PATH}/historical"

# Re-running this job would write the same historical trips again under
# NEW file names. silver.py reads Bronze as a file stream, so it would
# treat them as new input, and sink_postgres.py's additive upsert would
# count them twice in Gold. The job therefore loads each site's history
# only once; FORCE_RELOAD=1 overrides that (only safe after wiping the
# downstream Silver/Gold state, e.g. `make clean`).
FORCE_RELOAD = os.getenv("FORCE_RELOAD", "0") == "1"

# Every canonical field except ingest_ts, which does not exist yet
# in the prepared CSV -- it is added by this job.
CANONICAL_FIELDS = [
    field for field in TRIP_SCHEMA.fields if field.name != "ingest_ts"
]


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:
    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )

    if not HISTORICAL_FILE.exists():
        raise FileNotFoundError(
            f"Historical file not found: {HISTORICAL_FILE}"
        )


def historical_already_loaded() -> bool:
    partition = Path(HISTORICAL_BRONZE_PATH) / f"site_id={SITE_ID}" / "source=historical"
    return any(partition.glob("*.parquet"))


# ============================================================
# Transformation
# ============================================================

def read_historical(spark: SparkSession, path: Path) -> DataFrame:
    """
    Reads the prepared CSV matching columns BY NAME (via the header
    row), not by position. Every value comes in as a string; casting
    to the canonical types happens in cast_to_canonical_types().
    """
    df = spark.read.option("header", True).csv(str(path))

    missing = [
        field.name
        for field in CANONICAL_FIELDS
        if field.name not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Historical CSV is missing expected columns: {missing}"
        )

    return df


def cast_to_canonical_types(df: DataFrame) -> DataFrame:
    for field in CANONICAL_FIELDS:
        df = df.withColumn(field.name, F.col(field.name).cast(field.dataType))
    return df


def add_ingest_timestamp(df: DataFrame) -> DataFrame:
    """
    Stamps the instant each record enters the pipeline, then
    reorders columns to match the canonical schema exactly.
    """
    df = df.withColumn("ingest_ts", F.current_timestamp())
    return df.select(*[field.name for field in TRIP_SCHEMA.fields])


def write_bronze(df: DataFrame, path: str) -> None:
    """
    Overwrites only the touched partitions (site_id=<SITE>/source=historical),
    not the whole Bronze path. Spark's default "static" overwrite mode
    deletes the entire output directory, which would also wipe out any
    realtime data stream_bronze.py had already appended for this site.
    """
    (
        df.write
        .mode("overwrite")
        .option("partitionOverwriteMode", "dynamic")
        .partitionBy("site_id", "source")
        .parquet(path)
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    validate_configuration()

    if historical_already_loaded() and not FORCE_RELOAD:
        print(
            f"Historical data for site '{SITE_ID}' is already in Bronze "
            f"({HISTORICAL_BRONZE_PATH}) -- skipping to avoid double counting in Gold. "
            "Set FORCE_RELOAD=1 only after `make clean`."
        )
        return

    spark = (
        SparkSession.builder
        .appName(f"batch-bronze-{SITE_ID}")
        .getOrCreate()
    )

    print()
    print("========================================")
    print("Batch ingestion -> Bronze")
    print("========================================")
    print(f"Site:            {SITE_ID}")
    print(f"Historical file: {HISTORICAL_FILE}")
    print(f"Bronze path:     {HISTORICAL_BRONZE_PATH}")

    df = read_historical(spark, HISTORICAL_FILE)
    df = cast_to_canonical_types(df)
    df = add_ingest_timestamp(df)

    input_count = df.count()

    write_bronze(df, HISTORICAL_BRONZE_PATH)

    print()
    print(f"Rows written to bronze: {input_count:,}")
    print("Partition preview:")
    df.groupBy("site_id", "source").count().show()
    print("Done.")

    spark.stop()


if __name__ == "__main__":
    main()
