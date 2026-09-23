"""
Realtime trip producer.

Reads the realtime CSV assigned to one site, shifts the original
timestamps to the current execution time and publishes the trips
to Kafka while preserving their relative temporal spacing.

Configuration is provided through environment variables.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

from src.common.schema import (
    SCHEMA_VERSION,
    VALID_SITE_IDS,
)


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

REALTIME_FILE = Path(
    os.getenv(
        "REALTIME_FILE",
        f"data/prepared/{SITE_ID}/realtime.csv",
    )
)

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "taxi-trips",
)

ACCELERATION_FACTOR = float(
    os.getenv(
        "ACCELERATION_FACTOR",
        "60",
    )
)


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:

    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )

    if ACCELERATION_FACTOR <= 0:
        raise ValueError(
            "ACCELERATION_FACTOR must be greater than 0."
        )

    if not REALTIME_FILE.exists():
        raise FileNotFoundError(
            f"Realtime file not found: {REALTIME_FILE}"
        )


# ============================================================
# Kafka
# ============================================================

def create_kafka_producer() -> KafkaProducer:
    """
    Create the Kafka producer used to publish trip events.
    """

    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(
            value
        ).encode("utf-8"),
        key_serializer=lambda key: key.encode("utf-8"),
        acks="all",
    )


# ============================================================
# Data loading
# ============================================================

def load_realtime_data() -> pd.DataFrame:

    df = pd.read_csv(
        REALTIME_FILE,
        parse_dates=[
            "pickup_datetime",
            "dropoff_datetime",
        ],
    )

    if df.empty:
        raise ValueError(
            f"Realtime file is empty: {REALTIME_FILE}"
        )

    if "trip_id" not in df.columns:
        raise ValueError(
            "Realtime data does not contain trip_id."
        )

    if "site_id" not in df.columns:
        raise ValueError(
            "Realtime data does not contain site_id."
        )

    if "source" not in df.columns:
        raise ValueError(
            "Realtime data does not contain source."
        )

    # This producer must only process data belonging to its site.
    invalid_sites = set(df["site_id"].unique()) - {SITE_ID}

    if invalid_sites:
        raise ValueError(
            f"Realtime file contains data from other sites: "
            f"{invalid_sites}"
        )

    invalid_sources = set(df["source"].unique()) - {"realtime"}

    if invalid_sources:
        raise ValueError(
            f"Expected source='realtime', found: "
            f"{invalid_sources}"
        )

    return (
        df
        .sort_values("pickup_datetime")
        .reset_index(drop=True)
    )


# ============================================================
# Timestamp simulation
# ============================================================

def calculate_time_shift(
    first_pickup: pd.Timestamp,
) -> pd.Timedelta:
    """
    Calculate the shift required to move the first trip to now.

    The same shift is later applied to both pickup and dropoff
    timestamps, preserving trip duration.
    """

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)

    return now - first_pickup


def shift_timestamps(
    row: pd.Series,
    time_shift: pd.Timedelta,
) -> dict:
    """
    Convert a dataframe row to an event and shift its timestamps.
    """

    event = row.to_dict()

    shifted_pickup = (
        row["pickup_datetime"] + time_shift
    )

    shifted_dropoff = (
        row["dropoff_datetime"] + time_shift
    )

    event["pickup_datetime"] = (
        shifted_pickup.isoformat()
    )

    event["dropoff_datetime"] = (
        shifted_dropoff.isoformat()
    )

    # Keep schema version explicitly in every event.
    event["schema_version"] = SCHEMA_VERSION

    return event


# ============================================================
# Streaming simulation
# ============================================================

def publish_trips(
    producer: KafkaProducer,
    df: pd.DataFrame,
) -> None:

    first_pickup = df.iloc[0]["pickup_datetime"]

    time_shift = calculate_time_shift(
        first_pickup
    )

    previous_pickup = first_pickup

    print()
    print("========================================")
    print("Realtime simulation")
    print("========================================")
    print(f"Site:                 {SITE_ID}")
    print(f"Trips:                {len(df):,}")
    print(f"Kafka:                {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Topic:                {KAFKA_TOPIC}")
    print(f"Acceleration factor:  {ACCELERATION_FACTOR}x")
    print(f"Original first trip:  {first_pickup}")
    print(f"Time shift:           {time_shift}")
    print()

    for index, row in df.iterrows():

        current_pickup = row["pickup_datetime"]

        # Preserve the temporal distance between consecutive trips,
        # accelerated by the configured factor.
        if index > 0:

            original_delay = (
                current_pickup - previous_pickup
            ).total_seconds()

            simulated_delay = (
                original_delay / ACCELERATION_FACTOR
            )

            if simulated_delay > 0:
                time.sleep(simulated_delay)

        event = shift_timestamps(
            row,
            time_shift,
        )

        producer.send(
            KAFKA_TOPIC,
            key=event["trip_id"],
            value=event,
        )

        print(
            f"[{index + 1}/{len(df)}] "
            f"{event['trip_id'][:12]}... "
            f"pickup={event['pickup_datetime']}"
        )

        previous_pickup = current_pickup

    # Ensure every buffered event has been delivered.
    producer.flush()


# ============================================================
# Main
# ============================================================

def main() -> None:

    validate_configuration()

    print("Loading realtime data...")

    df = load_realtime_data()

    producer = create_kafka_producer()

    try:
        publish_trips(
            producer,
            df,
        )

    finally:
        producer.close()

    print()
    print(
        f"Finished publishing {len(df):,} trips "
        f"for site '{SITE_ID}'."
    )


if __name__ == "__main__":
    main()