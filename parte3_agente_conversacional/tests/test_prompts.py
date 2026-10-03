"""Tests del prompt de sistema (P3-10). Sin red: lo que se comprueba es el
texto del prompt y que el orquestador lo reconstruye con la fecha de hoy
en cada llamada. El comportamiento real del modelo se prueba a mano con
`python -m src.agent` (ver la issue #108).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from src.agent.config import Config
from src.agent.llm import LLMResponse, LLMUsage
from src.agent.orchestrator import Orchestrator
from src.agent.prompts import build_system_prompt


class _EchoLLM:
    """LLM falso: contesta siempre "ok" y guarda los mensajes recibidos."""

    def __init__(self) -> None:
        self.system_prompts: list[str] = []

    def chat(self, messages, tools=None):
        self.system_prompts.append(messages[0]["content"])
        return LLMResponse(
            message=SimpleNamespace(content="ok", tool_calls=None),
            model="modelo/principal",
            usage=LLMUsage(),
        )


def _config() -> Config:
    return Config(
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


def test_incluye_la_fecha_de_hoy_y_el_dia_de_la_semana():
    prompt = build_system_prompt(date(2026, 10, 3))

    assert "2026-10-03" in prompt
    assert "sábado" in prompt


def test_la_fecha_cambia_el_prompt():
    assert build_system_prompt(date(2026, 10, 3)) != build_system_prompt(date(2026, 10, 4))


def test_sin_argumento_usa_la_fecha_del_sistema():
    assert date.today().isoformat() in build_system_prompt()


def test_contiene_las_reglas_y_el_dominio():
    prompt = build_system_prompt(date(2026, 10, 3))

    # Reglas de la issue: privacidad con alternativa, fechas sin datos, acumulados.
    assert "viajes individuales" in prompt
    assert "get_zone" in prompt and "get_timeseries" in prompt
    assert "get_platform_status" in prompt
    assert "acumulados" in prompt
    assert "parcial" in prompt
    # Conocimiento del dominio: sedes tecnicas, no geograficas.
    assert "no tienen relación geográfica" in prompt
    assert "Nueva York" in prompt
    # Formato.
    assert "punto decimal" in prompt and "dólares" in prompt


def test_es_corto():
    # Se paga en cada llamada. ~4 caracteres por token en espanol.
    assert len(build_system_prompt(date(2026, 10, 3))) < 3500


def test_el_orquestador_inyecta_la_fecha_en_cada_llamada():
    llm = _EchoLLM()
    today = {"value": date(2026, 10, 3)}
    orchestrator = Orchestrator(llm=llm, config=_config(), clock=lambda: today["value"])

    orchestrator.run("hola")
    today["value"] = date(2026, 10, 4)
    orchestrator.run("hola")

    assert "2026-10-03" in llm.system_prompts[0]
    assert "2026-10-04" in llm.system_prompts[1]


def test_un_prompt_fijo_tiene_prioridad():
    llm = _EchoLLM()
    orchestrator = Orchestrator(llm=llm, config=_config(), system_prompt="PROMPT FIJO")

    orchestrator.run("hola")

    assert llm.system_prompts == ["PROMPT FIJO"]
