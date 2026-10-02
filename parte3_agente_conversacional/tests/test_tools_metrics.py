"""Tests de las herramientas de métricas (P3-06).

Sin red: un httpx.MockTransport responde con la función pura `responder`
del coordinador mock. Las cifras esperadas se calculan DIRECTAMENTE sobre
las fixtures JSON (sin pasar por el mock ni por aggregation.combine), así
que el test de exactitud compara dos caminos independientes.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
import pytest

from mock import mock_coordinator as mc
from src.api.schemas import Block
from src.data.coordinator_client import CoordinatorClient
from src.tools import invoke_tool, register_all_tools
from src.tools import metrics
from src.tools.base import ToolError, ToolResult, clear_registry, get_tool, tools_schema
from src.tools.metrics import (
    CompareSitesArgs,
    KpisArgs,
    TimeseriesArgs,
    compare_sites,
    get_kpis,
    get_timeseries,
)

URLS = ["http://localhost:8100", "http://localhost:8101", "http://localhost:8102"]
SITES = ["central", "chamartin", "atocha"]
FIXTURES = Path(mc.__file__).parent / "fixtures"
ONE_DAY = "2026-09-26"


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


def _client(behavior: str = "ok", seen: list | None = None) -> CoordinatorClient:
    """behavior: 'ok' (todas responden con el mock), 'down' (ninguna) o '4xx'."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if behavior == "down":
            raise httpx.ConnectError("simulado", request=request)
        if behavior == "4xx":
            return httpx.Response(422, json={"detail": "parametro invalido"})
        return httpx.Response(200, json=mc.responder(request.url.path, dict(request.url.params)))

    return CoordinatorClient(urls=URLS, timeout_s=10, transport=httpx.MockTransport(handler))


def _fixture_rows(table: str, sites=SITES, keep=lambda row: True) -> list[dict]:
    rows = []
    for site in sites:
        data = json.loads((FIXTURES / f"{site}.json").read_text(encoding="utf-8"))
        rows += [row for row in data[table] if keep(row)]
    return rows


def _q(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _expected(rows: list[dict]) -> dict:
    """Cálculo directo: Σ sumas / Σ conteos, con Decimal."""
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


def _between(start: str, end: str):
    return lambda row: start <= row["trip_date"] <= end


METRIC_KEYS = ["trips", "revenue", "avg_fare", "avg_distance", "avg_tip", "avg_total"]


# ============================================================
# Registro y esquemas
# ============================================================

def test_las_tres_herramientas_estan_registradas_con_esquema():
    schemas = {s["function"]["name"]: s["function"] for s in tools_schema()}
    for name in ("get_kpis", "compare_sites", "get_timeseries"):
        assert get_tool(name) is not None
        assert len(schemas[name]["description"]) > 50
        assert schemas[name]["parameters"]["type"] == "object"

    ts = schemas["get_timeseries"]["parameters"]
    assert set(ts["required"]) == {"metric", "granularity"}
    assert set(ts["properties"]["metric"]["enum"]) == set(METRIC_KEYS)
    assert "sites" in schemas["get_kpis"]["parameters"]["properties"]


def test_register_es_idempotente():
    before = len(tools_schema())
    register_all_tools()
    assert len(tools_schema()) == before


# ============================================================
# Exactitud contra las fixtures (diferencia 0)
# ============================================================

def test_kpis_todas_las_sedes_todo_el_periodo():
    res = get_kpis(KpisArgs(), client=_client())
    assert isinstance(res, ToolResult)
    expected = _expected(_fixture_rows("daily"))
    assert {k: res.data[k] for k in METRIC_KEYS} == expected
    assert res.meta.partial is False
    assert res.meta.sites_ok == SITES
    assert res.meta.period == "2020-01-01 a 2026-09-30"
    assert res.block.type == "kpi"
    assert [item["value"] for item in res.block.data] == [expected[k] for k in METRIC_KEYS]


def test_kpis_una_sede_y_un_rango():
    args = KpisArgs(sites=["chamartin"], date_from="2026-09-25", date_to="2026-09-27")
    res = get_kpis(args, client=_client())
    expected = _expected(_fixture_rows("daily", ["chamartin"], _between("2026-09-25", "2026-09-27")))
    assert {k: res.data[k] for k in METRIC_KEYS} == expected
    assert res.data["sites"] == ["chamartin"]
    assert res.meta.period == "2026-09-25 a 2026-09-27"


def test_compare_sites_una_fila_por_sede():
    res = compare_sites(CompareSitesArgs(), client=_client())
    assert [row["site"] for row in res.data] == SITES
    for row in res.data:
        expected = _expected(_fixture_rows("daily", [row["site"]]))
        assert {k: row[k] for k in METRIC_KEYS} == expected

    bar, table = res.blocks
    assert bar.type == "bar" and table.type == "table"
    assert bar.data["categories"] == SITES
    assert bar.data["series"][0]["values"] == [row["trips"] for row in res.data]
    assert len(table.data["rows"]) == 3
    assert len(table.data["columns"]) == len(table.data["rows"][0])


def test_compare_sites_suma_igual_a_kpis():
    """Las sedes son disjuntas: la suma de viajes por sede es el total."""
    comp = compare_sites(CompareSitesArgs(), client=_client())
    kpis = get_kpis(KpisArgs(), client=_client())
    assert sum(row["trips"] for row in comp.data) == kpis.data["trips"]


def test_timeseries_diaria_y_su_maximo():
    args = TimeseriesArgs(metric="trips", granularity="day")
    res = get_timeseries(args, client=_client())
    rows = _fixture_rows("daily")
    days = sorted({r["trip_date"] for r in rows})
    assert [p["t"] for p in res.data["points"]] == days
    for p in res.data["points"]:
        assert p["value"] == _expected([r for r in rows if r["trip_date"] == p["t"]])["trips"]
    best = max(res.data["points"], key=lambda p: p["value"])
    assert res.data["peak"] == best
    assert res.block.type == "line"
    assert res.block.data["x"] == days


def test_timeseries_de_una_metrica_media_por_sede():
    args = TimeseriesArgs(metric="avg_fare", granularity="day", sites=["atocha"])
    res = get_timeseries(args, client=_client())
    rows = _fixture_rows("daily", ["atocha"])
    for p in res.data["points"]:
        assert p["value"] == _expected([r for r in rows if r["trip_date"] == p["t"]])["avg_fare"]
    assert res.block.unit == "$"


# ============================================================
# Serie horaria de un solo día (date_to hasta las 23:59:59)
# ============================================================

def test_timeseries_horaria_de_un_dia_devuelve_todas_las_horas():
    seen = []
    args = TimeseriesArgs(metric="trips", granularity="hour", date_from=ONE_DAY, date_to=ONE_DAY)
    res = get_timeseries(args, client=_client(seen=seen))

    assert seen[0].url.params["date_to"] == f"{ONE_DAY}T23:59:59"
    assert seen[0].url.params["date_from"] == f"{ONE_DAY}T00:00:00"

    rows = _fixture_rows("hourly", keep=lambda r: r["trip_hour"].startswith(ONE_DAY))
    hours = sorted({r["trip_hour"] for r in rows})
    assert len(hours) > 1
    assert [p["t"] for p in res.data["points"]] == hours
    assert res.meta.period == ONE_DAY

    for p in res.data["points"]:
        n = sum(r["trip_count"] for r in rows if r["trip_hour"] == p["t"])
        assert p["value"] == (n if n >= 5 else None)


# ============================================================
# Sedes caídas (DOWN_SITES=atocha)
# ============================================================

def test_atocha_caida_resultado_parcial(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = get_kpis(KpisArgs(), client=_client())
    assert res.meta.partial is True
    assert res.meta.sites_failed == ["atocha"]
    assert "atocha" in res.meta.note
    expected = _expected(_fixture_rows("daily", ["central", "chamartin"]))
    assert {k: res.data[k] for k in METRIC_KEYS} == expected


def test_atocha_caida_en_la_comparativa(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = compare_sites(CompareSitesArgs(), client=_client())
    assert res.meta.partial is True
    assert res.meta.sites_failed == ["atocha"]
    assert [row["site"] for row in res.data] == ["central", "chamartin"]


def test_parcial_solo_respecto_a_las_sedes_pedidas(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = get_kpis(KpisArgs(sites=["central", "chamartin"]), client=_client())
    assert res.meta.partial is False
    assert res.meta.sites_failed == []


def test_todas_las_sedes_pedidas_caidas(monkeypatch):
    monkeypatch.setattr(mc, "DOWN_SITES", {"atocha"})
    res = get_kpis(KpisArgs(sites=["atocha"]), client=_client())
    assert isinstance(res, ToolError)
    assert res.error == "sedes_no_disponibles"


# ============================================================
# Parámetros inválidos y errores -> ToolError, nunca excepción
# ============================================================

@pytest.mark.parametrize("name,args", [
    ("get_kpis", {"sites": ["barcelona"]}),
    ("get_kpis", {"date_from": "2020-13-01"}),
    ("get_kpis", {"date_from": "01/01/2020"}),
    ("get_kpis", {"date_from": "2026-09-30", "date_to": "2026-09-01"}),
    ("get_kpis", {"ciudad": "Madrid"}),
    ("compare_sites", {"date_to": "ayer"}),
    ("get_timeseries", {"metric": "beneficio", "granularity": "day"}),
    ("get_timeseries", {"metric": "trips", "granularity": "minute"}),
    ("get_timeseries", {"granularity": "day"}),
    ("get_timeseries", "{no es json"),
])
def test_parametros_invalidos_devuelven_tool_error(name, args):
    res = invoke_tool(name, args, client=_client())
    assert isinstance(res, ToolError)
    assert res.error == "parametros_invalidos"
    assert res.detail


def test_herramienta_desconocida():
    res = invoke_tool("get_weather", {}, client=_client())
    assert isinstance(res, ToolError) and res.error == "herramienta_desconocida"


def test_invoke_tool_acepta_json_del_llm():
    res = invoke_tool("get_kpis", '{"sites": ["central"]}', client=_client())
    assert isinstance(res, ToolResult)
    assert res.data["sites"] == ["central"]


@pytest.mark.parametrize("name,args", [
    ("get_kpis", {}),
    ("compare_sites", {}),
    ("get_timeseries", {"metric": "trips", "granularity": "hour"}),
])
def test_coordinador_caido_devuelve_tool_error(name, args):
    res = invoke_tool(name, args, client=_client("down"))
    assert isinstance(res, ToolError)
    assert res.error == "coordinador_no_disponible"


def test_coordinador_rechaza_parametros():
    res = invoke_tool("get_kpis", {}, client=_client("4xx"))
    assert isinstance(res, ToolError) and res.error == "parametros_rechazados"


# ============================================================
# Sin datos, privacidad y límite de puntos
# ============================================================

def test_periodo_sin_datos_lo_dice_en_la_nota():
    args = KpisArgs(date_from="2021-03-01", date_to="2021-03-31")
    res = get_kpis(args, client=_client())
    assert isinstance(res, ToolResult)
    assert res.data is None and res.block is None
    assert "No hay viajes" in res.meta.note
    assert res.meta.period == "2021-03-01 a 2021-03-31"


def test_privacidad_oculta_celdas_pequenas(monkeypatch):
    monkeypatch.setenv("MIN_TRIPS_PER_CELL", "1000000")
    res = get_kpis(KpisArgs(), client=_client())
    assert res.data is None and "privacidad" in res.meta.note

    res = compare_sites(CompareSitesArgs(), client=_client())
    assert res.data is None and "3 valor(es)" in res.meta.note


def test_privacidad_en_la_serie_horaria():
    args = TimeseriesArgs(metric="avg_fare", granularity="hour", sites=["central"])
    res = get_timeseries(args, client=_client())
    rows = _fixture_rows("hourly", ["central"])
    small = sum(1 for r in rows if r["trip_count"] < 5)
    assert small > 0
    assert sum(1 for p in res.data["points"] if p["value"] is None) == small
    assert f"{small} valor(es)" in res.meta.note
    # La hora punta nunca es una celda oculta.
    assert res.data["peak"] is None or res.data["peak"]["value"] is not None


def test_serie_limitada_a_max_points(monkeypatch):
    monkeypatch.setattr(metrics, "MAX_POINTS", 10)
    res = get_timeseries(TimeseriesArgs(metric="trips", granularity="hour"), client=_client())
    assert len(res.data["points"]) == 10
    assert len(res.block.data["x"]) == 10
    assert "más recientes" in res.meta.note


def test_los_bloques_cumplen_el_contrato():
    outputs = [
        get_kpis(KpisArgs(), client=_client()),
        compare_sites(CompareSitesArgs(), client=_client()),
        get_timeseries(TimeseriesArgs(metric="revenue", granularity="day"), client=_client()),
    ]
    for res in outputs:
        for block in res.blocks:
            Block.model_validate(block.model_dump())
        # Todo el resultado es serializable a JSON (se le pasa al LLM).
        json.dumps(res.model_dump(mode="json"))
