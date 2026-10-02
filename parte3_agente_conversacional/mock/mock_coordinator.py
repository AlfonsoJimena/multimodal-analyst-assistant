"""Coordinador mock: responde igual que el real a partir de fixtures fijas.

Permite desarrollar y probar el chatbot (parte 3) sin levantar la parte 2
(que ocupa 8-9 GB y no cabe en CI). Imita el contrato del coordinador real
(`parte2_infraestructura_datos/src/coordinator/main.py`), incluido
`breakdown=site`.

Arranque:

    uvicorn mock.mock_coordinator:app --port 8190

Fallos simulados por variables de entorno:

    DOWN_SITES=atocha     -> atocha a sites_failed, partial=true, sin sus filas
    SLOW_SITES=atocha     -> responde tarde (SLOW_SECONDS, 5 por defecto)

La logica de combinacion vive en la funcion PURA `responder(path, params)`,
para poder testearla sin servidor (httpx.MockTransport), igual que la parte 2.
No importa nada de la parte 2: las fixtures viven en `mock/fixtures/`.
"""

import asyncio
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Query

SITES = ["central", "chamartin", "atocha"]
FIXTURES_DIR = Path(__file__).parent / "fixtures"

Breakdown = Literal["none", "site"]


# ============================================================
# Configuracion de fallos simulados (se lee del entorno; los
# tests pueden sobreescribir estos globales con monkeypatch).
# ============================================================

def _parse_sites(raw: str) -> set:
    return {s.strip() for s in raw.split(",") if s.strip()}


DOWN_SITES = _parse_sites(os.getenv("DOWN_SITES", ""))
SLOW_SITES = _parse_sites(os.getenv("SLOW_SITES", ""))
SLOW_SECONDS = float(os.getenv("SLOW_SECONDS", "5"))


# ============================================================
# Mapeo de endpoints
# ============================================================

PATH_METRIC = {
    "/metrics/hourly": "hourly",
    "/metrics/daily": "daily",
    "/metrics/zone": "zone",
    "/metrics/payment": "payment",
}
PATH_KEY = {
    "/metrics/hourly": "trip_hour",
    "/metrics/daily": "trip_date",
    "/metrics/zone": "pu_location_id",
    "/metrics/payment": "payment_type",
}


# ============================================================
# Fixtures
# ============================================================

_FIXTURES_CACHE: Optional[dict] = None


def _load_fixtures() -> dict:
    global _FIXTURES_CACHE
    if _FIXTURES_CACHE is None:
        data = {}
        for site in SITES:
            with (FIXTURES_DIR / f"{site}.json").open(encoding="utf-8") as f:
                data[site] = json.load(f)
        _FIXTURES_CACHE = data
    return _FIXTURES_CACHE


# ============================================================
# Filtros de fecha (mismos criterios que el coordinador real)
# ============================================================

def _parse_dt(path: str, raw):
    """date_from/date_to: datetime en hourly, date en daily. '2020-01-01'
    en hourly equivale a medianoche, igual que en el real."""
    if raw in (None, ""):
        return None
    if path == "/metrics/hourly":
        return datetime.fromisoformat(raw)
    return date.fromisoformat(str(raw)[:10])


def _passes_filter(path, row, date_from, date_to, pu_location_id, payment_type) -> bool:
    if path == "/metrics/hourly":
        ts = datetime.fromisoformat(row["trip_hour"])
        if date_from and ts < date_from:
            return False
        if date_to and ts > date_to:
            return False
    elif path == "/metrics/daily":
        d = date.fromisoformat(row["trip_date"])
        if date_from and d < date_from:
            return False
        if date_to and d > date_to:
            return False
    elif path == "/metrics/zone":
        if pu_location_id is not None and row["pu_location_id"] != pu_location_id:
            return False
    elif path == "/metrics/payment":
        if payment_type is not None and row["payment_type"] != payment_type:
            return False
    return True


# ============================================================
# Combinacion (misma logica que el coordinador real)
# ============================================================

def _money(value: Decimal) -> str:
    return str(value)


def _finalize(bucket: dict) -> dict:
    count = bucket["trip_count"]

    def avg(x):
        return x / count if count else (Decimal("0") if isinstance(x, Decimal) else 0.0)

    out = {}
    if "site_id" in bucket:
        out["site_id"] = bucket["site_id"]
    for key_field in ("trip_hour", "trip_date", "pu_location_id", "payment_type"):
        if key_field in bucket:
            out[key_field] = bucket[key_field]
    out["trip_count"] = count
    out["sum_fare_amount"] = _money(bucket["sum_fare_amount"])
    out["sum_trip_distance"] = bucket["sum_trip_distance"]
    out["sum_tip_amount"] = _money(bucket["sum_tip_amount"])
    out["sum_total_amount"] = _money(bucket["sum_total_amount"])
    out["avg_fare_amount"] = _money(avg(bucket["sum_fare_amount"]))
    out["avg_trip_distance"] = avg(bucket["sum_trip_distance"])
    out["avg_tip_amount"] = _money(avg(bucket["sum_tip_amount"]))
    out["avg_total_amount"] = _money(avg(bucket["sum_total_amount"]))
    return out


def responder(path: str, params: dict) -> dict:
    """Funcion pura: dado un path y sus parametros, devuelve la respuesta
    combinada, exactamente con el formato del coordinador real."""

    if path == "/health":
        return {"status": "ok", "site_id": "mock", "failover_priority": 1}

    metric = PATH_METRIC[path]
    key = PATH_KEY[path]
    breakdown = params.get("breakdown") or "none"

    date_from = _parse_dt(path, params.get("date_from"))
    date_to = _parse_dt(path, params.get("date_to"))
    pu = params.get("pu_location_id")
    pu = int(pu) if pu not in (None, "") else None
    ptype = params.get("payment_type")
    ptype = int(ptype) if ptype not in (None, "") else None

    fixtures = _load_fixtures()
    sites_ok: list[str] = []
    sites_failed: list[str] = []
    merged: dict = {}

    for site in sorted(SITES):
        if site in DOWN_SITES:
            sites_failed.append(site)
            continue
        sites_ok.append(site)

        for row in fixtures[site][metric]:
            if not _passes_filter(path, row, date_from, date_to, pu, ptype):
                continue

            key_value = row[key]
            bucket_key = (site, key_value) if breakdown == "site" else key_value
            bucket = merged.get(bucket_key)
            if bucket is None:
                bucket = {
                    key: key_value,
                    "trip_count": 0,
                    "sum_fare_amount": Decimal("0"),
                    "sum_trip_distance": 0.0,
                    "sum_tip_amount": Decimal("0"),
                    "sum_total_amount": Decimal("0"),
                }
                if breakdown == "site":
                    bucket["site_id"] = site
                merged[bucket_key] = bucket

            bucket["trip_count"] += row["trip_count"]
            bucket["sum_fare_amount"] += Decimal(row["sum_fare_amount"])
            bucket["sum_trip_distance"] += row["sum_trip_distance"]
            bucket["sum_tip_amount"] += Decimal(row["sum_tip_amount"])
            bucket["sum_total_amount"] += Decimal(row["sum_total_amount"])

    data = [_finalize(b) for b in merged.values()]
    return {
        "sites_ok": sites_ok,
        "sites_failed": sites_failed,
        "partial": len(sites_failed) > 0,
        "data": data,
    }


# ============================================================
# App FastAPI (contrato identico al coordinador real)
# ============================================================

app = FastAPI(title="coordinator-mock")


async def _maybe_slow() -> None:
    """Si alguna sede viva es lenta, responde tarde (para probar timeouts)."""
    if SLOW_SITES & (set(SITES) - DOWN_SITES):
        await asyncio.sleep(SLOW_SECONDS)


@app.get("/health")
def health() -> dict:
    return responder("/health", {})


@app.get("/metrics/hourly")
async def metrics_hourly(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    breakdown: Breakdown = Query("none"),
):
    await _maybe_slow()
    params = {"breakdown": breakdown}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    return responder("/metrics/hourly", params)


@app.get("/metrics/daily")
async def metrics_daily(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    breakdown: Breakdown = Query("none"),
):
    await _maybe_slow()
    params = {"breakdown": breakdown}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    return responder("/metrics/daily", params)


@app.get("/metrics/zone")
async def metrics_zone(
    pu_location_id: Optional[int] = Query(None),
    breakdown: Breakdown = Query("none"),
):
    await _maybe_slow()
    params = {"breakdown": breakdown}
    if pu_location_id is not None:
        params["pu_location_id"] = pu_location_id
    return responder("/metrics/zone", params)


@app.get("/metrics/payment")
async def metrics_payment(
    payment_type: Optional[int] = Query(None),
    breakdown: Breakdown = Query("none"),
):
    await _maybe_slow()
    params = {"breakdown": breakdown}
    if payment_type is not None:
        params["payment_type"] = payment_type
    return responder("/metrics/payment", params)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8190)
