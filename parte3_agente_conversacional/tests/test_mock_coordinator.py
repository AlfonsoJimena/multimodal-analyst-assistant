"""Tests del coordinador mock (P3-03).

Comprueban que el mock responde con el mismo formato que el coordinador
real, que los filtros de fecha y los fallos simulados funcionan, y que los
totales son coherentes entre tablas. Usan la funcion pura `responder`, sin
levantar servidor.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from mock import mock_coordinator as mc

METRIC_PATHS = ["/metrics/hourly", "/metrics/daily", "/metrics/zone", "/metrics/payment"]


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch):
    """Cada test arranca sin fallos simulados y con la cache fresca."""
    monkeypatch.setattr(mc, "DOWN_SITES", set())
    monkeypatch.setattr(mc, "SLOW_SITES", set())
    mc._FIXTURES_CACHE = None
    yield
    mc._FIXTURES_CACHE = None


# ============================================================
# Formato
# ============================================================

def test_health():
    assert mc.responder("/health", {}) == {
        "status": "ok",
        "site_id": "mock",
        "failover_priority": 1,
    }


@pytest.mark.parametrize("path", METRIC_PATHS)
def test_formato_respuesta(path):
    body = mc.responder(path, {})

    assert set(body) == {"sites_ok", "sites_failed", "partial", "data"}
    assert sorted(body["sites_ok"]) == ["atocha", "central", "chamartin"]
    assert body["sites_failed"] == []
    assert body["partial"] is False
    assert body["data"]

    row = body["data"][0]
    # importes Decimal como texto, distancia como numero
    assert isinstance(row["sum_fare_amount"], str)
    assert isinstance(row["sum_trip_distance"], (int, float))
    # media = suma / conteo
    assert Decimal(row["avg_fare_amount"]) == Decimal(row["sum_fare_amount"]) / row["trip_count"]


def test_claves_por_endpoint():
    assert "trip_hour" in mc.responder("/metrics/hourly", {})["data"][0]
    assert "trip_date" in mc.responder("/metrics/daily", {})["data"][0]
    assert "pu_location_id" in mc.responder("/metrics/zone", {})["data"][0]
    assert "payment_type" in mc.responder("/metrics/payment", {})["data"][0]


# ============================================================
# breakdown=site (igual que P3-02)
# ============================================================

def test_breakdown_site_una_fila_por_sede():
    body = mc.responder("/metrics/daily", {"breakdown": "site"})
    assert all("site_id" in r for r in body["data"])
    assert {r["site_id"] for r in body["data"]} == {"central", "chamartin", "atocha"}


def test_sin_breakdown_no_lleva_site_id():
    body = mc.responder("/metrics/daily", {})
    assert all("site_id" not in r for r in body["data"])


# ============================================================
# Filtros de fecha
# ============================================================

def test_filtro_fecha_daily():
    body = mc.responder("/metrics/daily", {"date_from": "2020-01-01", "date_to": "2020-01-01"})
    assert {r["trip_date"] for r in body["data"]} == {"2020-01-01"}


def test_hourly_dia_completo():
    body = mc.responder(
        "/metrics/hourly",
        {"date_from": "2020-01-01T00:00:00", "date_to": "2020-01-01T23:59:59"},
    )
    horas = {r["trip_hour"] for r in body["data"]}
    assert horas
    assert all(h.startswith("2020-01-01T") for h in horas)


def test_hourly_fecha_sin_hora_es_medianoche():
    # '2020-01-01' == medianoche: como mucho la franja 00:00 (igual que el real)
    body = mc.responder("/metrics/hourly", {"date_from": "2020-01-01", "date_to": "2020-01-01"})
    assert {r["trip_hour"] for r in body["data"]} <= {"2020-01-01T00:00:00"}


def test_filtro_zona():
    full = mc.responder("/metrics/zone", {})
    zona = full["data"][0]["pu_location_id"]
    body = mc.responder("/metrics/zone", {"pu_location_id": str(zona)})
    assert {r["pu_location_id"] for r in body["data"]} == {zona}


# ============================================================
# Fallos simulados
# ============================================================

def test_sede_caida(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    body = mc.responder("/metrics/daily", {"breakdown": "site"})

    assert body["partial"] is True
    assert body["sites_failed"] == ["atocha"]
    assert sorted(body["sites_ok"]) == ["central", "chamartin"]
    assert "atocha" not in {r["site_id"] for r in body["data"]}


def test_tres_sedes_caidas_devuelve_vacio(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"central", "chamartin", "atocha"})
    body = mc.responder("/metrics/daily", {})

    assert body["sites_ok"] == []
    assert body["data"] == []


def test_slow_no_altera_datos(monkeypatch):
    # SLOW_SECONDS=0 ejercita el camino lento sin esperar de verdad
    monkeypatch.setattr(mc, "SLOW_SITES", {"atocha"})
    monkeypatch.setattr(mc, "SLOW_SECONDS", 0.0)
    client = TestClient(mc.app)
    resp = client.get("/metrics/daily")
    assert resp.status_code == 200
    assert sorted(resp.json()["sites_ok"]) == ["atocha", "central", "chamartin"]


# ============================================================
# Coherencia de las fixtures
# ============================================================

def test_coherencia_totales_por_sede():
    def totales(path, campo, cero):
        body = mc.responder(path, {"breakdown": "site"})
        acc = {}
        for r in body["data"]:
            acc[r["site_id"]] = acc.get(r["site_id"], cero) + campo(r)
        return acc

    viajes = {p: totales(p, lambda r: r["trip_count"], 0) for p in METRIC_PATHS}
    assert viajes["/metrics/daily"] == viajes["/metrics/hourly"]
    assert viajes["/metrics/daily"] == viajes["/metrics/zone"]
    assert viajes["/metrics/daily"] == viajes["/metrics/payment"]

    dinero = {p: totales(p, lambda r: Decimal(r["sum_fare_amount"]), Decimal("0")) for p in METRIC_PATHS}
    assert dinero["/metrics/daily"] == dinero["/metrics/hourly"]
    assert dinero["/metrics/daily"] == dinero["/metrics/zone"]
    assert dinero["/metrics/daily"] == dinero["/metrics/payment"]


def test_hay_zonas_con_menos_de_5_viajes():
    body = mc.responder("/metrics/zone", {})
    counts = [r["trip_count"] for r in body["data"]]
    assert any(c < 5 for c in counts)
    assert len(body["data"]) >= 20


# ============================================================
# App: health y validacion
# ============================================================

def test_app_health_y_422():
    client = TestClient(mc.app)
    assert client.get("/health").json()["site_id"] == "mock"
    assert client.get("/metrics/daily", params={"breakdown": "ciudad"}).status_code == 422
