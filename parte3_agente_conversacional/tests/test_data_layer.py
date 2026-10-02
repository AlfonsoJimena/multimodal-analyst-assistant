"""Tests de la capa de datos (P3-04): cliente con failover, agregacion y privacidad.

Los tests unitarios no usan red: un httpx.MockTransport responde por las
replicas, delegando en la funcion `responder` del mock cuando la replica
esta "viva", igual que hacen los tests de la parte 2.
"""

import os
from decimal import Decimal

import httpx
import pytest

from mock import mock_coordinator as mc
from src.data.aggregation import combine, round_money, to_decimal
from src.data.coordinator_client import (
    CoordinatorClient,
    CoordinatorParamError,
    CoordinatorResult,
    CoordinatorUnavailable,
)
from src.data.privacy import suppress_small_cells

URLS = ["http://localhost:8100", "http://localhost:8101", "http://localhost:8102"]


def make_transport(behaviors: dict) -> httpx.MockTransport:
    """behaviors: url -> 'ok' | 'down' | 'timeout' | '500' | '4xx'. Por defecto 'ok'."""

    def handler(request: httpx.Request) -> httpx.Response:
        base = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        beh = behaviors.get(base, "ok")
        if beh == "down":
            raise httpx.ConnectError("simulado: replica caida", request=request)
        if beh == "timeout":
            raise httpx.ReadTimeout("simulado: replica colgada", request=request)
        if beh == "500":
            return httpx.Response(500, json={"detail": "error interno"})
        if beh == "4xx":
            return httpx.Response(422, json={"detail": "parametro invalido"})
        body = mc.responder(request.url.path, dict(request.url.params))
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", set())
    monkeypatch.setattr(mc, "SLOW_SITES", set())
    mc._FIXTURES_CACHE = None
    yield
    mc._FIXTURES_CACHE = None


def _client(behaviors=None) -> CoordinatorClient:
    return CoordinatorClient(urls=URLS, timeout_s=10, transport=make_transport(behaviors or {}))


# ============================================================
# Failover
# ============================================================

def test_failover_primaria_caida_responde_la_segunda():
    res = _client({"http://localhost:8100": "down"}).daily()
    assert res.served_by == "http://localhost:8101"
    assert any("8100" in s for s in res.skipped)


def test_failover_primaria_y_segunda_caidas_responde_la_tercera():
    res = _client({"http://localhost:8100": "down", "http://localhost:8101": "500"}).daily()
    assert res.served_by == "http://localhost:8102"
    assert len(res.skipped) == 2


def test_todas_caidas_lanza_unavailable():
    with pytest.raises(CoordinatorUnavailable):
        _client({u: "down" for u in URLS}).daily()


def test_4xx_no_hace_failover():
    # primaria 4xx, la 2a estaria viva: aun asi NO se reintenta -> error de parametros
    with pytest.raises(CoordinatorParamError):
        _client({"http://localhost:8100": "4xx"}).daily()


def test_5xx_si_hace_failover():
    res = _client({"http://localhost:8100": "500"}).daily()
    assert res.served_by == "http://localhost:8101"


def test_sede_colgada_respuesta_parcial_sin_failover(monkeypatch):
    # El coordinador devuelve parcial (una sede caida). El cliente lo acepta
    # de la primaria sin saltar a otra replica.
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = _client().daily()
    assert res.served_by == "http://localhost:8100"
    assert res.partial is True
    assert "atocha" in res.sites_failed
    assert res.skipped == []


def test_sites_ok_vacio_es_sin_datos(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"central", "chamartin", "atocha"})
    res = _client().daily()
    assert res.sites_ok == []
    assert res.no_data is True


def test_health_all():
    salud = _client({"http://localhost:8101": "down"}).health_all()
    assert salud[0]["ok"] is True and salud[0]["site_id"] == "mock"
    assert salud[1]["ok"] is False


def test_breakdown_site_llega_al_cliente():
    res = _client().daily(breakdown="site")
    assert all("site_id" in r for r in res.data)


# ============================================================
# Agregacion
# ============================================================

def test_media_ponderada_no_es_media_de_medias():
    # 500 viajes a 14 $ + 100 viajes a 20 $ = 15 $ (no 17 $)
    rows = [
        {"trip_count": 500, "sum_fare_amount": "7000.00", "sum_tip_amount": "0",
         "sum_total_amount": "7000.00", "sum_trip_distance": 0.0},
        {"trip_count": 100, "sum_fare_amount": "2000.00", "sum_tip_amount": "0",
         "sum_total_amount": "2000.00", "sum_trip_distance": 0.0},
    ]
    combinado = combine(rows)
    assert combinado["trip_count"] == 600
    assert combinado["avg_fare_amount"] == Decimal("15")
    assert combinado["avg_fare_amount"] != Decimal("17")


def test_importes_son_decimal_nunca_float():
    rows = [{"trip_count": 3, "sum_fare_amount": "10.00", "sum_tip_amount": "1.00",
             "sum_total_amount": "11.00", "sum_trip_distance": 5.0}]
    combinado = combine(rows)
    assert isinstance(combinado["sum_fare_amount"], Decimal)
    assert isinstance(combinado["avg_fare_amount"], Decimal)


def test_round_money_solo_al_presentar():
    assert round_money("15.0") == Decimal("15.00")
    assert round_money(Decimal("3.33333")) == Decimal("3.33")
    assert to_decimal("1600.50") == Decimal("1600.50")


# ============================================================
# Privacidad
# ============================================================

def test_supresion_celdas_con_datos_del_mock():
    body = mc.responder("/metrics/zone", {})
    kept, hidden = suppress_small_cells(body["data"], 5)
    assert hidden > 0
    assert all(r["trip_count"] >= 5 for r in kept)


def test_supresion_cuenta_las_ocultas():
    rows = [{"trip_count": 10}, {"trip_count": 3}, {"trip_count": 4}, {"trip_count": 7}]
    kept, hidden = suppress_small_cells(rows, 5)
    assert [r["trip_count"] for r in kept] == [10, 7]
    assert hidden == 2


# ============================================================
# Integracion (solo con --integration): contra el coordinador real o el mock
# ============================================================

@pytest.mark.integration
def test_integration_coordinador_real():
    client = CoordinatorClient()  # usa COORDINATOR_URLS del entorno
    res = client.daily()
    assert isinstance(res, CoordinatorResult)
    assert res.served_by
