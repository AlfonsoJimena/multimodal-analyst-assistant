from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    TimestampType,
    DoubleType,
    DecimalType,
)


# ============================================================
# Schema metadata
# ============================================================

SCHEMA_VERSION = 1

VALID_SITE_IDS = {
    "central",
    "chamartin",
    "atocha",
}

VALID_SOURCES = {
    "historical",
    "realtime",
}


# ============================================================
# Mapping from the original NYC Taxi dataset to the
# canonical schema used internally by the platform
# ============================================================

CSV_COLUMN_MAPPING = {
    "VendorID": "vendor_id",
    "tpep_pickup_datetime": "pickup_datetime",
    "tpep_dropoff_datetime": "dropoff_datetime",
    "passenger_count": "passenger_count",
    "trip_distance": "trip_distance",
    "RatecodeID": "ratecode_id",
    "store_and_fwd_flag": "store_and_fwd_flag",
    "PULocationID": "pu_location_id",
    "DOLocationID": "do_location_id",
    "payment_type": "payment_type",
    "fare_amount": "fare_amount",
    "extra": "extra",
    "mta_tax": "mta_tax",
    "tip_amount": "tip_amount",
    "tolls_amount": "tolls_amount",
    "improvement_surcharge": "improvement_surcharge",
    "total_amount": "total_amount",
    "congestion_surcharge": "congestion_surcharge",
}


# ============================================================
# Original trip fields
# Used, among other things, to generate the deterministic
# trip_id before the realtime producer modifies timestamps.
# ============================================================

TRIP_FIELDS = [
    "vendor_id",
    "pickup_datetime",
    "dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "ratecode_id",
    "store_and_fwd_flag",
    "pu_location_id",
    "do_location_id",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
]


# ============================================================
# Canonical Spark schema
# ============================================================

TRIP_SCHEMA = StructType([
    # Metadata
    StructField("trip_id", StringType(), False),
    StructField("site_id", StringType(), False),
    StructField("source", StringType(), False),
    StructField("schema_version", IntegerType(), False),
    StructField("ingest_ts", TimestampType(), False),

    # Trip information
    StructField("vendor_id", IntegerType(), True),
    StructField("pickup_datetime", TimestampType(), False),
    StructField("dropoff_datetime", TimestampType(), False),
    StructField("passenger_count", IntegerType(), True),
    StructField("trip_distance", DoubleType(), True),
    StructField("ratecode_id", IntegerType(), True),
    StructField("store_and_fwd_flag", StringType(), True),
    StructField("pu_location_id", IntegerType(), True),
    StructField("do_location_id", IntegerType(), True),

    # Payment information
    StructField("payment_type", IntegerType(), True),
    StructField("fare_amount", DecimalType(12, 2), True),
    StructField("extra", DecimalType(12, 2), True),
    StructField("mta_tax", DecimalType(12, 2), True),
    StructField("tip_amount", DecimalType(12, 2), True),
    StructField("tolls_amount", DecimalType(12, 2), True),
    StructField("improvement_surcharge", DecimalType(12, 2), True),
    StructField("total_amount", DecimalType(12, 2), True),
    StructField("congestion_surcharge", DecimalType(12, 2), True),
])



def validate_schema():
    field_names = [field.name for field in TRIP_SCHEMA.fields]

    assert len(field_names) == 23
    assert len(field_names) == len(set(field_names))

    assert "trip_id" in field_names
    assert "site_id" in field_names
    assert "source" in field_names
    assert "schema_version" in field_names
    assert "ingest_ts" in field_names

    assert set(VALID_SITE_IDS) == {"central", "chamartin", "atocha"}
    assert set(VALID_SOURCES) == {"historical", "realtime"}


if __name__ == "__main__":
    validate_schema()

    print("Canonical schema OK")
    print(f"Version: {SCHEMA_VERSION}")
    print(f"Number of fields: {len(TRIP_SCHEMA.fields)}")
    print()

    for field in TRIP_SCHEMA.fields:
        print(
            f"{field.name:<25} "
            f"{str(field.dataType):<20} "
            f"nullable={field.nullable}"
        )

