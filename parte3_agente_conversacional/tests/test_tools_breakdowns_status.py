"""Tests de las herramientas de pagos, zonas y estado (P3-07).

Igual que en P3-06: sin red, con httpx.MockTransport sobre `responder`
del mock, y cifras esperadas calculadas directamente sobre las fixtures.
"""

import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
import pytest

from mock import mock_coordinator as mc
from src.data.coordinator_client import CoordinatorClient
from src.tools import invoke_tool, register_all_tools
from src.tools.base import ToolError, ToolResult, clear_registry, get_tool, tools_schema
from src.tools.breakdowns import (
    PaymentArgs,
    ZoneArgs,
    ZonesArgs,
    get_payment_breakdown,
    get_zone,
    get_zones,
)
from src.tools.common import site_of_zone
from src.tools.status import get_platform_status

URLS = ["http://localhost:8100", "http://localhost:8101", "http://localhost:8102"]
SITES = ["central", "chamartin", "atocha"]
FIXTURES = Path(mc.__file__).parent / "fixtures"
METRIC_KEYS = ["trips", "revenue", "avg_fare", "avg_distance", "avg_tip", "avg_total"]
JFK = 132


# ============================================================
# Utilidades
# ============================================================

@pytest.fixture(autouse=True)
def _estado_limpio(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", set())
    monkeypatch.setattr(mc, "SLOW_SITES", set())
    monkeypatch.delenv("MIN_TRIPS_PER_CELL", raising=False)
    mc._FIXTURES_CACHE = None
    clear_registry()  # sin restos de otros tests (p. ej. la herramienta «juguete»)
    register_all_tools()
    yield
    mc._FIXTURES_CACHE = None


def _client(behaviors: dict | None = None) -> CoordinatorClient:
    """behaviors: url -> 'ok' | 'down' | '4xx'. Por defecto todas 'ok'."""
    behaviors = behaviors or {}

    def handler(request: httpx.Request) -> httpx.Response:
        base = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        beh = behaviors.get(base, "ok")
        if beh == "down":
            raise httpx.ConnectError("simulado", request=request)
        if beh == "4xx":
            return httpx.Response(422, json={"detail": "parametro invalido"})
        return httpx.Response(200, json=mc.responder(request.url.path, dict(request.url.params)))

    return CoordinatorClient(urls=URLS, timeout_s=10, transport=httpx.MockTransport(handler))


ALL_DOWN = {u: "down" for u in URLS}


def _fixture_rows(table: str, sites=SITES) -> list[dict]:
    rows = []
    for site in sites:
        data = json.loads((FIXTURES / f"{site}.json").read_text(encoding="utf-8"))
        rows += [{**row, "site_id": site} for row in data[table]]
    return rows


def _q(value: Decimal, places: str = "0.01") -> float:
    return float(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _expected(rows: list[dict]) -> dict:
    n = sum(r["trip_count"] for r in rows)
    fare = sum(Decimal(r["sum_fare_amount"]) for r in rows)
    tip = sum(Decimal(r["sum_tip_amount"]) for r in rows)
    total = sum(Decimal(r["sum_total_amount"]) for r in rows)
    dist = sum(Decimal(str(r["sum_trip_distance"])) for r in rows)
    return {
        "trips": n,
        "revenue": _q(total),
        "avg_fare": _q(fare / n),
        "avg_distance": _q(dist / n),
        "avg_tip": _q(tip / n),
        "avg_total": _q(total / n),
    }


def _by(rows: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


# ============================================================
# Registro
# ============================================================

def test_las_siete_herramientas_estan_registradas():
    names = {s["function"]["name"] for s in tools_schema()}
    assert names == {
        "get_kpis", "compare_sites", "get_timeseries",
        "get_payment_breakdown", "get_zones", "get_zone", "get_platform_status",
    }
    for name in ("get_payment_breakdown", "get_zones", "get_zone", "get_platform_status"):
        assert len(get_tool(name).description) > 50


# ============================================================
# get_payment_breakdown
# ============================================================

def test_pagos_cifras_y_porcentajes_exactos():
    res = get_payment_breakdown(PaymentArgs(), client=_client())
    rows = _fixture_rows("payment")
    groups = _by(rows, "payment_type")
    total_trips = sum(r["trip_count"] for r in rows)
    total_rev = sum(Decimal(r["sum_total_amount"]) for r in rows)

    assert [d["payment_type"] for d in res.data] == sorted(groups, key=lambda c: -sum(r["trip_count"] for r in groups[c]))
    for d in res.data:
        exp = _expected(groups[d["payment_type"]])
        assert d["trips"] == exp["trips"]
        assert d["revenue"] == exp["revenue"]
        assert d["pct_trips"] == _q(Decimal(exp["trips"]) * 100 / total_trips, "0.1")
        rev = sum(Decimal(r["sum_total_amount"]) for r in groups[d["payment_type"]])
        assert d["pct_revenue"] == _q(rev * 100 / total_rev, "0.1")
    assert res.data[0]["name"] == "tarjeta"
    assert "acumulados" in res.meta.note
    bar, table = res.blocks
    assert bar.type == "bar" and bar.unit == "%" and table.type == "table"


def test_pagos_oculta_celdas_pero_el_porcentaje_usa_el_total():
    """En central hay 4 viajes «sin cargo» y 3 en «disputa»: se ocultan."""
    res = get_payment_breakdown(PaymentArgs(sites=["central"]), client=_client())
    rows = _fixture_rows("payment", ["central"])
    total = sum(r["trip_count"] for r in rows)
    small = [r["payment_type"] for r in rows if r["trip_count"] < 5]

    assert small, "las fixtures deberían tener métodos con menos de 5 viajes en central"
    assert not {d["payment_type"] for d in res.data} & set(small)
    assert f"{len(small)} valor(es)" in res.meta.note
    for d in res.data:
        assert d["pct_trips"] == _q(Decimal(d["trips"]) * 100 / total, "0.1")
    assert sum(d["pct_trips"] for d in res.data) < 100


def test_pagos_con_atocha_caida(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = get_payment_breakdown(PaymentArgs(), client=_client())
    assert res.meta.partial is True and res.meta.sites_failed == ["atocha"]
    exp = sum(r["trip_count"] for r in _fixture_rows("payment", ["central", "chamartin"]))
    assert sum(d["trips"] for d in res.data) == exp


# ============================================================
# get_zones
# ============================================================

def _small_zones(sites=SITES) -> set[int]:
    groups = _by(_fixture_rows("zone", sites), "pu_location_id")
    return {z for z, rows in groups.items() if sum(r["trip_count"] for r in rows) < 5}


def test_ranking_por_viajes_con_nombres_y_cifras_exactas():
    res = get_zones(ZonesArgs(metric="trips", n=5), client=_client())
    groups = _by(_fixture_rows("zone"), "pu_location_id")
    expected = sorted(groups, key=lambda z: (-sum(r["trip_count"] for r in groups[z]), z))[:5]

    ranking = res.data["ranking"]
    assert [z["zone_id"] for z in ranking] == expected
    assert [z["rank"] for z in ranking] == [1, 2, 3, 4, 5]
    for z in ranking:
        assert {k: z[k] for k in METRIC_KEYS} == _expected(groups[z["zone_id"]])
        assert z["zone"] != "zona desconocida" and z["borough"]
    assert res.block.type == "table" and len(res.block.data["rows"]) == 5
    assert "acumulados" in res.meta.note


@pytest.mark.parametrize("metric", METRIC_KEYS)
def test_una_zona_con_menos_de_5_viajes_nunca_aparece(metric):
    small = _small_zones()
    assert small, "las fixtures tienen zonas raras (4, 12, 13)"
    res = get_zones(ZonesArgs(metric=metric, n=20), client=_client())
    assert not {z["zone_id"] for z in res.data["ranking"]} & small
    assert f"{len(small)} valor(es)" in res.meta.note


def test_ranking_por_media_ordenado():
    res = get_zones(ZonesArgs(metric="avg_fare", n=20), client=_client())
    values = [z["avg_fare"] for z in res.data["ranking"]]
    assert values == sorted(values, reverse=True)
    assert "Tarifa media ($)" in res.block.data["columns"]


def test_ranking_de_una_sede():
    res = get_zones(ZonesArgs(metric="trips", n=20, sites=["chamartin"]), client=_client())
    assert all(z["site"] == "chamartin" for z in res.data["ranking"])
    assert res.meta.sites_ok == ["chamartin"]


# ============================================================
# get_zone
# ============================================================

def test_get_zone_por_nombre_jfk():
    res = invoke_tool("get_zone", {"zone_name": "JFK Airport"}, client=_client())
    assert isinstance(res, ToolResult)
    site = site_of_zone(JFK)
    rows = [r for r in _fixture_rows("zone", [site]) if r["pu_location_id"] == JFK]
    assert res.data["zone_id"] == JFK and res.data["zone"] == "JFK Airport"
    assert res.data["site"] == site
    assert {k: res.data[k] for k in METRIC_KEYS} == _expected(rows)
    assert res.block.type == "kpi"


def test_get_zone_por_id_y_por_nombre_parcial_coinciden():
    by_id = get_zone(ZoneArgs(zone_id=JFK), client=_client())
    by_name = get_zone(ZoneArgs(zone_name="jfk"), client=_client())
    assert by_id.data == by_name.data


@pytest.mark.parametrize("zone_id", sorted(_small_zones()) + [1])
def test_get_zone_por_debajo_del_umbral_no_muestra_cifras(zone_id):
    """Zonas raras y una zona sin viajes: mismo mensaje y ninguna cifra."""
    res = get_zone(ZoneArgs(zone_id=zone_id), client=_client())
    assert isinstance(res, ToolResult)
    assert "trips" not in res.data and res.block is None
    assert "No hay datos suficientes" in res.meta.note


def test_get_zone_ambigua_devuelve_las_opciones():
    res = invoke_tool("get_zone", {"zone_name": "Corona"}, client=_client())
    assert isinstance(res, ToolError) and res.error == "zona_ambigua"
    assert "56" in res.detail and "57" in res.detail


def test_get_zone_inexistente():
    res = invoke_tool("get_zone", {"zone_name": "Barcelona"}, client=_client())
    assert isinstance(res, ToolError) and res.error == "zona_no_encontrada"


@pytest.mark.parametrize("args", [
    {},
    {"zone_id": 132, "zone_name": "JFK Airport"},
    {"zone_id": 0},
    {"zone_id": 266},
    {"zone_name": "x"},
])
def test_get_zone_parametros_invalidos(args):
    res = invoke_tool("get_zone", args, client=_client())
    assert isinstance(res, ToolError) and res.error == "parametros_invalidos"


def test_get_zone_solo_depende_de_su_sede(monkeypatch):
    site = site_of_zone(JFK)  # central
    other = next(s for s in SITES if s != site)
    monkeypatch.setattr(mc, "DOWN_SITES", {other})
    res = get_zone(ZoneArgs(zone_id=JFK), client=_client())
    assert isinstance(res, ToolResult) and res.meta.partial is False

    monkeypatch.setattr(mc, "DOWN_SITES", {site})
    res = get_zone(ZoneArgs(zone_id=JFK), client=_client())
    assert isinstance(res, ToolError) and res.error == "sedes_no_disponibles"
    assert site in res.detail


# ============================================================
# get_platform_status
# ============================================================

def test_estado_todo_arriba():
    res = get_platform_status(client=_client())
    d = res.data
    assert d["coordinator"] == "disponible"
    assert d["replicas_up"] == 3 and d["replicas_total"] == 3
    assert [s["status"] for s in d["sites"]] == ["responde"] * 3
    dates = sorted({r["trip_date"] for r in _fixture_rows("daily")})
    assert d["first_date"] == dates[0] and d["last_date"] == dates[-1]
    assert d["dates_with_data"] == dates
    assert res.meta.partial is False and res.meta.note is None
    assert res.block.type == "table"


def test_estado_con_una_sede_caida(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = get_platform_status(client=_client())
    status = {s["site"]: s["status"] for s in res.data["sites"]}
    assert status == {"central": "responde", "chamartin": "responde", "atocha": "no responde"}
    assert res.meta.partial is True and res.meta.sites_failed == ["atocha"]
    assert "atocha" in res.meta.note


def test_estado_con_la_replica_central_caida():
    res = get_platform_status(client=_client({URLS[0]: "down"}))
    d = res.data
    assert d["coordinator"] == "disponible"
    assert [r["status"] for r in d["replicas"]] == ["caída", "activa", "activa"]
    assert d["served_by"] == URLS[1]
    assert "failover" in res.meta.note


def test_estado_con_todo_caido_no_lanza():
    res = invoke_tool("get_platform_status", {}, client=_client(ALL_DOWN))
    assert isinstance(res, ToolResult)
    assert res.data["coordinator"] == "no disponible"
    assert res.data["replicas_up"] == 0
    assert "no disponible" in res.meta.note.lower()
    assert all(s["status"] == "desconocido" for s in res.data["sites"])


def test_estado_ante_un_fallo_inesperado_tampoco_lanza():
    class Roto:
        def health_all(self):
            raise RuntimeError("boom")

    res = get_platform_status(client=Roto())
    assert isinstance(res, ToolResult) and res.data["coordinator"] == "desconocido"


# ============================================================
# Relevo B -> C: todas las herramientas, también con una sede caída
# ============================================================

CALLS = [
    ("get_kpis", {}),
    ("compare_sites", {}),
    ("get_timeseries", {"metric": "trips", "granularity": "day"}),
    ("get_payment_breakdown", {}),
    ("get_zones", {"metric": "revenue", "n": 5}),
    ("get_zone", {"zone_name": "JFK Airport"}),
    ("get_platform_status", {}),
]


@pytest.mark.parametrize("down", [set(), {"atocha"}])
@pytest.mark.parametrize("name,args", CALLS)
def test_relevo_todas_las_herramientas_responden(monkeypatch, name, args, down):
    monkeypatch.setattr(mc, "DOWN_SITES", down)
    res = invoke_tool(name, args, client=_client())
    assert isinstance(res, ToolResult), res
    assert res.blocks, "toda herramienta con datos pinta al menos un bloque"
    json.dumps(res.model_dump(mode="json"))
    if down and name != "get_zone":
        assert res.meta.partial is True and res.meta.sites_failed == ["atocha"]


@pytest.mark.parametrize("name,args", CALLS[:-1])
def test_relevo_coordinador_caido_es_tool_error(name, args):
    res = invoke_tool(name, args, client=_client(ALL_DOWN))
    assert isinstance(res, ToolError) and res.error == "coordinador_no_disponible"
