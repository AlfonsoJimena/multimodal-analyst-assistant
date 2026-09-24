"""
Data quality rules shared by the batch and streaming pipelines.

The rules below come from analyzing the 999-row sample provided for
the project (data/raw/rows.csv). Two decisions are deliberately
*not* enforced as rejection rules, documented here so nobody
"fixes" them later without re-reading this analysis:

  - total_amount != sum(fare_amount, extra, mta_tax, tip_amount,
    tolls_amount, improvement_surcharge, congestion_surcharge)
    happens in 369/999 sample rows, almost all VendorID 1, whose
    "extra" field already folds in the congestion surcharge.
    Using this as a rejection rule would discard ~37% of valid data.

  - passenger_count == 0 is kept: the trip still happened.

Negative monetary amounts are only rejected when they are NOT
explained by payment_type 3 (no charge) or 4 (dispute), which is
how the sample's cancelled/disputed trips show up. Those are
flagged with is_cancelled instead of being quarantined.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.common.schema import VALID_SITE_IDS, VALID_SOURCES


# ============================================================
# Configuration
# ============================================================

REQUIRED_FIELDS = [
    "trip_id",
    "site_id",
    "source",
    "schema_version",
    "pickup_datetime",
    "dropoff_datetime",
    "pu_location_id",
    "do_location_id",
]

MONEY_COLUMNS = [
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
]

# payment_type values that legitimately explain a negative amount
# (cancellations / disputes), per the NYC TLC data dictionary.
CANCELLATION_PAYMENT_TYPES = [3, 4]

MAX_TRIP_DURATION_MINUTES = 180
MAX_PASSENGER_COUNT = 9


# ============================================================
# Individual rules
# Each rule returns (condition_column, reason_string).
# condition == True means "this row fails this rule".
# ============================================================

def _rule_missing_required_field(df: DataFrame):
    condition = F.lit(False)
    for field in REQUIRED_FIELDS:
        condition = condition | F.col(field).isNull()
    return condition, "missing_required_field"


def _rule_invalid_enum_value(df: DataFrame):
    condition = (
        (~F.col("site_id").isin(*VALID_SITE_IDS))
        | (~F.col("source").isin(*VALID_SOURCES))
    )
    return condition, "invalid_enum_value"


def _rule_invalid_duration(df: DataFrame):
    condition = F.col("dropoff_datetime") <= F.col("pickup_datetime")
    return condition, "invalid_duration"


def _rule_duration_too_long(df: DataFrame):
    duration_minutes = (
        F.col("dropoff_datetime").cast("long")
        - F.col("pickup_datetime").cast("long")
    ) / 60.0
    condition = duration_minutes > MAX_TRIP_DURATION_MINUTES
    return condition, "duration_too_long"


def _rule_negative_distance(df: DataFrame):
    condition = F.col("trip_distance") < 0
    return condition, "negative_distance"


def _rule_invalid_passenger_count(df: DataFrame):
    condition = (
        (F.col("passenger_count") < 0)
        | (F.col("passenger_count") > MAX_PASSENGER_COUNT)
    )
    return condition, "invalid_passenger_count"


def _rule_unexplained_negative_amount(df: DataFrame):
    is_negative = F.lit(False)
    for column in MONEY_COLUMNS:
        is_negative = is_negative | (F.col(column) < 0)

    is_cancellation = F.col("payment_type").isin(*CANCELLATION_PAYMENT_TYPES)

    condition = is_negative & (~is_cancellation)
    return condition, "unexplained_negative_amount"


RULES = [
    _rule_missing_required_field,
    _rule_invalid_enum_value,
    _rule_invalid_duration,
    _rule_duration_too_long,
    _rule_negative_distance,
    _rule_invalid_passenger_count,
    _rule_unexplained_negative_amount,
]


# ============================================================
# Public API
# ============================================================

def flag_cancellations(df: DataFrame) -> DataFrame:
    """
    Marks trips whose negative amounts are explained by a
    cancellation/dispute payment_type, so they are NOT sent to
    quarantine later. These are legitimate business events, not
    data quality errors.
    """
    is_negative = F.lit(False)
    for column in MONEY_COLUMNS:
        is_negative = is_negative | (F.col(column) < 0)

    is_cancellation = F.col("payment_type").isin(*CANCELLATION_PAYMENT_TYPES)

    return df.withColumn("is_cancelled", is_negative & is_cancellation)


def apply_quarantine_rules(df: DataFrame) -> DataFrame:
    """
    Adds two columns:
      - quarantine_reasons: array<string> with every rule this row
        failed (empty array if none).
      - is_valid: boolean, True when quarantine_reasons is empty.
    """
    reason_expressions = [
        F.when(condition, F.lit(reason))
        for condition, reason in (rule(df) for rule in RULES)
    ]

    df = df.withColumn("quarantine_reasons", F.array(*reason_expressions))
    df = df.withColumn(
        "quarantine_reasons",
        F.expr("filter(quarantine_reasons, x -> x is not null)"),
    )
    df = df.withColumn("is_valid", F.size("quarantine_reasons") == 0)

    return df


def drop_duplicate_trips(df: DataFrame) -> DataFrame:
    """
    Deduplicates by trip_id. Needed because streaming micro-batches
    can be reprocessed after a failure, and prepare_data.py already
    warns that exact duplicate source rows are possible.
    """
    return df.dropDuplicates(["trip_id"])


def split_valid_quarantine(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    """
    Runs the full cleaning pipeline and returns (valid_df, quarantine_df).

    valid_df keeps the canonical schema columns plus is_cancelled.
    quarantine_df keeps the original row plus rejection_reason and
    rejected_at, matching sql/quarantine.sql (silver_rejected).
    """
    df = drop_duplicate_trips(df)
    df = flag_cancellations(df)
    df = apply_quarantine_rules(df)

    valid_df = df.filter(F.col("is_valid")).drop(
        "quarantine_reasons", "is_valid"
    )

    quarantine_df = (
        df.filter(~F.col("is_valid"))
        .withColumn("rejection_reason", F.array_join("quarantine_reasons", ";"))
        .withColumn("rejected_at", F.current_timestamp())
        .drop("quarantine_reasons", "is_valid")
    )

    return valid_df, quarantine_df


if __name__ == "__main__":
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .appName("cleaning-smoke-test")
        .master("local[*]")
        .getOrCreate()
    )

    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv("data/prepared/central/historical.csv")
    )

    valid_df, quarantine_df = split_valid_quarantine(df)

    print()
    print("========================================")
    print("Cleaning smoke test (data/prepared/central/historical.csv)")
    print("========================================")
    print(f"Input rows:      {df.count():,}")
    print(f"Valid rows:      {valid_df.count():,}")
    print(f"Quarantined:     {quarantine_df.count():,}")
    print(f"Cancelled (kept):{valid_df.filter('is_cancelled').count():>6,}")
    print()
    print("Quarantine reasons breakdown:")
    (
        quarantine_df
        .withColumn("reason", F.explode(F.split("rejection_reason", ";")))
        .groupBy("reason")
        .count()
        .orderBy(F.desc("count"))
        .show(truncate=False)
    )

    spark.stop()
