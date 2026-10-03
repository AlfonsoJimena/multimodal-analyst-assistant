"""Tests de la API del agente (P3-11). Sin red ni coste: TestClient de
FastAPI, un LLM falso con guion y herramientas de juguete.
"""

from __future__ import annotations

import copy
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from src.agent.config import Config
from src.agent.llm import LLMResponse, LLMUnavailable, LLMUsage
from src.agent.orchestrator import Orchestrator
from src.api.main import create_app
from src.api.schemas import Block
from src.api.sessions import SessionStore
from src.tools import base
from src.tools.base import ToolError, ToolMeta, ToolResult, register_tool

TOKEN = "secreto-de-prueba"


# ============================================================
# Piezas de test
# ============================================================

def _config(**overrides: Any) -> Config:
    values = dict(
        openrouter_api_key="sk-or-fake",
        llm_model="modelo/principal",
        llm_fallback_model="modelo/respaldo",
        llm_temperature=0.1,
        llm_timeout_s=5.0,
        max_tool_rounds=5,
        coordinator_urls=["http://localhost:8100"],
        coordinator_timeout_s=10.0,
        min_trips_per_cell=5,
        agent_api_token="",
        agent_api_url="http://localhost:8300",
        max_history_turns=6,
    )
    values.update(overrides)
    return Config(**values)


class FakeLLM:
    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _answer(text: str) -> LLMResponse:
    usage = LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0)
    return LLMResponse(
        message=SimpleNamespace(content=text, tool_calls=None),
        model="modelo/principal",
        usage=usage,
    )


def _ask(name: str, args: dict[str, Any], call_id: str = "c1") -> LLMResponse:
    function = SimpleNamespace(name=name, arguments=json.dumps(args))
    call = SimpleNamespace(id=call_id, type="function", function=function)
    usage = LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0)
    return LLMResponse(
        message=SimpleNamespace(content=None, tool_calls=[call]),
        model="modelo/principal",
        usage=usage,
    )


class _SumArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int
    b: int


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _suma(args: _SumArgs, client=None) -> ToolResult:
    meta = ToolMeta(sites_ok=["central"], served_by="central", latency_ms=7)
    block = Block(type="kpi", title="Suma", data=[{"label": "Suma", "value": args.a + args.b}])
    return ToolResult(data={"suma": args.a + args.b}, meta=meta, block=block)


def _caida(args: _NoArgs, client=None) -> ToolError:
    return ToolError(error="coordinador_no_disponible", detail="sin respuesta")


def _estado(args: _NoArgs, client=None) -> ToolResult:
    meta = ToolMeta(sites_ok=["central", "chamartin", "atocha"], served_by="http://mock")
    block = Block(type="table", title="Estado de la plataforma", data={"columns": [], "rows": []})
    return ToolResult(data={"sedes": ["central", "chamartin", "atocha"]}, meta=meta, block=block)


@pytest.fixture(autouse=True)
def herramientas():
    saved = dict(base._REGISTRY)
    base.clear_registry()
    register_tool("suma", "Suma dos enteros", _SumArgs, _suma)
    register_tool("caida", "Coordinador caido", _NoArgs, _caida)
    register_tool("get_platform_status", "Estado de la plataforma", _NoArgs, _estado)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def log_lines():
    handler = _ListHandler()
    logger = logging.getLogger("agent.api")
    logger.addHandler(handler)
    yield handler.lines
    logger.removeHandler(handler)


def _client(llm: FakeLLM, clock=None, **config_overrides: Any) -> TestClient:
    config = _config(**config_overrides)
    orchestrator = Orchestrator(llm=llm, config=config, system_prompt="PROMPT")
    kwargs = {"clock": clock} if clock is not None else {}
    return TestClient(create_app(orchestrator=orchestrator, config=config, **kwargs))


def _chat(client: TestClient, message: str = "hola", session_id: str = "demo", **kwargs):
    return client.post(
        "/chat", json={"session_id": session_id, "message": message}, **kwargs
    )


# ============================================================
# /chat
# ============================================================

def test_chat_devuelve_la_respuesta_completa():
    llm = FakeLLM([_ask("suma", {"a": 2, "b": 3}), _answer("Son 5.")])
    response = _chat(_client(llm), "¿2+3?")

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Son 5."
    assert body["request_id"]
    assert [b["title"] for b in body["blocks"]] == ["Suma"]
    assert body["sources"][0]["tool"] == "suma"
    assert body["sources"][0]["args"] == {"a": 2, "b": 3}
    assert body["warnings"] == []
    assert body["latency_ms"] >= 0


def test_la_sesion_recuerda_el_turno_anterior():
    llm = FakeLLM([_answer("Hola, soy el asistente."), _answer("Te llamas Ana.")])
    client = _client(llm)

    _chat(client, "Me llamo Ana")
    _chat(client, "¿Cómo me llamo?")

    second = llm.calls[1]["messages"]
    assert [(m["role"], m["content"]) for m in second[1:]] == [
        ("user", "Me llamo Ana"),
        ("assistant", "Hola, soy el asistente."),
        ("user", "¿Cómo me llamo?"),
    ]


def test_el_historial_guarda_solo_texto_no_mensajes_de_herramientas():
    llm = FakeLLM([_ask("suma", {"a": 1, "b": 1}), _answer("Son 2."), _answer("ok")])
    client = _client(llm)

    _chat(client, "1+1")
    _chat(client, "gracias")

    roles = [m["role"] for m in llm.calls[2]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_las_sesiones_estan_aisladas():
    llm = FakeLLM([_answer("a"), _answer("b")])
    client = _client(llm)

    _chat(client, "pregunta de A", session_id="A")
    _chat(client, "pregunta de B", session_id="B")

    assert [m["role"] for m in llm.calls[1]["messages"]] == ["system", "user"]


def test_el_historial_se_acota_a_max_history_turns():
    llm = FakeLLM([_answer(f"r{i}") for i in range(5)])
    client = _client(llm, max_history_turns=2)

    for i in range(5):
        _chat(client, f"p{i}")

    last = llm.calls[4]["messages"]
    assert len(last) == 1 + 4 + 1  # sistema + 2 turnos + pregunta
    assert last[1]["content"] == "p2"


def test_la_sesion_caduca_tras_un_tiempo_sin_uso():
    clock = _Clock()
    llm = FakeLLM([_answer("r1"), _answer("r2")])
    client = _client(llm, clock=clock)

    _chat(client, "primera")
    clock.now += 3601
    _chat(client, "segunda")

    assert [m["role"] for m in llm.calls[1]["messages"]] == ["system", "user"]


def test_coordinador_caido_responde_200_con_warnings():
    llm = FakeLLM([_ask("caida", {}), _answer("No he podido consultar los datos.")])
    response = _chat(_client(llm), "¿cuántos viajes?")

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "No he podido consultar los datos."
    assert body["warnings"]


def test_llm_no_disponible_da_503_con_mensaje_claro_y_no_guarda_el_turno():
    llm = FakeLLM([LLMUnavailable("ni uno ni otro"), _answer("ya funciona")])
    client = _client(llm)

    failed = _chat(client, "primera")
    assert failed.status_code == 503
    assert "no está disponible" in failed.json()["detail"]

    _chat(client, "segunda")
    assert [m["role"] for m in llm.calls[1]["messages"]] == ["system", "user"]


# ============================================================
# Validacion
# ============================================================

@pytest.mark.parametrize("message", ["", "x" * 2001])
def test_mensaje_vacio_o_demasiado_largo_da_422(message):
    llm = FakeLLM([])
    response = _chat(_client(llm), message)

    assert response.status_code == 422
    assert llm.calls == []


def test_sin_session_id_da_422():
    response = _client(FakeLLM([])).post("/chat", json={"message": "hola"})

    assert response.status_code == 422


def test_mensaje_de_2000_caracteres_es_valido():
    llm = FakeLLM([_answer("ok")])

    assert _chat(_client(llm), "x" * 2000).status_code == 200


# ============================================================
# Token
# ============================================================

def test_sin_token_da_401_en_chat_y_status():
    client = _client(FakeLLM([]), agent_api_token=TOKEN)

    assert _chat(client).status_code == 401
    assert client.get("/status").status_code == 401


def test_token_incorrecto_da_401():
    client = _client(FakeLLM([]), agent_api_token=TOKEN)

    assert _chat(client, headers={"X-API-Key": "otro"}).status_code == 401


def test_token_correcto_da_200():
    llm = FakeLLM([_answer("ok")])
    client = _client(llm, agent_api_token=TOKEN)

    assert _chat(client, headers={"X-API-Key": TOKEN}).status_code == 200
    assert client.get("/status", headers={"X-API-Key": TOKEN}).status_code == 200


def test_con_el_token_vacio_se_desactiva():
    llm = FakeLLM([_answer("ok")])

    assert _chat(_client(llm, agent_api_token="")).status_code == 200


def test_health_no_pide_token():
    client = _client(FakeLLM([]), agent_api_token=TOKEN)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ============================================================
# /status y /docs
# ============================================================

def test_status_devuelve_el_resultado_de_get_platform_status():
    response = _client(FakeLLM([])).get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"sedes": ["central", "chamartin", "atocha"]}
    assert body["meta"]["sites_ok"] == ["central", "chamartin", "atocha"]
    assert body["block"]["title"] == "Estado de la plataforma"


def test_status_con_error_responde_200_con_el_error():
    register_tool("get_platform_status", "Estado", _NoArgs, _caida)
    response = _client(FakeLLM([])).get("/status")

    assert response.status_code == 200
    assert response.json()["error"] == "coordinador_no_disponible"


def test_los_tres_endpoints_aparecen_en_la_documentacion():
    client = _client(FakeLLM([]))
    paths = client.get("/openapi.json").json()["paths"]

    assert {"/chat", "/status", "/health"} <= set(paths)
    assert client.get("/docs").status_code == 200


# ============================================================
# Log
# ============================================================

def test_una_linea_json_por_peticion_con_los_campos_pedidos(log_lines):
    llm = FakeLLM([_ask("suma", {"a": 2, "b": 3}), _answer("Son 5.")])
    response = _chat(_client(llm), "mensaje confidencial", session_id="s1")

    assert len(log_lines) == 1
    entry = json.loads(log_lines[0])
    assert entry["request_id"] == response.json()["request_id"]
    assert entry["session_id"] == "s1"
    assert entry["message_chars"] == len("mensaje confidencial")
    assert entry["status"] == 200
    assert entry["path"] == "/chat"
    assert entry["tools"] == [
        {
            "tool": "suma",
            "args": {"a": 2, "b": 3},
            "served_by": "central",
            "partial": False,
            "latency_ms": 7,
        }
    ]
    assert entry["model"] == "modelo/principal"
    assert entry["total_tokens"] == 30
    assert entry["tool_rounds"] == 1
    assert isinstance(entry["latency_ms"], int)
    assert isinstance(entry["agent_latency_ms"], int)
    # Nunca se registra el texto del mensaje.
    assert "confidencial" not in log_lines[0]


def test_el_log_recoge_los_errores_con_su_codigo_de_estado(log_lines):
    client = _client(FakeLLM([LLMUnavailable("caido")]), agent_api_token=TOKEN)

    _chat(client)  # 401
    _chat(client, headers={"X-API-Key": TOKEN})  # 503
    _chat(client, "", headers={"X-API-Key": TOKEN})  # 422

    entries = [json.loads(line) for line in log_lines]
    assert [e["status"] for e in entries] == [401, 503, 422]
    assert entries[1]["error"] == "llm_unavailable"


def test_health_y_docs_no_se_registran(log_lines):
    client = _client(FakeLLM([]))

    client.get("/health")
    client.get("/docs")
    client.get("/openapi.json")

    assert log_lines == []


# ============================================================
# Sesiones (unitarios)
# ============================================================

def test_el_almacen_limita_el_numero_de_sesiones():
    store = SessionStore(max_sessions=2)

    for session_id in ("a", "b", "c"):
        store.add_turn(session_id, "u", "r")

    assert len(store) == 2
    assert store.history("a") == []  # la mas antigua se expulsa
    assert store.history("c")


def test_el_almacen_devuelve_copias():
    store = SessionStore()
    store.add_turn("a", "u", "r")

    store.history("a").clear()

    assert len(store.history("a")) == 2
