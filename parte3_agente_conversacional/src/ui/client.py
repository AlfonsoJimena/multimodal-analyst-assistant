"""Cliente de la API del agente para la interfaz (P3-12).

Es lo UNICO de la interfaz que sale a la red, y solo habla con la API del
agente (P3-11): nunca con el coordinador ni con el LLM.

`ask_agent` (POST /chat) y `get_status` (GET /status, P3-13) nunca lanzan:
devuelven la respuesta o un `AgentError` con un mensaje pensado para el
usuario (sin trazas de Python), asi la interfaz solo tiene que pintarlo.
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
# /status consulta /health de cada replica y las fechas: sin LLM, mas corto.
STATUS_TIMEOUT_S = 30.0

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
STATUS_UNKNOWN_MESSAGE = (
    "No se ha podido comprobar el estado de la plataforma."
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
StatusReply = Union[dict, AgentError]


def _headers(token: str) -> dict[str, str]:
    """Cabecera X-API-Key solo si hay token (vacio = modo desarrollo)."""
    return {"X-API-Key": token} if token else {}


def _request(
    method: str,
    url: str,
    token: str,
    timeout_s: float,
    transport: Optional[httpx.BaseTransport],
    **kwargs,
) -> Union[httpx.Response, AgentError]:
    """Hace la peticion y traduce los fallos de red y los codigos de error."""
    timeout = httpx.Timeout(timeout_s, connect=CONNECT_TIMEOUT_S)
    try:
        with httpx.Client(timeout=timeout, transport=transport) as client:
            response = client.request(method, url, headers=_headers(token), **kwargs)
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
    return response


def ask_agent(
    api_url: str,
    token: str,
    session_id: str,
    message: str,
    transport: Optional[httpx.BaseTransport] = None,
) -> AgentReply:
    """Envia una pregunta a POST /chat y devuelve la respuesta o un AgentError."""
    response = _request(
        "POST",
        f"{api_url.rstrip('/')}/chat",
        token,
        REQUEST_TIMEOUT_S,
        transport,
        json={"session_id": session_id, "message": message},
    )
    if isinstance(response, AgentError):
        return response
    try:
        return ChatResponse.model_validate(response.json())
    except (ValueError, ValidationError):
        return AgentError(UNEXPECTED_MESSAGE, response.status_code)


def get_status(
    api_url: str,
    token: str,
    transport: Optional[httpx.BaseTransport] = None,
) -> StatusReply:
    """Estado de la plataforma (GET /status): el `data` de get_platform_status.

    Devuelve {coordinator, replicas, sites, first_date, last_date,
    dates_with_data, ...} mas `note`, o un AgentError si la API no responde
    o no ha podido comprobar el estado.
    """
    response = _request(
        "GET", f"{api_url.rstrip('/')}/status", token, STATUS_TIMEOUT_S, transport
    )
    if isinstance(response, AgentError):
        return response
    try:
        body = response.json()
    except ValueError:
        return AgentError(UNEXPECTED_MESSAGE, response.status_code)
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or "sites" not in data:
        return AgentError(STATUS_UNKNOWN_MESSAGE, response.status_code)
    note = (body.get("meta") or {}).get("note")
    return {**data, "note": note}
