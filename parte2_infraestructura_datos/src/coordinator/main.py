"""
Coordinator: combines the 3 sites' Gold aggregates into one answer.

Each endpoint mirrors one of site_api's /metrics/* endpoints, calls
it on all 3 sites via clients.fetch_all_sites(), and merges the
results by summing trip_count and sum_* per matching key (same
trip_hour/trip_date/pu_location_id/payment_type across sites) --
exactly the "combinable aggregate" contract gold.py's docstring
describes. Averages (avg_fare_amount, etc.) are computed here, once,
from the combined sums and counts. This is the ONLY correct place to
compute them: averaging each site's own average would give the wrong
answer (the "average of averages" error gold.py warns about), because
sites can have very different trip volumes.

sites_ok/sites_failed/partial reflect exactly what clients.py saw: a
site that errored or timed out lands in sites_failed and its data is
simply missing from the combined totals, rather than failing the
whole request.

The coordinator is stateless, so it is replicated as-is on every site
(profile "coordinator" in deploy/docker-compose.site.yml, #59). No
instance knows about the others: failover is the caller's job, trying
FAILOVER_ORDER in order (see scripts/coordinator_failover.py).
"""

import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Optional, TypeVar

from fastapi import FastAPI, Query
from pydantic import BaseModel

from src.common.schema import VALID_SITE_IDS
from src.coordinator import clients
from src.coordinator.clients import SiteResult, fetch_all_sites


# ============================================================
# Configuration
# ============================================================

# Site hosting THIS coordinator replica (not the sites it queries --
# every replica queries all three).
SITE_ID = os.getenv("SITE_ID", "central")

# Order in which callers must try the coordinator replicas:
# 1st central (primary), then chamartin, then atocha (backups).
FAILOVER_ORDER = ["central", "chamartin", "atocha"]


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:
    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )

    clients.validate_configuration()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_configuration()
    yield


app = FastAPI(title=f"coordinator-{SITE_ID}", lifespan=lifespan)

T = TypeVar("T")


# ============================================================
# Response models
# ============================================================

class CombinedResponse(BaseModel, Generic[T]):
    sites_ok: list[str]
    sites_failed: list[str]
    partial: bool
    data: list[T]


class HourlyCombined(BaseModel):
    trip_hour: datetime
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal
    avg_fare_amount: Decimal
    avg_trip_distance: float
    avg_tip_amount: Decimal
    avg_total_amount: Decimal


class DailyCombined(BaseModel):
    trip_date: date
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal
    avg_fare_amount: Decimal
    avg_trip_distance: float
    avg_tip_amount: Decimal
    avg_total_amount: Decimal


class ZoneCombined(BaseModel):
    pu_location_id: int
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal
    avg_fare_amount: Decimal
    avg_trip_distance: float
    avg_tip_amount: Decimal
    avg_total_amount: Decimal


class PaymentCombined(BaseModel):
    payment_type: int
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal
    avg_fare_amount: Decimal
    avg_trip_distance: float
    avg_tip_amount: Decimal
    avg_total_amount: Decimal


# ============================================================
# Combining logic
# Shared by all 4 endpoints below -- only the grouping key differs.
# ============================================================

def _empty_bucket(group_key: str, key_value) -> dict:
    return {
        group_key: key_value,
        "trip_count": 0,
        "sum_fare_amount": Decimal("0"),
        "sum_trip_distance": 0.0,
        "sum_tip_amount": Decimal("0"),
        "sum_total_amount": Decimal("0"),
    }


def combine_metric_rows(
    results: list[SiteResult], group_key: str
) -> tuple[list[str], list[str], list[dict]]:
    sites_ok: list[str] = []
    sites_failed: list[str] = []
    merged: dict = {}

    for result in results:
        if not result.ok:
            sites_failed.append(result.site_id)
            continue

        sites_ok.append(result.site_id)

        for row in result.data:
            key_value = row[group_key]
            bucket = merged.setdefault(key_value, _empty_bucket(group_key, key_value))

            bucket["trip_count"] += row["trip_count"]
            bucket["sum_fare_amount"] += Decimal(row["sum_fare_amount"])
            bucket["sum_trip_distance"] += row["sum_trip_distance"]
            bucket["sum_tip_amount"] += Decimal(row["sum_tip_amount"])
            bucket["sum_total_amount"] += Decimal(row["sum_total_amount"])

    combined = [_add_averages(bucket) for bucket in merged.values()]
    return sites_ok, sites_failed, combined


def _add_averages(bucket: dict) -> dict:
    count = bucket["trip_count"]

    bucket["avg_fare_amount"] = bucket["sum_fare_amount"] / count if count else Decimal("0")
    bucket["avg_trip_distance"] = bucket["sum_trip_distance"] / count if count else 0.0
    bucket["avg_tip_amount"] = bucket["sum_tip_amount"] / count if count else Decimal("0")
    bucket["avg_total_amount"] = bucket["sum_total_amount"] / count if count else Decimal("0")

    return bucket


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "site_id": SITE_ID,
        "failover_priority": FAILOVER_ORDER.index(SITE_ID) + 1,
    }


# ============================================================
# Combined metrics endpoints
# ============================================================

@app.get("/metrics/hourly", response_model=CombinedResponse[HourlyCombined])
async def get_combined_hourly(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    params = {}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()

    results = await fetch_all_sites("/metrics/hourly", params)
    sites_ok, sites_failed, data = combine_metric_rows(results, "trip_hour")

    return CombinedResponse(
        sites_ok=sites_ok,
        sites_failed=sites_failed,
        partial=len(sites_failed) > 0,
        data=data,
    )


@app.get("/metrics/daily", response_model=CombinedResponse[DailyCombined])
async def get_combined_daily(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    params = {}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()

    results = await fetch_all_sites("/metrics/daily", params)
    sites_ok, sites_failed, data = combine_metric_rows(results, "trip_date")

    return CombinedResponse(
        sites_ok=sites_ok,
        sites_failed=sites_failed,
        partial=len(sites_failed) > 0,
        data=data,
    )


@app.get("/metrics/zone", response_model=CombinedResponse[ZoneCombined])
async def get_combined_zone(
    pu_location_id: Optional[int] = Query(None),
):
    params = {}
    if pu_location_id is not None:
        params["pu_location_id"] = pu_location_id

    results = await fetch_all_sites("/metrics/zone", params)
    sites_ok, sites_failed, data = combine_metric_rows(results, "pu_location_id")

    return CombinedResponse(
        sites_ok=sites_ok,
        sites_failed=sites_failed,
        partial=len(sites_failed) > 0,
        data=data,
    )


@app.get("/metrics/payment", response_model=CombinedResponse[PaymentCombined])
async def get_combined_payment(
    payment_type: Optional[int] = Query(None),
):
    params = {}
    if payment_type is not None:
        params["payment_type"] = payment_type

    results = await fetch_all_sites("/metrics/payment", params)
    sites_ok, sites_failed, data = combine_metric_rows(results, "payment_type")

    return CombinedResponse(
        sites_ok=sites_ok,
        sites_failed=sites_failed,
        partial=len(sites_failed) > 0,
        data=data,
    )


# ============================================================
# Main (local dev only -- production runs via uvicorn in Dockerfile)
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
