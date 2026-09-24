"""
Gold layer: business aggregates computed from Silver valid trips.

Every aggregate here is a COMBINABLE quantity (a count and sums),
never an average or other summary statistic. This is deliberate:
the coordinator (#57/#58) merges partial results from three
independent per-site aggregates, and averaging pre-computed averages
across sites gives a wrong "average of averages" -- in the group's
own architecture review, that error was ~13% on a worked example.
Real averages are computed once, at the coordinator, from the
summed counts and sums this layer provides -- never here.

Each compute_*_metrics() function takes a DataFrame (a single
micro-batch, or the whole Silver dataset for local testing) and
returns the PARTIAL aggregate for just that input. Merging partial
aggregates across micro-batches into running totals is
sink_postgres.py's job (#55), via an upsert
(ON CONFLICT DO UPDATE ... = existing + incoming) -- not this
module's.

Cancelled/disputed trips (is_cancelled=True, set by cleaning.py) are
excluded from every aggregate: an annulled trip should not count
toward revenue or trip-volume metrics. They stay visible in Silver
for anyone who needs them.
"""

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from pyspark.sql.types import BooleanType, StructField, StructType

from src.common.schema import TRIP_SCHEMA, VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

SILVER_PATH = os.getenv("SILVER_PATH", "data/lakehouse/silver")

# Placeholder destination until sink_postgres.py (#55) exists: lets
# every gold table be inspected/tested locally as Parquet before the
# real Postgres upsert is wired in. sink_postgres.py will reuse the
# compute_*_metrics functions below and replace this write path.
GOLD_PATH = os.getenv("GOLD_PATH", "data/lakehouse/gold")

CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    f"data/checkpoints/gold/{SITE_ID}",
)

TRIGGER_INTERVAL_SECONDS = int(os.getenv("TRIGGER_INTERVAL_SECONDS", "10"))
RUN_MODE = os.getenv("RUN_MODE", "continuous")

# Silver's schema is the canonical TRIP_SCHEMA plus is_cancelled,
# added by cleaning.flag_cancellations() before the valid/quarantine
# split. Needed explicitly because Spark cannot infer a schema for a
# streaming source.
SILVER_SCHEMA = StructType(
    TRIP_SCHEMA.fields + [StructField("is_cancelled", BooleanType(), True)]
)

MONEY_SUM_COLUMNS = [
    "fare_amount",
    "trip_distance",
    "tip_amount",
    "total_amount",
]


# ============================================================
# Shared aggregation building blocks
# ============================================================

def _exclude_cancelled(df: DataFrame) -> DataFrame:
    if "is_cancelled" in df.columns:
        return df.filter(~F.col("is_cancelled"))
    return df


def _combinable_aggregates():
    """
    trip_count plus one sum_<column> per monetary/distance column.
    The sum_ prefix is a reminder to whoever reads a gold table
    (site_api, the coordinator) that these values are meant to be
    added together, not averaged directly.
    """
    aggregates = [F.count(F.lit(1)).alias("trip_count")]
    for column in MONEY_SUM_COLUMNS:
        aggregates.append(F.sum(column).alias(f"sum_{column}"))
    return aggregates


# ============================================================
# Gold tables
# ============================================================

def compute_hourly_metrics(df: DataFrame) -> DataFrame:
    df = _exclude_cancelled(df)
    return (
        df.withColumn(
            "trip_hour", F.date_trunc("hour", F.col("pickup_datetime"))
        )
        .groupBy("site_id", "trip_hour")
        .agg(*_combinable_aggregates())
    )


def compute_daily_metrics(df: DataFrame) -> DataFrame:
    df = _exclude_cancelled(df)
    return (
        df.withColumn("trip_date", F.to_date(F.col("pickup_datetime")))
        .groupBy("site_id", "trip_date")
        .agg(*_combinable_aggregates())
    )


def compute_zone_metrics(df: DataFrame) -> DataFrame:
    df = _exclude_cancelled(df)
    return df.groupBy("site_id", "pu_location_id").agg(
        *_combinable_aggregates()
    )


def compute_payment_metrics(df: DataFrame) -> DataFrame:
    df = _exclude_cancelled(df)
    return df.groupBy("site_id", "payment_type").agg(
        *_combinable_aggregates()
    )


GOLD_TABLES = {
    "hourly_metrics": compute_hourly_metrics,
    "daily_metrics": compute_daily_metrics,
    "zone_metrics": compute_zone_metrics,
    "payment_metrics": compute_payment_metrics,
}


# ============================================================
# Per-micro-batch processing
# ============================================================

def process_batch(batch_df: DataFrame, batch_id: int) -> None:
    batch_df = batch_df.filter(batch_df.site_id == SITE_ID)
    batch_df.persist()

    summary = []

    for table_name, compute_fn in GOLD_TABLES.items():
        table_df = compute_fn(batch_df)

        (
            table_df.write
            .mode("append")
            .parquet(f"{GOLD_PATH}/{table_name}")
        )

        summary.append(f"{table_name}={table_df.count():,} rows")

    print(f"[batch {batch_id}] site={SITE_ID} " + " | ".join(summary))

    batch_df.unpersist()


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
# Main
# ============================================================

def main() -> None:
    validate_configuration()

    spark = (
        SparkSession.builder
        .appName(f"gold-{SITE_ID}")
        .getOrCreate()
    )

    print()
    print("========================================")
    print("Silver -> Gold")
    print("========================================")
    print(f"Site:            {SITE_ID}")
    print(f"Silver path:     {SILVER_PATH}")
    print(f"Gold path:       {GOLD_PATH}")
    print(f"Run mode:        {RUN_MODE}")

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
