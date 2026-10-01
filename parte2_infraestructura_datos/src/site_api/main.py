"""
Site API: the only door out of this site's data.

Exposes the Gold aggregates written by sink_postgres.py (sql/init.sql)
and a rejection-reason summary over quarantine (sql/quarantine.sql).
Every response is a COMBINABLE aggregate (trip_count, sum_*, or a
count grouped by reason) -- never a single trip row and never a
pre-computed average. Averages are the coordinator's job (#57/#58),
computed once from the sums this API returns; an average returned
here could not be re-combined across sites without the same
"average of averages" error gold.py's docstring warns about.

Every query filters explicitly on site_id = SITE_ID, even though this
Postgres instance is only ever expected to hold this site's rows --
the same defense-in-depth the producer already applies to its own
input data (producer.py's load_realtime_data), in case that
assumption is ever wrong.
"""

import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from src.common.schema import VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_ID = os.getenv("SITE_ID", "central")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "pids")
POSTGRES_USER = os.getenv("POSTGRES_USER", "pids")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pids")

# Small, fixed pool: this API only ever serves small aggregate
# queries (a handful of rows per table), so there is no scenario in
# this project where more concurrent DB connections would help.
POOL_MIN_CONNECTIONS = 1
POOL_MAX_CONNECTIONS = 5


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:
    if SITE_ID not in VALID_SITE_IDS:
        raise ValueError(
            f"Invalid SITE_ID '{SITE_ID}'. "
            f"Expected one of {sorted(VALID_SITE_IDS)}."
        )


# ============================================================
# Database
# ============================================================

connection_pool: Optional[psycopg2.pool.SimpleConnectionPool] = None


def get_connection():
    connection = connection_pool.getconn()
    try:
        yield connection
    finally:
        connection_pool.putconn(connection)


def fetch_all(connection, query: str, params: tuple) -> list[dict]:
    with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        except psycopg2.Error as error:
            connection.rollback()
            raise HTTPException(
                status_code=503, detail="Database query failed"
            ) from error


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_configuration()

    global connection_pool
    connection_pool = psycopg2.pool.SimpleConnectionPool(
        POOL_MIN_CONNECTIONS,
        POOL_MAX_CONNECTIONS,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )

    yield

    connection_pool.closeall()


app = FastAPI(title=f"site-api-{SITE_ID}", lifespan=lifespan)


# ============================================================
# Prometheus instrumentation
# Ruta dedicada '/prometheus': '/metrics' ya lo usan los
# endpoints de negocio (metrics/hourly, etc.).
# ============================================================

HTTP_REQUESTS = Counter(
    "site_api_requests_total",
    "Peticiones HTTP atendidas por la site_api.",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "site_api_request_seconds",
    "Latencia de las peticiones HTTP de la site_api.",
    ["method", "endpoint"],
)
TRIPS_PROCESSED = Gauge(
    "trips_processed_total",
    "Viajes procesados (trip_count) acumulados en Gold para esta sede.",
)


@app.middleware("http")
async def prometheus_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    endpoint = request.url.path
    HTTP_LATENCY.labels(request.method, endpoint).observe(elapsed)
    HTTP_REQUESTS.labels(
        request.method, endpoint, response.status_code
    ).inc()
    return response


@app.get("/prometheus")
def prometheus_metrics():
    # Metrica de negocio: lee el acumulado de Gold en cada scrape.
    # Si la BD falla, se sirven el resto de metricas igualmente.
    try:
        conn = connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(trip_count), 0) "
                    "FROM hourly_metrics WHERE site_id = %s",
                    (SITE_ID,),
                )
                TRIPS_PROCESSED.set(cur.fetchone()[0])
        finally:
            connection_pool.putconn(conn)
    except Exception:
        pass
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ============================================================
# Response models
# One per Gold table, mirroring exactly the combinable columns
# sink_postgres.py writes (sql/init.sql) -- no trip-level fields,
# no averages.
# ============================================================

class HourlyMetric(BaseModel):
    trip_hour: datetime
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal


class DailyMetric(BaseModel):
    trip_date: date
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal


class ZoneMetric(BaseModel):
    pu_location_id: int
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal


class PaymentMetric(BaseModel):
    payment_type: int
    trip_count: int
    sum_fare_amount: Decimal
    sum_trip_distance: float
    sum_tip_amount: Decimal
    sum_total_amount: Decimal


class QuarantineReasonSummary(BaseModel):
    rejection_reason: str
    rejected_count: int


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "site_id": SITE_ID}


# ============================================================
# Gold endpoints
# ============================================================

@app.get("/metrics/hourly", response_model=list[HourlyMetric])
def get_hourly_metrics(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    connection=Depends(get_connection),
):
    query = "SELECT trip_hour, trip_count, sum_fare_amount, sum_trip_distance, sum_tip_amount, sum_total_amount FROM hourly_metrics WHERE site_id = %s"
    params: list = [SITE_ID]

    if date_from is not None:
        query += " AND trip_hour >= %s"
        params.append(date_from)
    if date_to is not None:
        query += " AND trip_hour <= %s"
        params.append(date_to)

    query += " ORDER BY trip_hour"

    return fetch_all(connection, query, tuple(params))


@app.get("/metrics/daily", response_model=list[DailyMetric])
def get_daily_metrics(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    connection=Depends(get_connection),
):
    query = "SELECT trip_date, trip_count, sum_fare_amount, sum_trip_distance, sum_tip_amount, sum_total_amount FROM daily_metrics WHERE site_id = %s"
    params: list = [SITE_ID]

    if date_from is not None:
        query += " AND trip_date >= %s"
        params.append(date_from)
    if date_to is not None:
        query += " AND trip_date <= %s"
        params.append(date_to)

    query += " ORDER BY trip_date"

    return fetch_all(connection, query, tuple(params))


@app.get("/metrics/zone", response_model=list[ZoneMetric])
def get_zone_metrics(
    pu_location_id: Optional[int] = Query(None),
    connection=Depends(get_connection),
):
    query = "SELECT pu_location_id, trip_count, sum_fare_amount, sum_trip_distance, sum_tip_amount, sum_total_amount FROM zone_metrics WHERE site_id = %s"
    params: list = [SITE_ID]

    if pu_location_id is not None:
        query += " AND pu_location_id = %s"
        params.append(pu_location_id)

    query += " ORDER BY pu_location_id"

    return fetch_all(connection, query, tuple(params))


@app.get("/metrics/payment", response_model=list[PaymentMetric])
def get_payment_metrics(
    payment_type: Optional[int] = Query(None),
    connection=Depends(get_connection),
):
    query = "SELECT payment_type, trip_count, sum_fare_amount, sum_trip_distance, sum_tip_amount, sum_total_amount FROM payment_metrics WHERE site_id = %s"
    params: list = [SITE_ID]

    if payment_type is not None:
        query += " AND payment_type = %s"
        params.append(payment_type)

    query += " ORDER BY payment_type"

    return fetch_all(connection, query, tuple(params))


# ============================================================
# Quarantine endpoint
# ============================================================

@app.get("/quarantine/summary", response_model=list[QuarantineReasonSummary])
def get_quarantine_summary(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    connection=Depends(get_connection),
):
    """
    Counts of rejected trips grouped by rejection_reason -- an
    aggregate over silver_rejected, never the rejected rows
    themselves (those can contain arbitrary/malformed trip data that
    has no business leaving the site either).
    """
    query = (
        "SELECT rejection_reason, COUNT(*) AS rejected_count "
        "FROM silver_rejected WHERE site_id = %s"
    )
    params: list = [SITE_ID]

    if date_from is not None:
        query += " AND rejected_at >= %s"
        params.append(date_from)
    if date_to is not None:
        query += " AND rejected_at <= %s"
        params.append(date_to)

    query += " GROUP BY rejection_reason ORDER BY rejected_count DESC"

    return fetch_all(connection, query, tuple(params))


# ============================================================
# Main (local dev only -- production runs via uvicorn in Dockerfile)
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
