"""
Streaming ingestion of realtime trips into the Bronze layer.

Reads JSON events published by src/producer/producer.py to Kafka,
parses them, casts them to the canonical schema, stamps ingest_ts
(the instant each record enters the pipeline) and appends them to
the same Bronze location used by batch_bronze.py.

The parsing logic (parse_events) is deliberately separated from the
Kafka I/O (main) so it can be exercised with a plain, static
DataFrame in tests/smoke checks without a running Kafka broker.
"""

import os
from datetime import datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from src.common.schema import TRIP_SCHEMA, VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "taxi-trips")

BRONZE_PATH = os.getenv("BRONZE_PATH", "data/lakehouse/bronze")

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    f"data/checkpoints/stream_bronze/{SITE_ID}",
)

TRIGGER_INTERVAL_SECONDS = int(
    os.getenv("TRIGGER_INTERVAL_SECONDS", "10")
)


# ============================================================
# Shape of the JSON payload published by src/producer/producer.py
# (a dict built from a pandas row -- see producer.shift_timestamps).
# Timestamps arrive as ISO-8601 strings, everything else as the
# JSON-native type pandas/json produced for it.
# ============================================================

EVENT_SCHEMA = StructType([
    StructField("vendor_id", IntegerType(), True),
    StructField("pickup_datetime", StringType(), True),
    StructField("dropoff_datetime", StringType(), True),
    StructField("passenger_count", IntegerType(), True),
    StructField("trip_distance", DoubleType(), True),
    StructField("ratecode_id", IntegerType(), True),
    StructField("store_and_fwd_flag", StringType(), True),
    StructField("pu_location_id", IntegerType(), True),
    StructField("do_location_id", IntegerType(), True),
    StructField("payment_type", IntegerType(), True),
    StructField("fare_amount", DoubleType(), True),
    StructField("extra", DoubleType(), True),
    StructField("mta_tax", DoubleType(), True),
    StructField("tip_amount", DoubleType(), True),
    StructField("tolls_amount", DoubleType(), True),
    StructField("improvement_surcharge", DoubleType(), True),
    StructField("total_amount", DoubleType(), True),
    StructField("congestion_surcharge", DoubleType(), True),
    StructField("trip_id", StringType(), True),
    StructField("site_id", StringType(), True),
    StructField("source", StringType(), True),
    StructField("schema_version", IntegerType(), True),
])

CANONICAL_FIELD_TYPES = {
    field.name: field.dataType
    for field in TRIP_SCHEMA.fields
    if field.name != "ingest_ts"
}


# ============================================================
# ISO-8601 parsing
# datetime.fromisoformat handles the optional fractional-seconds
# part gracefully (unlike a fixed Spark timestampFormat pattern),
# which matters because the producer's shift is computed from
# pd.Timestamp.now() and usually carries microseconds.
# ============================================================

@F.udf(returnType=TimestampType())
def parse_iso_timestamp(value):
    if value is None:
        return None
    return datetime.fromisoformat(value)


# ============================================================
# Transformation (Kafka-agnostic: takes a "value" string column)
# ============================================================

def parse_events(raw: DataFrame) -> DataFrame:
    """
    raw must have a string column named "value" holding the JSON
    payload published by the producer. Returns the canonical
    DataFrame, with ingest_ts stamped and columns in TRIP_SCHEMA
    order.
    """
    parsed = raw.select(
        F.from_json(F.col("value"), EVENT_SCHEMA).alias("event")
    ).select("event.*")

    parsed = parsed.withColumn(
        "pickup_datetime", parse_iso_timestamp(F.col("pickup_datetime"))
    )
    parsed = parsed.withColumn(
        "dropoff_datetime", parse_iso_timestamp(F.col("dropoff_datetime"))
    )

    for name, data_type in CANONICAL_FIELD_TYPES.items():
        if name in ("pickup_datetime", "dropoff_datetime"):
            continue
        parsed = parsed.withColumn(name, F.col(name).cast(data_type))

    parsed = parsed.withColumn("ingest_ts", F.current_timestamp())

    return parsed.select(*[field.name for field in TRIP_SCHEMA.fields])


# ============================================================
# Main (Kafka I/O)
# ============================================================

def validate_configuration() -> None:
    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )


def main() -> None:
    validate_configuration()

    spark = (
        SparkSession.builder
        .appName(f"stream-bronze-{SITE_ID}")
        .getOrCreate()
    )

    print()
    print("========================================")
    print("Streaming ingestion -> Bronze")
    print("========================================")
    print(f"Site:            {SITE_ID}")
    print(f"Kafka:           {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic:           {KAFKA_TOPIC}")
    print(f"Bronze path:     {BRONZE_PATH}")
    print(f"Checkpoint path: {CHECKPOINT_PATH}")

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest")
        .load()
        .selectExpr("CAST(value AS STRING) AS value")
    )

    events = parse_events(raw)

    query = (
        events.writeStream
        .format("parquet")
        .option("path", BRONZE_PATH)
        .option("checkpointLocation", CHECKPOINT_PATH)
        .partitionBy("site_id", "source")
        .outputMode("append")
        .trigger(processingTime=f"{TRIGGER_INTERVAL_SECONDS} seconds")
        .start()
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()
