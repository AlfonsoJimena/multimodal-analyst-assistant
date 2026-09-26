"""
M3 - Federated accuracy vs a centralised computation (issue #68, restriction E2).

E2 asks for "unified answers combining the results of the different
locations". M3 checks that the federated answer (3 site pipelines ->
site_api -> coordinator) is EXACTLY what a single centralised computation
over all the raw data would give.

Reference ("oracle"): recomputed here in plain Python from
data/prepared/<site>/*.csv -- no Spark, no Postgres -- applying the rules
documented in src/common/cleaning.py and gold.py (dedup by trip_id,
quarantine rules, cancelled trips excluded from Gold). Money is summed
as Decimal, so counts and money sums must match with zero error.

What is compared (tests/results/m3_accuracy.md):
  - each site_api against the reference for that site;
  - the coordinator against the reference for the three sites together;
  - zone and payment: key by key;
  - hourly and daily: historical keys (original 2020 timestamps) key by
    key, realtime rows by totals only, because the producer shifts
    realtime timestamps to "now";
  - coordinator averages: must equal sum / count of the combined data.

It also measures the error the design avoids: averaging each site's own
average ("average of averages") instead of sum / count.
"""

import csv
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx
import pytest

from tests.conftest import COORDINATOR_URLS, PART2_DIR, SITE_API_URLS, SITES, write_results


PREPARED_DIR = PART2_DIR / "data" / "prepared"

MONEY_COLUMNS = [
    "fare_amount", "extra", "mta_tax", "tip_amount",
    "tolls_amount", "improvement_surcharge", "total_amount", "congestion_surcharge",
]
REQUIRED_FIELDS = [
    "trip_id", "site_id", "source", "schema_version",
    "pickup_datetime", "dropoff_datetime", "pu_location_id", "do_location_id",
]
CANCELLATION_PAYMENT_TYPES = {3, 4}
MAX_TRIP_DURATION_MINUTES = 180
MAX_PASSENGER_COUNT = 9

DISTANCE_REL_TOLERANCE = 1e-9
AVERAGE_TOLERANCE = Decimal("1e-9")


# ============================================================
# Reference implementation (independent of Spark)
# ============================================================

def _int(value):
    return None if value in ("", None) else int(float(value))


def _decimal(value):
    return None if value in ("", None) else Decimal(value)


def _float(value):
    return None if value in ("", None) else float(value)


def _timestamp(value):
    return None if value in ("", None) else datetime.fromisoformat(value)


@dataclass
class Trip:
    raw: dict
    source: str
    pickup: datetime
    dropoff: datetime
    pu_location_id: int
    payment_type: int
    passenger_count: int
    trip_distance: float
    money: dict


def parse_trip(row: dict) -> Trip:
    return Trip(
        raw=row,
        source=row.get("source", ""),
        pickup=_timestamp(row.get("pickup_datetime")),
        dropoff=_timestamp(row.get("dropoff_datetime")),
        pu_location_id=_int(row.get("pu_location_id")),
        payment_type=_int(row.get("payment_type")),
        passenger_count=_int(row.get("passenger_count")),
        trip_distance=_float(row.get("trip_distance")),
        money={c: _decimal(row.get(c)) for c in MONEY_COLUMNS},
    )


def classify(trip: Trip) -> str:
    """
    'valid', 'cancelled' or 'quarantine', mirroring cleaning.py. A
    comparison against a missing value never flags a row (as in Spark,
    where it evaluates to null); the one case where that matters for
    Gold -- a negative amount with no payment_type -- leaves is_cancelled
    null, which gold.py's filter also drops, so it is 'cancelled' here.
    """
    if any(trip.raw.get(f) in ("", None) for f in REQUIRED_FIELDS):
        return "quarantine"

    negative = any(v is not None and v < 0 for v in trip.money.values())
    cancellation = trip.payment_type in CANCELLATION_PAYMENT_TYPES

    duration_min = (trip.dropoff - trip.pickup).total_seconds() / 60
    rules = [
        trip.dropoff <= trip.pickup,
        duration_min > MAX_TRIP_DURATION_MINUTES,
        trip.trip_distance is not None and trip.trip_distance < 0,
        trip.passenger_count is not None
        and not 0 <= trip.passenger_count <= MAX_PASSENGER_COUNT,
        negative and trip.payment_type is not None and not cancellation,
    ]
    if any(rules):
        return "quarantine"
    if negative:
        return "cancelled"
    return "valid"


def gold_trips(rows: list[dict]) -> list[Trip]:
    """Trips that must end up in Gold: deduplicated, valid, not cancelled."""
    seen = set()
    result = []
    for row in rows:
        if row["trip_id"] in seen:
            continue
        seen.add(row["trip_id"])
        trip = parse_trip(row)
        if classify(trip) == "valid":
            result.append(trip)
    return result


@dataclass
class Aggregate:
    trip_count: int = 0
    sum_fare_amount: Decimal = Decimal("0")
    sum_trip_distance: float = 0.0
    sum_tip_amount: Decimal = Decimal("0")
    sum_total_amount: Decimal = Decimal("0")

    def add(self, trip: Trip) -> None:
        self.trip_count += 1
        self.sum_fare_amount += trip.money["fare_amount"] or 0
        self.sum_trip_distance += trip.trip_distance or 0.0
        self.sum_tip_amount += trip.money["tip_amount"] or 0
        self.sum_total_amount += trip.money["total_amount"] or 0

    def merge(self, other: "Aggregate") -> None:
        self.trip_count += other.trip_count
        self.sum_fare_amount += other.sum_fare_amount
        self.sum_trip_distance += other.sum_trip_distance
        self.sum_tip_amount += other.sum_tip_amount
        self.sum_total_amount += other.sum_total_amount


KEY_FUNCTIONS = {
    "/metrics/hourly": ("trip_hour", lambda t: t.pickup.replace(minute=0, second=0, microsecond=0)),
    "/metrics/daily": ("trip_date", lambda t: t.pickup.date()),
    "/metrics/zone": ("pu_location_id", lambda t: t.pu_location_id),
    "/metrics/payment": ("payment_type", lambda t: t.payment_type),
}
TIME_PATHS = {"/metrics/hourly", "/metrics/daily"}


def aggregate(trips: list[Trip], key_fn) -> dict:
    result = defaultdict(Aggregate)
    for trip in trips:
        result[key_fn(trip)].add(trip)
    return dict(result)


def load_site_rows(site: str) -> list[dict]:
    rows = []
    for source in ("historical", "realtime"):
        path = PREPARED_DIR / site / f"{source}.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


# ============================================================
# Unit tests - the reference itself (no Docker)
# ============================================================

def _row(**overrides) -> dict:
    row = {
        "trip_id": "t1", "site_id": "central", "source": "historical", "schema_version": "1",
        "vendor_id": "1", "pickup_datetime": "2020-01-01 10:00:00",
        "dropoff_datetime": "2020-01-01 10:20:00", "passenger_count": "1",
        "trip_distance": "2.5", "ratecode_id": "1", "store_and_fwd_flag": "N",
        "pu_location_id": "138", "do_location_id": "236", "payment_type": "1",
        "fare_amount": "10.00", "extra": "0.5", "mta_tax": "0.5", "tip_amount": "2.00",
        "tolls_amount": "0", "improvement_surcharge": "0.3", "total_amount": "13.30",
        "congestion_surcharge": "0",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, "valid"),
        ({"passenger_count": "0"}, "valid"),  # kept on purpose (cleaning.py)
        ({"fare_amount": "-10.00", "payment_type": "3"}, "cancelled"),
        ({"fare_amount": "-10.00", "payment_type": "4"}, "cancelled"),
        ({"fare_amount": "-10.00", "payment_type": "1"}, "quarantine"),
        ({"dropoff_datetime": "2020-01-01 10:00:00"}, "quarantine"),
        ({"dropoff_datetime": "2020-01-01 13:01:00"}, "quarantine"),  # > 180 min
        ({"trip_distance": "-1"}, "quarantine"),
        ({"passenger_count": "10"}, "quarantine"),
        ({"pu_location_id": ""}, "quarantine"),
        ({"passenger_count": ""}, "valid"),  # null comparison never flags
    ],
)
def test_reference_classifies_like_cleaning_rules(overrides, expected):
    assert classify(parse_trip(_row(**overrides))) == expected


def test_reference_deduplicates_and_excludes_cancelled_from_gold():
    rows = [
        _row(trip_id="a"),
        _row(trip_id="a"),  # duplicate
        _row(trip_id="b", fare_amount="-5.00", payment_type="3"),  # cancelled
        _row(trip_id="c", trip_distance="-1"),  # quarantined
        _row(trip_id="d"),
    ]
    assert [t.raw["trip_id"] for t in gold_trips(rows)] == ["a", "d"]


def test_reference_sums_money_exactly():
    rows = [_row(trip_id=str(i), fare_amount="0.10") for i in range(10)]
    (agg,) = aggregate(gold_trips(rows), lambda t: "all").values()
    assert agg.sum_fare_amount == Decimal("1.00")  # a float sum would give 0.9999999999999999


@pytest.mark.skipif(shutil.which("java") is None, reason="needs Java for a local Spark session")
def test_reference_agrees_with_spark_cleaning():
    """
    Cross-check: the reference and cleaning.py (the code the pipeline
    runs) select exactly the same trips, so any M3 mismatch comes from
    the distributed pipeline, not from the reference.
    """
    if not PREPARED_DIR.exists():
        pytest.skip("data/prepared/ not found")

    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    from src.common.cleaning import split_valid_quarantine
    from src.common.schema import TRIP_SCHEMA

    spark = SparkSession.builder.master("local[1]").appName("m3-oracle").getOrCreate()
    try:
        rows = [row for site in SITES for row in load_site_rows(site)]
        df = spark.read.option("header", True).csv(
            [str(PREPARED_DIR / s / f"{src}.csv") for s in SITES for src in ("historical", "realtime")]
        )
        for field in TRIP_SCHEMA.fields:
            if field.name in df.columns:
                df = df.withColumn(field.name, F.col(field.name).cast(field.dataType))
        valid, _ = split_valid_quarantine(df)
        spark_gold = {r.trip_id for r in valid.filter(~F.col("is_cancelled")).select("trip_id").collect()}
    finally:
        spark.stop()

    assert {t.raw["trip_id"] for t in gold_trips(rows)} == spark_gold


# ============================================================
# Integration - deployed pipeline vs reference (pytest --integration)
# ============================================================

def _parse_key(path: str, value):
    if path == "/metrics/hourly":
        return datetime.fromisoformat(value)
    if path == "/metrics/daily":
        return date.fromisoformat(value)
    return value


def _observed(rows: list[dict], path: str) -> dict:
    key_name = KEY_FUNCTIONS[path][0]
    result = {}
    for row in rows:
        result[_parse_key(path, row[key_name])] = Aggregate(
            trip_count=row["trip_count"],
            sum_fare_amount=Decimal(row["sum_fare_amount"]),
            sum_trip_distance=float(row["sum_trip_distance"]),
            sum_tip_amount=Decimal(row["sum_tip_amount"]),
            sum_total_amount=Decimal(row["sum_total_amount"]),
        )
    return result


def _differences(expected: Aggregate, observed: Aggregate) -> list[str]:
    diffs = []
    for field in ("trip_count", "sum_fare_amount", "sum_tip_amount", "sum_total_amount"):
        if getattr(expected, field) != getattr(observed, field):
            diffs.append(f"{field}: esperado {getattr(expected, field)}, obtenido {getattr(observed, field)}")
    e, o = expected.sum_trip_distance, observed.sum_trip_distance
    if abs(e - o) > DISTANCE_REL_TOLERANCE * max(1.0, abs(e)):
        diffs.append(f"sum_trip_distance: esperado {e}, obtenido {o}")
    return diffs


def compare(path: str, reference: list[Trip], observed_rows: list[dict]) -> dict:
    """Key-by-key comparison; realtime rows of time paths compared by totals."""
    key_fn = KEY_FUNCTIONS[path][1]
    observed = _observed(observed_rows, path)
    mismatches = []

    if path in TIME_PATHS:
        expected = aggregate([t for t in reference if t.source == "historical"], key_fn)
        realtime_expected = Aggregate()
        for trip in reference:
            if trip.source == "realtime":
                realtime_expected.add(trip)
        realtime_observed = Aggregate()
        for key in set(observed) - set(expected):
            realtime_observed.merge(observed.pop(key))
        diffs = _differences(realtime_expected, realtime_observed)
        if diffs:
            mismatches.append({"key": "realtime (totales)", "diffs": diffs})
    else:
        expected = aggregate(reference, key_fn)

    for key in sorted(set(expected) | set(observed), key=str):
        if key not in observed:
            mismatches.append({"key": str(key), "diffs": ["falta en la respuesta"]})
        elif key not in expected:
            mismatches.append({"key": str(key), "diffs": ["no existe en la referencia"]})
        else:
            diffs = _differences(expected[key], observed[key])
            if diffs:
                mismatches.append({"key": str(key), "diffs": diffs})

    return {
        "path": path,
        "keys_compared": len(set(expected) | set(observed)),
        "trips_expected": sum(t.trip_count for t in expected.values())
        + (realtime_expected.trip_count if path in TIME_PATHS else 0),
        "trips_observed": sum(r["trip_count"] for r in observed_rows),
        "mismatches": mismatches,
    }


def _get(url: str, path: str):
    response = httpx.get(f"{url}{path}", timeout=15)
    response.raise_for_status()
    return response.json()


@pytest.fixture(scope="module")
def reference():
    if not PREPARED_DIR.exists():
        pytest.skip("data/prepared/ not found: run `python -m scripts.prepare_data` first")
    return {site: gold_trips(load_site_rows(site)) for site in SITES}


@pytest.fixture(scope="module")
def observed(deployment_up):
    sites = {site: {p: _get(SITE_API_URLS[site], p) for p in KEY_FUNCTIONS} for site in SITES}
    coordinator = {p: _get(COORDINATOR_URLS["central"], p) for p in KEY_FUNCTIONS}
    return {"sites": sites, "coordinator": coordinator}


@pytest.fixture(scope="module")
def comparisons(reference, observed):
    all_trips = [t for site in SITES for t in reference[site]]
    return {
        "sites": {
            site: [compare(p, reference[site], observed["sites"][site][p]) for p in KEY_FUNCTIONS]
            for site in SITES
        },
        "coordinator": [
            compare(p, all_trips, observed["coordinator"][p]["data"]) for p in KEY_FUNCTIONS
        ],
    }


def average_of_averages(reference: dict) -> list[dict]:
    """The error the 'combinable aggregates' design avoids, on real data."""
    rows = []
    for label, key_fn in (("global", lambda t: "todas"), ("por método de pago", lambda t: t.payment_type)):
        per_site = {site: aggregate(reference[site], key_fn) for site in SITES}
        keys = set().union(*per_site.values())
        for key in sorted(keys, key=str):
            parts = [per_site[s][key] for s in SITES if key in per_site[s]]
            if len(parts) < 2:
                continue  # nothing to combine
            count = sum(p.trip_count for p in parts)
            correct = sum(p.sum_fare_amount for p in parts) / count
            naive = sum(p.sum_fare_amount / p.trip_count for p in parts) / len(parts)
            rows.append({
                "grupo": f"{label}: {key}",
                "viajes_por_sede": [p.trip_count for p in parts],
                "media_correcta": float(correct),
                "media_de_medias": float(naive),
                "error_relativo": float(abs(naive - correct) / correct) if correct else 0.0,
            })
    return rows


def _markdown(comparisons: dict, observed: dict, avg_rows: list[dict]) -> str:
    lines = [
        "# M3 · Exactitud federada frente a cálculo centralizado",
        "",
        "Referencia: cálculo centralizado en Python (sin Spark) sobre `data/prepared/`, con las "
        "reglas de `cleaning.py`. Conteos y sumas de dinero en `Decimal`: la diferencia admitida es 0.",
        "",
        "| Origen | Endpoint | Claves comparadas | Viajes esperados | Viajes obtenidos | Claves con diferencias |",
        "|---|---|---|---|---|---|",
    ]
    for site, results in comparisons["sites"].items():
        for r in results:
            lines.append(
                f"| {site} | `{r['path']}` | {r['keys_compared']} | {r['trips_expected']} | "
                f"{r['trips_observed']} | **{len(r['mismatches'])}** |"
            )
    for r in comparisons["coordinator"]:
        lines.append(
            f"| coordinador | `{r['path']}` | {r['keys_compared']} | {r['trips_expected']} | "
            f"{r['trips_observed']} | **{len(r['mismatches'])}** |"
        )

    lines += [
        "",
        "## Error que evita el diseño: «media de medias»",
        "",
        "Tarifa media calculada como media de las medias de cada sede, frente a Σ sumas / Σ conteos "
        "(lo que hace el coordinador).",
        "",
        "| Grupo | Viajes por sede | Media correcta | Media de medias | Error relativo |",
        "|---|---|---|---|---|",
    ]
    for row in avg_rows:
        lines.append(
            f"| {row['grupo']} | {', '.join(map(str, row['viajes_por_sede']))} | "
            f"{row['media_correcta']:.4f} | {row['media_de_medias']:.4f} | {row['error_relativo']:.2%} |"
        )

    problems = [
        (origin, r["path"], m)
        for origin, results in list(comparisons["sites"].items()) + [("coordinador", comparisons["coordinator"])]
        for r in results
        for m in r["mismatches"]
    ]
    if problems:
        lines += ["", "## Diferencias encontradas", ""]
        for origin, path, m in problems[:50]:
            lines.append(f"- {origin} `{path}` clave `{m['key']}`: {'; '.join(m['diffs'])}")
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def m3_report(reference, observed, comparisons):
    yield
    avg_rows = average_of_averages(reference)
    path = write_results(
        "m3_accuracy",
        {"comparisons": comparisons, "average_of_averages": avg_rows},
        _markdown(comparisons, observed, avg_rows),
    )
    print(f"\nM3 results written to {path}")


@pytest.mark.integration
def test_m3_coordinator_answer_is_complete(observed, m3_report):
    for path, body in observed["coordinator"].items():
        assert body["partial"] is False, f"{path}: sites_failed={body['sites_failed']}"


@pytest.mark.integration
def test_m3_total_trips_match_reference(reference, observed, m3_report):
    expected = sum(len(trips) for trips in reference.values())
    got = sum(r["trip_count"] for r in observed["coordinator"]["/metrics/payment"]["data"])
    assert got == expected, (
        f"Gold has {got} trips, the reference {expected}. More than expected usually "
        "means the producer was re-run on a loaded site (realtime counted twice); "
        "fewer means part of the data never reached Gold."
    )


@pytest.mark.integration
@pytest.mark.parametrize("site", SITES)
def test_m3_each_site_matches_reference(site, comparisons, m3_report):
    bad = {r["path"]: r["mismatches"][:5] for r in comparisons["sites"][site] if r["mismatches"]}
    assert not bad, bad


@pytest.mark.integration
def test_m3_coordinator_matches_centralised_computation(comparisons, m3_report):
    bad = {r["path"]: r["mismatches"][:5] for r in comparisons["coordinator"] if r["mismatches"]}
    assert not bad, bad


@pytest.mark.integration
def test_m3_coordinator_averages_are_sum_over_count(observed, m3_report):
    for path, body in observed["coordinator"].items():
        for row in body["data"]:
            count = row["trip_count"]
            for field in ("fare_amount", "tip_amount", "total_amount"):
                expected = Decimal(row[f"sum_{field}"]) / count
                assert abs(Decimal(row[f"avg_{field}"]) - expected) <= AVERAGE_TOLERANCE, (path, row)
