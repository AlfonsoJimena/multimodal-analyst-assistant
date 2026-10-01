"""Configuracion de la parte 3, leida por completo del entorno.

No hay valores secretos aqui: la clave de OpenRouter solo se lee de la
variable OPENROUTER_API_KEY (en el .env del backend, nunca en el repo).
`Config.from_env()` lee el entorno en el momento de llamarse, asi los
tests pueden fijar variables con monkeypatch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _split_urls(raw: str) -> list[str]:
    """Convierte "a,b,c" en ["a", "b", "c"], ignorando vacios y espacios."""

    return [part.strip() for part in raw.split(",") if part.strip()]


# URLs del coordinador en local (orden de failover: central -> chamartin -> atocha).
DEFAULT_COORDINATOR_URLS = (
    "http://localhost:8100,http://localhost:8101,http://localhost:8102"
)


@dataclass
class Config:
    # --- LLM (OpenRouter, API compatible con OpenAI) ---
    openrouter_api_key: str
    llm_model: str
    llm_fallback_model: str
    llm_temperature: float
    llm_timeout_s: float
    max_tool_rounds: int

    # --- Coordinador de la parte 2 ---
    coordinator_urls: list[str]
    coordinator_timeout_s: float

    # --- Privacidad ---
    min_trips_per_cell: int

    # --- API del agente / interfaz ---
    agent_api_token: str
    agent_api_url: str
    max_history_turns: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            # Modelos PROVISIONALES: la eleccion definitiva es P3-08/P3-16.
            llm_model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
            llm_fallback_model=os.getenv(
                "LLM_FALLBACK_MODEL", "google/gemini-flash-1.5"
            ),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "30")),
            max_tool_rounds=int(os.getenv("MAX_TOOL_ROUNDS", "5")),
            coordinator_urls=_split_urls(
                os.getenv("COORDINATOR_URLS", DEFAULT_COORDINATOR_URLS)
            ),
            coordinator_timeout_s=float(os.getenv("COORDINATOR_TIMEOUT_S", "10")),
            min_trips_per_cell=int(os.getenv("MIN_TRIPS_PER_CELL", "5")),
            agent_api_token=os.getenv("AGENT_API_TOKEN", ""),
            agent_api_url=os.getenv("AGENT_API_URL", "http://localhost:8300"),
            max_history_turns=int(os.getenv("MAX_HISTORY_TURNS", "6")),
        )


def get_config() -> "Config":
    """Atajo para leer la configuracion del entorno."""

    return Config.from_env()
