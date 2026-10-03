"""Tests de la interfaz de chat (P3-12). Sin red ni navegador:

  - el cliente HTTP (`src/ui/client.py`) contra httpx.MockTransport;
  - la pagina (`src/ui/app.py`) con el AppTest de Streamlit, sustituyendo
    `ask_agent` por un doble que apunta lo que recibe.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from src.api.schemas import ChatResponse
from src.ui import client as agent_client
from src.ui.client import AgentError, ask_agent

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py")
API_URL = "http://agente:8300"

CHAT_OK = {
    "request_id": "abc",
    "reply": "Hubo 1500 viajes.",
    "blocks": [{"type": "kpi", "title": "Indicadores", "data": [{"label": "Viajes", "value": 1500}]}],
    "sources": [],
    "warnings": [],
    "latency_ms": 12,
}


# ============================================================
# Cliente HTTP
# ============================================================

def _transport(status: int = 200, body=None, seen: list | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=CHAT_OK if body is None else body)

    return httpx.MockTransport(handler)


def _raising(error: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return httpx.MockTransport(handler)


def test_cliente_envia_sesion_mensaje_y_token():
    seen: list[httpx.Request] = []
    reply = ask_agent(API_URL + "/", "secreto", "sesion-1", "hola", transport=_transport(seen=seen))

    assert isinstance(reply, ChatResponse)
    assert reply.reply == "Hubo 1500 viajes."
    assert reply.blocks[0].type == "kpi"
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "http://agente:8300/chat"
    assert request.headers["X-API-Key"] == "secreto"
    assert json.loads(request.content) == {"session_id": "sesion-1", "message": "hola"}


def test_cliente_sin_token_no_manda_cabecera():
    seen: list[httpx.Request] = []
    ask_agent(API_URL, "", "s", "hola", transport=_transport(seen=seen))
    assert "X-API-Key" not in seen[0].headers


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, agent_client.UNAUTHORIZED_MESSAGE),
        (422, agent_client.INVALID_MESSAGE),
        (503, agent_client.LLM_DOWN_MESSAGE),
        (500, agent_client.UNAVAILABLE_MESSAGE),
        (404, agent_client.UNEXPECTED_MESSAGE),
    ],
)
def test_cliente_traduce_codigos_de_error(status, expected):
    reply = ask_agent(API_URL, "t", "s", "hola", transport=_transport(status, {"detail": "x"}))
    assert reply == AgentError(expected, status)


def test_cliente_api_parada():
    reply = ask_agent(API_URL, "t", "s", "hola", transport=_raising(httpx.ConnectError("refused")))
    assert reply == AgentError(agent_client.API_DOWN_MESSAGE)


def test_cliente_api_lenta():
    reply = ask_agent(API_URL, "t", "s", "hola", transport=_raising(httpx.ReadTimeout("lenta")))
    assert reply == AgentError(agent_client.TIMEOUT_MESSAGE)


@pytest.mark.parametrize("body", ["<html>no es json</html>", {"reply": "falta request_id"}])
def test_cliente_respuesta_inesperada(body):
    reply = ask_agent(API_URL, "t", "s", "hola", transport=_transport(200, body))
    assert reply == AgentError(agent_client.UNEXPECTED_MESSAGE, 200)


# ============================================================
# Pagina de Streamlit
# ============================================================

class FakeAgent:
    """Sustituye a `ask_agent`: apunta las llamadas y responde con un guion."""

    def __init__(self, replies=None) -> None:
        self.calls: list[dict] = []
        self._replies = list(replies or [])

    def __call__(self, api_url, token, session_id, message, transport=None):
        self.calls.append(
            {"api_url": api_url, "token": token, "session_id": session_id, "message": message}
        )
        if self._replies:
            return self._replies.pop(0)
        return ChatResponse(request_id="r", reply=f"Respuesta a: {message}")


@pytest.fixture
def agent(monkeypatch) -> FakeAgent:
    monkeypatch.setenv("AGENT_API_URL", API_URL)
    monkeypatch.setenv("AGENT_API_TOKEN", "secreto")
    fake = FakeAgent()
    monkeypatch.setattr(agent_client, "ask_agent", fake)
    return fake


def _app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=10)
    at.run()
    assert not at.exception
    return at


def _ask(at: AppTest, text: str) -> None:
    at.chat_input[0].set_value(text).run()
    assert not at.exception


def _texts(at: AppTest) -> list[str]:
    return [md.value for md in at.markdown]


def test_pagina_inicial_sin_llamadas(agent):
    at = _app()
    assert at.title[0].value == "Asistente de análisis de datos"
    assert len(at.chat_message) == 1  # solo el saludo
    assert at.session_state.messages == []
    assert agent.calls == []


def test_pregunta_llama_a_la_api_con_config_y_pinta_la_respuesta(agent):
    at = _app()
    _ask(at, "¿Cuántos viajes hubo?")

    assert agent.calls == [
        {
            "api_url": API_URL,
            "token": "secreto",
            "session_id": at.session_state.session_id,
            "message": "¿Cuántos viajes hubo?",
        }
    ]
    assert "¿Cuántos viajes hubo?" in _texts(at)
    assert "Respuesta a: ¿Cuántos viajes hubo?" in _texts(at)
    assert at.session_state.messages[1]["response"].reply == "Respuesta a: ¿Cuántos viajes hubo?"


def test_varias_preguntas_usan_la_misma_sesion(agent):
    at = _app()
    for question in ("primera", "segunda", "tercera"):
        _ask(at, question)

    assert [c["message"] for c in agent.calls] == ["primera", "segunda", "tercera"]
    assert len({c["session_id"] for c in agent.calls}) == 1
    assert len(at.chat_message) == 1 + 6  # saludo + 3 turnos


def test_nueva_conversacion_regenera_sesion_y_limpia(agent):
    at = _app()
    _ask(at, "primera")
    old_session = at.session_state.session_id

    at.sidebar.button[0].click().run()
    assert at.session_state.session_id != old_session
    assert at.session_state.messages == []
    assert len(at.chat_message) == 1

    _ask(at, "segunda")
    assert agent.calls[-1]["session_id"] == at.session_state.session_id != old_session


def test_error_de_la_api_se_muestra_sin_trazas(agent, monkeypatch):
    fake = FakeAgent([AgentError(agent_client.LLM_DOWN_MESSAGE, 503)])
    monkeypatch.setattr(agent_client, "ask_agent", fake)
    at = _app()
    _ask(at, "hola")

    assert [e.value for e in at.error] == [agent_client.LLM_DOWN_MESSAGE]
    assert not at.exception

    # El error se queda en el historial y la conversacion sigue.
    _ask(at, "otra vez")
    assert [e.value for e in at.error] == [agent_client.LLM_DOWN_MESSAGE]
    assert "Respuesta a: otra vez" in _texts(at)
