"""
Desglose por sede del coordinador: parametro ?breakdown= (P3-02).

breakdown=none (por defecto): el coordinador suma entre sedes, una fila
por clave, exactamente como antes. breakdown=site: no suma entre sedes,
una fila por (site_id, clave), con site_id y las medias de esa sede
calculadas a partir de sus propias sumas.

Como en M1, las sedes se simulan con httpx.MockTransport (fixture
fake_sites de conftest). Volumenes muy distintos a proposito para que una
"media de medias" se notaria.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SITES


SITE_TRIP_COUNT = {"central": 10, "chamartin": 30, "atocha": 60}
SITE_SUM_FARE = {"central": "100.00", "chamartin": "450.00", "atocha": "600.00"}
TRIP_DATE = "2020-01-01"


def _daily_row(site: str) -> dict:
    count = SITE_TRIP_COUNT[site]
    return {
        "trip_date": TRIP_DATE,
        "trip_count": count,
        # site_api serializa Decimal como texto y los float como numero
        "sum_fare_amount": SITE_SUM_FARE[site],
        "sum_trip_distance": 2.0 * count,
        "sum_tip_amount": f"{count}.00",
        "sum_total_amount": f"{3 * count}.00",
    }


def build_payloads() -> dict:
    return {site: {"/metrics/daily": [_daily_row(site)]} for site in SITES}


@pytest.fixture
def coordinator(fake_sites):
    from src.coordinator.main import app

    sites = fake_sites(build_payloads())
    with TestClient(app) as client:
        yield client, sites


def _rows_by_site(data: list[dict]) -> dict:
    return {row["site_id"]: row for row in data}


# ============================================================
# breakdown=site
# ============================================================

def test_breakdown_site_una_fila_por_sede(coordinator):
    client, _ = coordinator

    body = client.get("/metrics/daily", params={"breakdown": "site"}).json()

    assert sorted(body["sites_ok"]) == sorted(SITES)
    assert body["partial"] is False
    assert len(body["data"]) == 3

    by_site = _rows_by_site(body["data"])
    assert set(by_site) == set(SITES)
    for site in SITES:
        assert by_site[site]["trip_count"] == SITE_TRIP_COUNT[site]
        assert by_site[site]["trip_date"] == TRIP_DATE


def test_breakdown_site_medias_por_sede(coordinator):
    client, _ = coordinator

    body = client.get("/metrics/daily", params={"breakdown": "site"}).json()
    by_site = _rows_by_site(body["data"])

    # Media de cada sede = sus propias sumas / sus propios conteos.
    for site in SITES:
        expected = Decimal(SITE_SUM_FARE[site]) / SITE_TRIP_COUNT[site]
        assert Decimal(str(by_site[site]["avg_fare_amount"])) == expected

    # central y atocha dan 10; chamartin 15. No es una media de medias
    # (que para las tres juntas daria (10+15+10)/3 = 11.67).
    assert Decimal(str(by_site["central"]["avg_fare_amount"])) == Decimal("10")
    assert Decimal(str(by_site["chamartin"]["avg_fare_amount"])) == Decimal("15")
    assert Decimal(str(by_site["atocha"]["avg_fare_amount"])) == Decimal("10")


def test_breakdown_site_sede_caida(coordinator):
    client, sites = coordinator
    sites.behaviour["atocha"] = "down"

    body = client.get("/metrics/daily", params={"breakdown": "site"}).json()

    assert body["partial"] is True
    assert body["sites_failed"] == ["atocha"]
    assert sorted(body["sites_ok"]) == ["central", "chamartin"]

    by_site = _rows_by_site(body["data"])
    assert set(by_site) == {"central", "chamartin"}
    assert "atocha" not in by_site


# ============================================================
# breakdown=none: la respuesta de antes, sin cambios
# ============================================================

def test_sin_breakdown_respuesta_combinada_sin_site_id(coordinator):
    client, _ = coordinator

    body = client.get("/metrics/daily").json()

    assert len(body["data"]) == 1
    row = body["data"][0]
    assert "site_id" not in row  # response_model_exclude_none lo omite
    assert row["trip_count"] == sum(SITE_TRIP_COUNT.values())  # 100


def test_sin_breakdown_igual_que_breakdown_none(coordinator):
    client, _ = coordinator

    sin = client.get("/metrics/daily").json()
    explicito = client.get("/metrics/daily", params={"breakdown": "none"}).json()

    assert sin == explicito


def test_breakdown_invalido_da_422(coordinator):
    client, _ = coordinator

    resp = client.get("/metrics/daily", params={"breakdown": "ciudad"})

    assert resp.status_code == 422
