"""Tests de la pasarela LLM (P3-08). Sin red: el cliente OpenAI se
sustituye por un doble de prueba que sigue un guion fijo.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from openai import APIStatusError, RateLimitError

from src.agent.config import Config
from src.agent.llm import LLM, LLMUnavailable


def _config(**overrides: Any) -> Config:
    base = dict(
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
    base.update(overrides)
    return Config(**base)


def _fake_response(model: str, content: str = "hola", tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0001
    )
    return SimpleNamespace(model=model, choices=[choice], usage=usage)


def _api_status_error(status_code: int) -> APIStatusError:
    """Construye un APIStatusError como lo haria el SDK de openai."""

    request = SimpleNamespace()
    response = SimpleNamespace(status_code=status_code, headers={}, request=request)
    return APIStatusError("error del proveedor", response=response, body=None)


class _ScriptedClient:
    """Doble del cliente openai: una cola de resultados por llamada.

    Cada elemento de `script` es una respuesta (se devuelve tal cual)
    o una excepcion (se lanza). `calls` guarda el modelo pedido en
    cada llamada, para comprobar el orden principal -> respaldo.
    """

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any):
        self.calls.append(kwargs["model"])
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_chat_usa_el_modelo_principal_si_responde():
    client = _ScriptedClient([_fake_response("modelo/principal", "hola")])
    llm = LLM(config=_config(), client=client)

    result = llm.chat(messages=[{"role": "user", "content": "hola"}])

    assert result.model == "modelo/principal"
    assert result.message.content == "hola"
    assert result.usage.total_tokens == 15
    assert client.calls == ["modelo/principal"]


def test_chat_reintenta_con_el_respaldo_si_el_principal_falla():
    client = _ScriptedClient(
        [
            RateLimitError("limite alcanzado", response=SimpleNamespace(status_code=429, headers={}, request=SimpleNamespace()), body=None),
            _fake_response("modelo/respaldo", "hola desde el respaldo"),
        ]
    )
    llm = LLM(config=_config(), client=client)

    result = llm.chat(messages=[{"role": "user", "content": "hola"}])

    assert result.model == "modelo/respaldo"
    assert result.message.content == "hola desde el respaldo"
    assert client.calls == ["modelo/principal", "modelo/respaldo"]


def test_chat_lanza_llmunavailable_si_fallan_los_dos():
    client = _ScriptedClient(
        [
            _api_status_error(402),
            _api_status_error(404),
        ]
    )
    llm = LLM(config=_config(), client=client)

    with pytest.raises(LLMUnavailable):
        llm.chat(messages=[{"role": "user", "content": "hola"}])

    assert client.calls == ["modelo/principal", "modelo/respaldo"]


def test_chat_pasa_las_tools_cuando_se_le_dan():
    client = _ScriptedClient([_fake_response("modelo/principal")])
    llm = LLM(config=_config(), client=client)
    tools = [{"type": "function", "function": {"name": "foo"}}]

    llm.chat(messages=[{"role": "user", "content": "hola"}], tools=tools)

    # El doble no registra kwargs completos; probamos indirectamente
    # con un doble que si los guarda.
    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        return _fake_response("modelo/principal")

    client2 = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    llm2 = LLM(config=_config(), client=client2)
    llm2.chat(messages=[{"role": "user", "content": "hola"}], tools=tools)
    assert captured["tools"] == tools
