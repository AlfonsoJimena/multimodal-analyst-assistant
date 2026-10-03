"""Tests del pintado de respuestas y de la barra lateral (P3-13). Sin red:

  - funciones puras de `src/ui/render.py` (formato, tablas, series, fechas);
  - GET /status del cliente contra httpx.MockTransport;
  - la pagina con AppTest, alimentada con respuestas REALES de /chat: el
    orquestador con un LLM de guion y las herramientas contra el mock.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from mock import mock_coordinator as mc
from src.agent.config import Config
from src.agent.llm import LLMResponse, LLMUsage
from src.agent.orchestrator import Orchestrator
from src.api.schemas import Block, ChatResponse, Source
from src.data.coordinator_client import CoordinatorClient
from src.tools import register_all_tools
from src.tools.base import clear_registry
from src.ui import client as agent_client
from src.ui import render
from src.ui.client import AgentError
from tests.test_ui import (  # noqa: F401 - `agent` es un fixture
    API_URL,
    FakeAgent,
    FakeStatus,
    _app,
    _ask,
    _raising,
    _texts,
    _transport,
    agent,
    status_data,
)

COORDINATOR_URLS = ["http://localhost:8100", "http://localhost:8101", "http://localhost:8102"]


# ============================================================
# Respuestas reales de /chat
# ============================================================

def _config() -> Config:
    return Config(
        openrouter_api_key="sk-or-fake",
        llm_model="modelo/principal",
        llm_fallback_model="modelo/respaldo",
        llm_temperature=0.1,
        llm_timeout_s=5.0,
        max_tool_rounds=5,
        coordinator_urls=COORDINATOR_URLS,
        coordinator_timeout_s=10.0,
        min_trips_per_cell=5,
        agent_api_token="",
        agent_api_url=API_URL,
        max_history_turns=6,
    )


class ToolThenAnswer:
    """LLM de guion: pide una herramienta y luego contesta con un texto fijo."""

    def __init__(self, tool: str, args: dict) -> None:
        self._tool = tool
        self._args = args

    def chat(self, messages, tools=None):
        if messages[-1]["role"] == "tool":
            message = SimpleNamespace(content="Aquí tienes los datos.", tool_calls=None)
        else:
            function = SimpleNamespace(name=self._tool, arguments=json.dumps(self._args))
            call = SimpleNamespace(id="c1", type="function", function=function)
            message = SimpleNamespace(content=None, tool_calls=[call])
        return LLMResponse(message=message, model="guion", usage=LLMUsage())


@pytest.fixture
def real_response(monkeypatch):
    """Construye el ChatResponse que devolveria /chat para una herramienta."""
    monkeypatch.setattr(mc, "SLOW_SITES", set())
    mc._FIXTURES_CACHE = None
    clear_registry()
    register_all_tools()

    def build(tool: str, args: dict | None = None, down: tuple[str, ...] = ()) -> ChatResponse:
        monkeypatch.setattr(mc, "DOWN_SITES", set(down))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mc.responder(request.url.path, dict(request.url.params)))

        client = CoordinatorClient(urls=COORDINATOR_URLS, transport=httpx.MockTransport(handler))
        llm = ToolThenAnswer(tool, args or {})
        return Orchestrator(llm=llm, config=_config(), client=client).run("pregunta").response

    yield build
    clear_registry()
    mc._FIXTURES_CACHE = None


def _charts(at: AppTest) -> list:
    return at.get("arrow_vega_lite_chart")


def _page_with(monkeypatch, response: ChatResponse, status=None) -> AppTest:
    monkeypatch.setattr(agent_client, "ask_agent", FakeAgent([response]))
    if status is not None:
        monkeypatch.setattr(agent_client, "get_status", status)
    at = _app()
    _ask(at, "pregunta")
    return at


def _sidebar_text(at: AppTest) -> str:
    return " ".join(md.value for md in at.sidebar.markdown)


# ============================================================
# Formato (funciones puras)
# ============================================================

@pytest.mark.parametrize(
    "value, unit, label, expected",
    [
        (1500, None, "Viajes", "1500 viajes"),
        (56446.6, "$", "Ingresos", "$56446.60"),
        (2.345, "mi", "Distancia media", "2.35 millas"),
        (70.0, "%", None, "70.00 %"),
        (3, None, "#", "3"),
        (None, "$", "Ingresos", "—"),
        ("central", None, None, "central"),
    ],
)
def test_format_value(value, unit, label, expected):
    assert render.format_value(value, unit, label) == expected


def test_md_escapa_dolares_para_que_no_sean_latex():
    assert render.md("de $10 a $20") == r"de \$10 a \$20"


def test_date_ranges_agrupa_dias_consecutivos():
    dates = ["2026-09-26", "2020-01-01", "2026-09-25", "2019-12-31", "2026-09-28"]
    assert render.date_ranges(dates) == [
        ("2019-12-31", "2020-01-01"),
        ("2026-09-25", "2026-09-26"),
        ("2026-09-28", "2026-09-28"),
    ]


def test_tabla_con_unidades_y_decimales():
    block = Block(type="table", title="t", data={
        "columns": ["Sede", "Viajes", "Distancia media (mi)"],
        "rows": [["central", 150, 10.123], ["atocha", 900, 9.5]],
    })
    frame = render.table_frame(block)
    assert list(frame.columns) == ["Sede", "Viajes", "Distancia media (millas)"]
    config = render.table_column_config(frame)
    assert config["Viajes"]["type_config"]["format"] == "%d"
    assert config["Distancia media (millas)"]["type_config"]["format"] == "%.2f"
    assert "Sede" not in config


def test_serie_con_fechas_y_huecos_por_privacidad():
    block = Block(type="line", title="t", unit="$", data={
        "x": ["2026-09-25T00:00:00", "2026-09-25T01:00:00"],
        "series": [{"name": "Ingresos", "points": [12.5, None]}],
    })
    frame = render.line_frame(block)
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame["Ingresos"].iloc[0] == 12.5
    assert math.isnan(frame["Ingresos"].iloc[1])
    assert render.axis_label("Ingresos", "mi") == "Ingresos (millas)"


def test_linea_de_trazabilidad():
    source = Source(
        tool="get_kpis", args={"sites": ["central"]}, served_by="http://localhost:8101",
        sites_ok=["central", "chamartin"], sites_failed=["atocha"], partial=True, latency_ms=42,
    )
    line = render.source_line(source)
    for text in ("get_kpis", '"central"', "localhost:8101", "central, chamartin", "caídas: atocha", "42 ms"):
        assert text in line


# ============================================================
# Cliente: GET /status
# ============================================================

def test_get_status_devuelve_data_y_nota():
    body = {"data": status_data(down=("atocha",)), "meta": {"note": "No responde(n): atocha."}}
    seen: list[httpx.Request] = []
    status = agent_client.get_status(API_URL, "secreto", transport=_transport(200, body, seen))

    assert status["sites"][2]["status"] == "no responde"
    assert status["note"] == "No responde(n): atocha."
    assert seen[0].method == "GET"
    assert str(seen[0].url) == API_URL + "/status"
    assert seen[0].headers["X-API-Key"] == "secreto"


@pytest.mark.parametrize(
    "transport, expected",
    [
        (_transport(200, {"error": "x", "detail": "y"}), AgentError(agent_client.STATUS_UNKNOWN_MESSAGE, 200)),
        (_transport(401, {}), AgentError(agent_client.UNAUTHORIZED_MESSAGE, 401)),
        (_raising(httpx.ConnectError("x")), AgentError(agent_client.API_DOWN_MESSAGE)),
    ],
)
def test_get_status_errores(transport, expected):
    assert agent_client.get_status(API_URL, "t", transport=transport) == expected


# ============================================================
# Pagina: un bloque por herramienta real
# ============================================================

@pytest.mark.parametrize(
    "tool, args, metrics, tables, charts",
    [
        ("get_kpis", {}, 6, 0, 0),
        ("compare_sites", {}, 0, 1, 1),
        ("get_timeseries", {"metric": "trips", "granularity": "hour",
                            "date_from": "2026-09-26", "date_to": "2026-09-26"}, 0, 0, 1),
        ("get_payment_breakdown", {}, 0, 1, 1),
        ("get_zones", {"metric": "revenue", "n": 5}, 0, 1, 0),
        ("get_zone", {"zone_name": "JFK Airport"}, 6, 0, 0),
        ("get_platform_status", {}, 0, 1, 0),
    ],
)
def test_cada_herramienta_se_pinta(agent, monkeypatch, real_response, tool, args, metrics, tables, charts):
    response = real_response(tool, args)
    assert response.blocks, f"{tool} no ha devuelto bloques"
    at = _page_with(monkeypatch, response)

    assert len(at.metric) == metrics
    assert len(at.dataframe) == tables
    assert len(_charts(at)) == charts
    assert [e.label for e in at.expander] == [render.TRACE_TITLE]
    assert not at.exception


def test_kpis_con_unidades(agent, monkeypatch, real_response):
    at = _page_with(monkeypatch, real_response("get_kpis"))
    values = {m.label: m.value for m in at.metric}

    assert values["Viajes"] == "1500 viajes"
    assert values["Ingresos"].startswith("$")
    assert len(values["Ingresos"].split(".")[1]) == 2
    assert values["Distancia media"].endswith(" millas")


def test_sede_caida_muestra_aviso_trazabilidad_y_barra_lateral(agent, monkeypatch, real_response):
    response = real_response("compare_sites", down=("atocha",))
    status = FakeStatus(status_data(down=("atocha",)))
    at = _page_with(monkeypatch, response, status)

    assert any("atocha" in w.value for w in at.warning)
    trace = " ".join(md.value for md in at.expander[0].markdown)
    assert "caídas: atocha" in trace
    assert "🔴 **atocha** · no responde" in _sidebar_text(at)
    assert "🟢 **central** · responde" in _sidebar_text(at)
    assert status.calls == 2  # al abrir y, otra vez, tras el aviso


def test_respuesta_sin_herramientas_no_tiene_trazabilidad(agent):
    at = _app()
    _ask(at, "hola")
    assert len(at.expander) == 0


def test_respuesta_con_dolares_no_se_pinta_como_latex(agent, monkeypatch):
    response = ChatResponse(request_id="r", reply="Ingresos de $120.50 y propina de $3.20.")
    at = _page_with(monkeypatch, response)
    assert r"Ingresos de \$120.50 y propina de \$3.20." in _texts(at)


def test_pregunta_sugerida_lanza_la_consulta(agent):
    at = _app()
    suggestions = [b for b in at.button if b.key and b.key.startswith("sugerencia_")]
    assert 3 <= len(suggestions) <= 4

    suggestions[1].click().run()
    assert [c["message"] for c in agent.calls] == [suggestions[1].label]
    assert f"Respuesta a: {suggestions[1].label}" in _texts(at)


def test_barra_lateral_estado_y_refrescar(agent, monkeypatch):
    status = FakeStatus()
    monkeypatch.setattr(agent_client, "get_status", status)
    at = _app()

    assert "3 de 3 réplicas activas" in _sidebar_text(at)
    assert "2020-01-01" in _sidebar_text(at)
    assert "2026-09-25 a 2026-09-30" in _sidebar_text(at)
    assert status.calls == 1

    at.run()  # un rerun normal no vuelve a pedir el estado
    assert status.calls == 1
    next(b for b in at.sidebar.button if b.label == "Refrescar estado").click().run()
    assert status.calls == 2


def test_barra_lateral_sin_api(agent, monkeypatch):
    monkeypatch.setattr(agent_client, "get_status", FakeStatus(AgentError(agent_client.API_DOWN_MESSAGE)))
    at = _app()
    assert [w.value for w in at.sidebar.warning] == [agent_client.API_DOWN_MESSAGE]
