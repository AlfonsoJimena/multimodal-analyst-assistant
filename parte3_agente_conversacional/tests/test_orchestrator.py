"""Tests del orquestador del dialogo (P3-09). Sin red ni coste: el LLM es
un doble que sigue un guion fijo y las herramientas son de juguete.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from src.agent.config import Config
from src.agent.llm import LLMResponse, LLMUnavailable, LLMUsage
from src.agent.orchestrator import Orchestrator
from src.api.schemas import Block
from src.tools import base
from src.tools.base import ToolError, ToolMeta, ToolResult, register_tool


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
    """LLM falso: devuelve las respuestas del guion, una por llamada."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None):
        # Copia profunda: el orquestador sigue anadiendo mensajes a la lista.
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools})
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _usage() -> LLMUsage:
    return LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0)


def _answer(text: str, model: str = "modelo/principal") -> LLMResponse:
    message = SimpleNamespace(content=text, tool_calls=None)
    return LLMResponse(message=message, model=model, usage=_usage())


def _ask(*calls: Any, model: str = "modelo/principal") -> LLMResponse:
    message = SimpleNamespace(content=None, tool_calls=list(calls))
    return LLMResponse(message=message, model=model, usage=_usage())


def _call(call_id: str, name: str, args: Any) -> SimpleNamespace:
    arguments = args if isinstance(args, str) else json.dumps(args)
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, type="function", function=function)


class _SumArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int
    b: int


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _kpi(title: str, value: Any) -> Block:
    return Block(type="kpi", title=title, data=[{"label": title, "value": value}])


def _suma(args: _SumArgs, client=None) -> ToolResult:
    meta = ToolMeta(sites_ok=["central"], served_by="central", latency_ms=7)
    return ToolResult(
        data={"suma": args.a + args.b},
        meta=meta,
        block=_kpi(f"Suma {args.a}+{args.b}", args.a + args.b),
    )


def _parcial(args: _NoArgs, client=None) -> ToolResult:
    meta = ToolMeta(
        sites_ok=["central", "chamartin"],
        sites_failed=["atocha"],
        partial=True,
        served_by="central",
    )
    return ToolResult(data={"viajes": 100}, meta=meta, block=_kpi("Viajes", 100))


def _caida(args: _NoArgs, client=None) -> ToolError:
    return ToolError(error="coordinador_no_disponible", detail="sin respuesta")


def _serie_larga(args: _NoArgs, client=None) -> ToolResult:
    data = [{"dia": i, "viajes": i * 10} for i in range(300)]
    return ToolResult(data=data, meta=ToolMeta(sites_ok=["central"]))


@pytest.fixture(autouse=True)
def herramientas():
    """Registro con herramientas de juguete; se restaura al acabar."""
    saved = dict(base._REGISTRY)
    base.clear_registry()
    register_tool("suma", "Suma dos enteros", _SumArgs, _suma)
    register_tool("parcial", "Resultado parcial", _NoArgs, _parcial)
    register_tool("caida", "Coordinador caido", _NoArgs, _caida)
    register_tool("serie_larga", "Serie con muchos puntos", _NoArgs, _serie_larga)
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


def _orquestador(llm: FakeLLM, **config_overrides: Any) -> Orchestrator:
    return Orchestrator(llm=llm, config=_config(**config_overrides))


def _tool_messages(call: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in call["messages"] if m["role"] == "tool"]


# ============================================================
# Bucle de tool calling
# ============================================================

def test_respuesta_directa_sin_herramientas():
    llm = FakeLLM([_answer("Hola, ¿en qué te ayudo?")])
    result = _orquestador(llm).run("Hola")

    assert result.response.reply == "Hola, ¿en qué te ayudo?"
    assert result.response.blocks == []
    assert result.response.sources == []
    assert result.response.warnings == []
    assert result.tool_rounds == 0
    assert len(llm.calls) == 1


def test_una_herramienta():
    llm = FakeLLM([_ask(_call("c1", "suma", {"a": 2, "b": 3})), _answer("Son 5.")])
    result = _orquestador(llm).run("¿Cuánto es 2+3?")
    response = result.response

    assert response.reply == "Son 5."
    assert [b.title for b in response.blocks] == ["Suma 2+3"]
    assert len(response.sources) == 1
    source = response.sources[0]
    assert source.tool == "suma"
    assert source.args == {"a": 2, "b": 3}
    assert source.served_by == "central"
    assert source.sites_ok == ["central"]
    assert source.partial is False
    assert source.latency_ms == 7
    assert response.warnings == []
    assert result.tool_rounds == 1

    # Orden correcto: assistant con tool_calls ANTES del mensaje role="tool".
    second = llm.calls[1]["messages"]
    roles = [m["role"] for m in second]
    assert roles == ["system", "user", "assistant", "tool"]
    assert second[2]["tool_calls"][0]["id"] == "c1"
    assert second[3]["tool_call_id"] == "c1"
    assert json.loads(second[3]["content"])["data"] == {"suma": 5}


def test_mensajes_iniciales_sistema_historial_y_pregunta():
    llm = FakeLLM([_answer("ok")])
    history = [
        {"role": "user", "content": "primera"},
        {"role": "assistant", "content": "respuesta"},
    ]
    _orquestador(llm).run("segunda", history=history)

    messages = llm.calls[0]["messages"]
    assert messages[0]["role"] == "system" and messages[0]["content"]
    assert messages[1:] == [
        {"role": "user", "content": "primera"},
        {"role": "assistant", "content": "respuesta"},
        {"role": "user", "content": "segunda"},
    ]


def test_dos_herramientas_en_la_misma_respuesta():
    llm = FakeLLM(
        [
            _ask(
                _call("c1", "suma", {"a": 1, "b": 1}),
                _call("c2", "suma", {"a": 2, "b": 2}),
            ),
            _answer("2 y 4."),
        ]
    )
    result = _orquestador(llm).run("dos sumas")

    assert result.tool_rounds == 1
    assert [b.title for b in result.response.blocks] == ["Suma 1+1", "Suma 2+2"]
    assert [s.args for s in result.response.sources] == [
        {"a": 1, "b": 1},
        {"a": 2, "b": 2},
    ]
    tool_messages = _tool_messages(llm.calls[1])
    assert [m["tool_call_id"] for m in tool_messages] == ["c1", "c2"]
    # Un solo mensaje del asistente con las dos llamadas.
    assistants = [m for m in llm.calls[1]["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 1 and len(assistants[0]["tool_calls"]) == 2


def test_dos_rondas_encadenadas():
    llm = FakeLLM(
        [
            _ask(_call("c1", "suma", {"a": 1, "b": 2})),
            _ask(_call("c2", "suma", {"a": 3, "b": 4})),
            _answer("3 y 7."),
        ]
    )
    result = _orquestador(llm).run("encadena")

    assert result.response.reply == "3 y 7."
    assert result.tool_rounds == 2
    assert len(llm.calls) == 3
    # La tercera llamada ve las dos rondas completas en el historial.
    roles = [m["role"] for m in llm.calls[2]["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "tool"]
    assert len(result.response.sources) == 2


def test_limite_de_rondas_da_respuesta_controlada():
    llm = FakeLLM(
        [
            _ask(_call("c1", "suma", {"a": 1, "b": 1})),
            _ask(_call("c2", "suma", {"a": 2, "b": 2})),
            _ask(_call("c3", "suma", {"a": 3, "b": 3})),
        ]
    )
    result = _orquestador(llm, max_tool_rounds=2).run("no acaba nunca")
    response = result.response

    assert len(llm.calls) == 3  # 2 rondas con herramientas + la llamada que ya no se atiende
    assert result.tool_rounds == 2
    assert "concretar" in response.reply
    assert response.warnings  # avisa del limite
    assert len(response.sources) == 2  # lo ejecutado hasta entonces se conserva


def test_herramienta_desconocida_vuelve_al_modelo_como_dato():
    llm = FakeLLM(
        [_ask(_call("c1", "no_existe", {})), _answer("No puedo hacer eso.")]
    )
    result = _orquestador(llm).run("pregunta")

    content = json.loads(_tool_messages(llm.calls[1])[0]["content"])
    assert content["error"] == "herramienta_desconocida"
    assert result.response.reply == "No puedo hacer eso."
    assert result.response.sources == []


@pytest.mark.parametrize(
    "arguments",
    [
        "{esto no es json",  # JSON roto
        '{"a": "x", "b": 1}',  # tipo incorrecto
        '{"a": 1, "b": 2, "c": 3}',  # campo que no existe
        '{"a": 1}',  # falta un campo
    ],
)
def test_argumentos_invalidos_no_lanzan_y_vuelven_al_modelo(arguments):
    llm = FakeLLM([_ask(_call("c1", "suma", arguments)), _answer("Corrijo.")])
    result = _orquestador(llm).run("pregunta")

    content = json.loads(_tool_messages(llm.calls[1])[0]["content"])
    assert content["error"] == "parametros_invalidos"
    assert result.response.reply == "Corrijo."
    assert result.response.blocks == []
    assert result.response.sources == []


# ============================================================
# blocks / sources / warnings salen de las herramientas
# ============================================================

def test_resultado_parcial_genera_warning_aunque_el_llm_no_lo_diga():
    llm = FakeLLM(
        [_ask(_call("c1", "parcial", {})), _answer("Hubo 100 viajes.")]
    )
    result = _orquestador(llm).run("¿cuántos viajes?")
    response = result.response

    assert "parcial" not in response.reply.lower()  # el modelo no lo menciona
    assert response.warnings
    assert "atocha" in response.warnings[0]
    assert response.sources[0].partial is True
    assert response.sources[0].sites_failed == ["atocha"]


def test_coordinador_caido_genera_warning():
    llm = FakeLLM([_ask(_call("c1", "caida", {})), _answer("No hay datos.")])
    result = _orquestador(llm).run("¿cuántos viajes?")

    assert result.response.warnings
    assert result.response.sources == []
    assert result.response.blocks == []


def test_los_warnings_no_se_repiten():
    llm = FakeLLM(
        [
            _ask(_call("c1", "parcial", {}), _call("c2", "parcial", {})),
            _answer("listo"),
        ]
    )
    result = _orquestador(llm).run("dos veces lo mismo")

    assert len(result.response.warnings) == 1
    assert len(result.response.blocks) == 1  # el mismo bloque no se duplica
    assert len(result.response.sources) == 2


def test_los_bloques_no_salen_del_texto_del_llm():
    llm = FakeLLM([_answer("Hubo 999999 viajes.")])
    result = _orquestador(llm).run("¿cuántos viajes?")

    assert result.response.blocks == []
    assert result.response.sources == []


# ============================================================
# Contexto, historial, registro y errores
# ============================================================

def test_resultados_largos_se_recortan_antes_de_ir_al_llm():
    llm = FakeLLM([_ask(_call("c1", "serie_larga", {})), _answer("ok")])
    _orquestador(llm).run("serie")

    content = _tool_messages(llm.calls[1])[0]["content"]
    parsed = json.loads(content)
    assert parsed["data"]["total_elementos"] == 300
    assert len(parsed["data"]["primeros"]) + len(parsed["data"]["ultimos"]) <= 20
    assert len(content) < 6000


def test_el_historial_se_acota_a_max_history_turns():
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(20)
    ]
    llm = FakeLLM([_answer("ok")])
    _orquestador(llm, max_history_turns=2).run("nueva", history=history)

    messages = llm.calls[0]["messages"]
    assert len(messages) == 1 + 4 + 1  # sistema + 2 turnos + pregunta
    assert messages[1]["content"] == "m16"
    assert messages[-1] == {"role": "user", "content": "nueva"}


def test_las_herramientas_se_descubren_del_registro():
    def _nueva(args: _NoArgs, client=None) -> ToolResult:
        return ToolResult(data={}, meta=ToolMeta())

    register_tool("herramienta_nueva", "Recien anadida", _NoArgs, _nueva)
    llm = FakeLLM([_answer("ok")])
    _orquestador(llm).run("hola")

    names = {t["function"]["name"] for t in llm.calls[0]["tools"]}
    assert {"suma", "parcial", "caida", "serie_larga", "herramienta_nueva"} <= names


def test_suma_el_uso_de_todas_las_llamadas_y_devuelve_el_ultimo_modelo():
    llm = FakeLLM(
        [
            _ask(_call("c1", "suma", {"a": 1, "b": 1}), model="modelo/principal"),
            _answer("2", model="modelo/respaldo"),
        ]
    )
    result = _orquestador(llm).run("1+1")

    assert result.model == "modelo/respaldo"
    assert result.usage.prompt_tokens == 20
    assert result.usage.completion_tokens == 10
    assert result.usage.total_tokens == 30
    assert result.response.request_id
    assert result.response.latency_ms >= 0


def test_respuesta_vacia_del_modelo_da_un_mensaje_controlado():
    llm = FakeLLM([_answer("   ")])
    result = _orquestador(llm).run("hola")

    assert result.response.reply  # nunca vacia


def test_llm_no_disponible_se_propaga():
    llm = FakeLLM([LLMUnavailable("ni principal ni respaldo")])
    with pytest.raises(LLMUnavailable):
        _orquestador(llm).run("hola")
