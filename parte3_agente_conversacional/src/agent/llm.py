"""Pasarela al LLM via OpenRouter (API compatible con OpenAI).

Expone `LLM.chat(messages, tools)`: intenta primero `LLM_MODEL` y, si
falla por timeout, limite de peticiones o un error del proveedor,
reintenta una vez con `LLM_FALLBACK_MODEL`. Si los dos fallan, lanza
`LLMUnavailable` (la API la convertira en un 503, ver P3-11).

El orquestador (P3-09) y los tests no dependen de esta clase en
concreto: les basta con inyectar cualquier objeto que tenga un metodo
`chat(messages, tools)` con la misma firma (ver `ChatLLM`), como un
LLM falso que sigue un guion fijo.

La clave solo se lee de OPENROUTER_API_KEY (via Config), nunca va
escrita aqui ni en ningun otro fichero del repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from .config import Config, get_config

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Errores del proveedor (no del cliente) que justifican probar el
# modelo de respaldo: timeout, rate limit, conexion, o cualquier otro
# error que OpenRouter/el proveedor upstream devuelva como status HTTP
# (402 sin credito, 404 modelo no encontrado, 5xx, etc).
_RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    APIConnectionError,
    APIStatusError,
)


class LLMUnavailable(Exception):
    """Ni el modelo principal ni el de respaldo han podido responder."""


@dataclass
class LLMUsage:
    """Tokens y coste de una llamada, para el log de P3-11."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass
class LLMResponse:
    """Lo que necesita el orquestador de cada llamada al LLM."""

    message: Any  # ChatCompletionMessage del SDK openai: .content, .tool_calls
    model: str  # modelo que realmente respondio (principal o respaldo)
    usage: LLMUsage = field(default_factory=LLMUsage)


class ChatLLM(Protocol):
    """Protocolo minimo que debe cumplir cualquier LLM (real o falso)."""

    def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None
    ) -> LLMResponse: ...


class LLM:
    """Pasarela a OpenRouter con reintento automatico al modelo de respaldo."""

    def __init__(
        self,
        config: Optional[Config] = None,
        client: Optional[OpenAI] = None,
    ) -> None:
        self._config = config or get_config()
        self._client = client or OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=self._config.openrouter_api_key,
            timeout=self._config.llm_timeout_s,
        )

    def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None
    ) -> LLMResponse:
        try:
            return self._call(self._config.llm_model, messages, tools)
        except _RETRYABLE_EXCEPTIONS as primary_error:
            try:
                return self._call(self._config.llm_fallback_model, messages, tools)
            except _RETRYABLE_EXCEPTIONS as fallback_error:
                raise LLMUnavailable(
                    f"Ni {self._config.llm_model} ({primary_error}) ni "
                    f"{self._config.llm_fallback_model} ({fallback_error}) "
                    "han podido responder."
                ) from fallback_error

    def _call(
        self, model: str, messages: list[dict], tools: Optional[list[dict]]
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._config.llm_temperature,
        }
        if tools:
            kwargs["tools"] = tools

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = resp.usage

        return LLMResponse(
            message=choice.message,
            model=resp.model,
            usage=LLMUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage, "total_tokens", 0) or 0,
                cost=getattr(usage, "cost", 0.0) or 0.0,
            ),
        )


def get_llm() -> LLM:
    """Atajo para obtener una pasarela configurada desde el entorno."""

    return LLM()
