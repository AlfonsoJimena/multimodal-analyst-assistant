"""Cliente de la API del agente para la interfaz (P3-12).

Es lo UNICO de la interfaz que sale a la red, y solo habla con la API del
agente (P3-11): nunca con el coordinador ni con el LLM.

`ask_agent` nunca lanza: devuelve el `ChatResponse` o un `AgentError` con
un mensaje pensado para el usuario (sin trazas de Python), asi la
interfaz solo tiene que pintarlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

import httpx
from pydantic import ValidationError

from ..api.schemas import ChatResponse

# El agente puede encadenar varias llamadas al LLM (30 s cada una) y a las
# herramientas: la espera tiene que ser bastante mayor que una sola llamada.
REQUEST_TIMEOUT_S = 120.0
CONNECT_TIMEOUT_S = 5.0

UNAVAILABLE_MESSAGE = (
    "El asistente no está disponible ahora mismo. "
    "Inténtalo de nuevo en unos minutos."
)
API_DOWN_MESSAGE = (
    "El asistente no está disponible ahora mismo: no se puede conectar con "
    "su API. Comprueba que está en marcha e inténtalo de nuevo."
)
TIMEOUT_MESSAGE = (
    "El asistente está tardando demasiado en responder. "
    "Inténtalo de nuevo o haz una pregunta más concreta."
)
LLM_DOWN_MESSAGE = (
    "El asistente no está disponible ahora mismo: el modelo de lenguaje no "
    "responde. Inténtalo de nuevo en unos minutos."
)
UNAUTHORIZED_MESSAGE = (
    "La interfaz no tiene permiso para usar el asistente: el token no es "
    "válido. Revisa AGENT_API_TOKEN."
)
INVALID_MESSAGE = (
    "No se ha podido enviar el mensaje: debe tener entre 1 y 2000 caracteres."
)
UNEXPECTED_MESSAGE = (
    "El asistente ha devuelto una respuesta inesperada. "
    "Inténtalo de nuevo en unos minutos."
)


@dataclass
class AgentError:
    """Fallo al hablar con la API, listo para enseñar al usuario."""

    message: str
    status_code: Optional[int] = None


AgentReply = Union[ChatResponse, AgentError]


def _headers(token: str) -> dict[str, str]:
    """Cabecera X-API-Key solo si hay token (vacio = modo desarrollo)."""
    return {"X-API-Key": token} if token else {}


def ask_agent(
    api_url: str,
    token: str,
    session_id: str,
    message: str,
    transport: Optional[httpx.BaseTransport] = None,
) -> AgentReply:
    """Envia una pregunta a POST /chat y devuelve la respuesta o un AgentError."""
    timeout = httpx.Timeout(REQUEST_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.post(
                f"{api_url.rstrip('/')}/chat",
                json={"session_id": session_id, "message": message},
                headers=_headers(token),
            )
    except httpx.TimeoutException:
        return AgentError(TIMEOUT_MESSAGE)
    except httpx.HTTPError:
        return AgentError(API_DOWN_MESSAGE)

    status = response.status_code
    if status == 401:
        return AgentError(UNAUTHORIZED_MESSAGE, status)
    if status == 422:
        return AgentError(INVALID_MESSAGE, status)
    if status == 503:
        return AgentError(LLM_DOWN_MESSAGE, status)
    if status >= 500:
        return AgentError(UNAVAILABLE_MESSAGE, status)
    if status != 200:
        return AgentError(UNEXPECTED_MESSAGE, status)

    try:
        return ChatResponse.model_validate(response.json())
    except (ValueError, ValidationError):
        return AgentError(UNEXPECTED_MESSAGE, status)
