"""
Prepare the original NYC Taxi dataset for the distributed deployment.

Responsibilities:
1. Rename the original CSV columns to the canonical schema.
2. Generate a deterministic trip_id using SHA-256.
3. Assign each trip to a site according to PULocationID % 3.
4. Split each site's data chronologically into:
      - 80% historical
      - 20% realtime
5. Write the six resulting CSV files.

ingest_ts is NOT generated here. It is assigned when each record
enters the processing pipeline.
"""

import hashlib
from pathlib import Path

import pandas as pd

from src.common.schema import (
    CSV_COLUMN_MAPPING,
    SCHEMA_VERSION,
    TRIP_FIELDS,
    VALID_SITE_IDS,
    VALID_SOURCES,
)


# ============================================================
# Configuration
# ============================================================

INPUT_FILE = Path("data/raw/rows.csv")
OUTPUT_DIR = Path("data/prepared")

HISTORICAL_RATIO = 0.80

DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"

SITE_MAPPING = {
    0: "central",
    1: "chamartin",
    2: "atocha",
}


# ============================================================
# Helper functions
# ============================================================

def assign_sites(df: pd.DataFrame) -> pd.Series:
    """
    Assign a physical site according to pu_location_id.

    Rule:
        PULocationID % 3 == 0 -> central
        PULocationID % 3 == 1 -> chamartin
        PULocationID % 3 == 2 -> atocha

    This is a deterministic technical partition. It does not represent
    a geographical equivalence between NYC taxi zones and Madrid sites.
    """

    if df["pu_location_id"].isna().any():
        null_count = df["pu_location_id"].isna().sum()

        raise ValueError(
            f"Cannot assign site: {null_count} rows have null "
            "pu_location_id."
        )

    remainder = df["pu_location_id"].astype(int) % 3

    return remainder.map(SITE_MAPPING)


def generate_trip_ids(df: pd.DataFrame) -> pd.Series:
    """
    Generate a deterministic SHA-256 identifier from the original
    trip fields.

    Metadata fields such as site_id, source, schema_version and
    ingest_ts are deliberately excluded so that the identity of the
    trip does not depend on how or where it is processed.
    """

    missing_fields = [
        field
        for field in TRIP_FIELDS
        if field not in df.columns
    ]

    if missing_fields:
        raise ValueError(
            f"Cannot generate trip_id. Missing fields: {missing_fields}"
        )

    # Convert the trip fields to a stable textual representation.
    canonical = (
        df[TRIP_FIELDS]
        .fillna("")
        .astype(str)
        .agg("|".join, axis=1)
    )

    return canonical.map(
        lambda value: hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()
    )


def validate_input_columns(df: pd.DataFrame) -> None:
    """
    Check that all columns expected from the original CSV exist.
    """

    expected_columns = set(CSV_COLUMN_MAPPING.keys())
    actual_columns = set(df.columns)

    missing = expected_columns - actual_columns

    if missing:
        raise ValueError(
            f"Input CSV is missing columns: {sorted(missing)}"
        )


def validate_output(
    original_count: int,
    outputs: list[pd.DataFrame],
) -> None:
    """
    Perform basic integrity checks after the split.
    """

    combined = pd.concat(outputs, ignore_index=True)

    output_count = len(combined)

    if output_count != original_count:
        raise ValueError(
            "Row count mismatch: "
            f"input={original_count}, output={output_count}"
        )

    # Every row must have the required preparation metadata.
    if combined["trip_id"].isna().any():
        raise ValueError("Null trip_id values found.")

    if combined["site_id"].isna().any():
        raise ValueError("Null site_id values found.")

    if combined["source"].isna().any():
        raise ValueError("Null source values found.")

    if combined["schema_version"].isna().any():
        raise ValueError("Null schema_version values found.")

    # Check allowed values.
    invalid_sites = set(combined["site_id"].unique()) - VALID_SITE_IDS

    if invalid_sites:
        raise ValueError(
            f"Invalid site_id values found: {invalid_sites}"
        )

    invalid_sources = set(combined["source"].unique()) - VALID_SOURCES

    if invalid_sources:
        raise ValueError(
            f"Invalid source values found: {invalid_sources}"
        )

    # A PULocationID must always belong to exactly one site.
    sites_per_location = (
        combined
        .groupby("pu_location_id")["site_id"]
        .nunique()
    )

    if (sites_per_location > 1).any():
        raise ValueError(
            "At least one pu_location_id was assigned "
            "to multiple sites."
        )

    print()
    print("========================================")
    print("Validation")
    print("========================================")
    print(f"Input rows:       {original_count:,}")
    print(f"Output rows:      {output_count:,}")
    print(f"Unique trip IDs:  {combined['trip_id'].nunique():,}")

    duplicate_ids = combined["trip_id"].duplicated().sum()
    print(f"Duplicate IDs:    {duplicate_ids:,}")

    if duplicate_ids > 0:
        print(
            "WARNING: duplicate trip IDs detected. "
            "This can indicate exact duplicate trips in the source dataset."
        )

    print("Site assignment:  OK")
    print("Source values:    OK")
    print("Row conservation: OK")
    print()
    print("Preparation completed successfully.")


# ============================================================
# Main preparation
# ============================================================

def main() -> None:

    print("========================================")
    print("PIDS - Data preparation")
    print("========================================")
    print()

    # --------------------------------------------------------
    # 1. Read original CSV
    # --------------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    print(f"Reading {INPUT_FILE}...")

    df = pd.read_csv(INPUT_FILE)

    original_count = len(df)

    print(f"Loaded {original_count:,} rows.")

    # --------------------------------------------------------
    # 2. Validate original columns
    # --------------------------------------------------------

    validate_input_columns(df)

    # --------------------------------------------------------
    # 3. Rename columns to canonical names
    # --------------------------------------------------------

    print("Applying canonical column names...")

    df = df.rename(columns=CSV_COLUMN_MAPPING)

    # --------------------------------------------------------
    # 4. Parse timestamps
    # --------------------------------------------------------

    print("Parsing timestamps...")

    df["pickup_datetime"] = pd.to_datetime(
        df["pickup_datetime"],
        format=DATE_FORMAT,
        errors="raise",
    )

    df["dropoff_datetime"] = pd.to_datetime(
        df["dropoff_datetime"],
        format=DATE_FORMAT,
        errors="raise",
    )

    # --------------------------------------------------------
    # 5. Generate deterministic trip_id
    # --------------------------------------------------------

    print("Generating SHA-256 trip IDs...")

    df["trip_id"] = generate_trip_ids(df)

    # --------------------------------------------------------
    # 6. Assign physical site
    # --------------------------------------------------------

    print("Assigning sites using PULocationID % 3...")

    df["site_id"] = assign_sites(df)

    # --------------------------------------------------------
    # 7. Add schema version
    # --------------------------------------------------------

    df["schema_version"] = SCHEMA_VERSION

    # --------------------------------------------------------
    # 8. Prepare output directories
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 9. Split each site into historical/realtime
    # --------------------------------------------------------

    generated_outputs = []

    print()
    print("Splitting sites:")
    print()

    for site in SITE_MAPPING.values():

        site_df = (
            df[df["site_id"] == site]
            .sort_values("pickup_datetime")
            .reset_index(drop=True)
        )

        split_index = int(
            len(site_df) * HISTORICAL_RATIO
        )

        historical = (
            site_df
            .iloc[:split_index]
            .copy()
        )

        realtime = (
            site_df
            .iloc[split_index:]
            .copy()
        )

        historical["source"] = "historical"
        realtime["source"] = "realtime"

        site_dir = OUTPUT_DIR / site

        site_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        historical_file = (
            site_dir / "historical.csv"
        )

        realtime_file = (
            site_dir / "realtime.csv"
        )

        historical.to_csv(
            historical_file,
            index=False,
        )

        realtime.to_csv(
            realtime_file,
            index=False,
        )

        generated_outputs.extend(
            [historical, realtime]
        )

        print(
            f"{site:<10} "
            f"total={len(site_df):>9,} | "
            f"historical={len(historical):>9,} | "
            f"realtime={len(realtime):>9,}"
        )

    # --------------------------------------------------------
    # 10. Validate result
    # --------------------------------------------------------

    validate_output(
        original_count,
        generated_outputs,
    )


if __name__ == "__main__":
    main()