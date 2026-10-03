"""API del agente (P3-11): la unica puerta de entrada al agente.

    uvicorn src.api.main:app --port 8300

Endpoints:
  - POST /chat    ChatRequest -> ChatResponse (con sesion y token).
  - GET  /status  resultado de get_platform_status (barra lateral de la interfaz).
  - GET  /health  sin token, para Docker.

Token: la cabecera X-API-Key debe coincidir con AGENT_API_TOKEN en /chat y
/status (401 si falta o no coincide). Con AGENT_API_TOKEN vacio el token
se desactiva (modo desarrollo).

Errores: si el LLM no esta disponible, 503 con un mensaje claro. Si el
coordinador esta caido, /chat responde 200: el modelo lo explica y la
respuesta lleva `warnings` (lo garantiza el orquestador).

Log: una linea JSON por peticion en stdout (peticion, sesion, longitud del
mensaje -nunca su texto-, herramientas con argumentos, modelo, tokens,
latencias y codigo de estado). /health y la documentacion no se registran.

Ejemplo:

    curl -s localhost:8300/chat -H "X-API-Key: $AGENT_API_TOKEN" \\
         -H "Content-Type: application/json" \\
         -d '{"session_id": "demo", "message": "Compara las tres sedes"}'
"""

from __future__ import annotations

import json
import logging
import secrets
import sys
import threading
import time
import uuid
from typing import Any, Callable, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from ..agent.config import Config, get_config
from ..agent.llm import LLMUnavailable
from ..agent.orchestrator import Orchestrator, get_orchestrator
from ..tools import invoke_tool, register_all_tools
from ..tools.base import ToolError
from .schemas import ChatRequest, ChatResponse
from .sessions import SessionStore

SESSION_TTL_S = 3600.0  # una hora sin uso
LLM_UNAVAILABLE_MESSAGE = (
    "El modelo de lenguaje no está disponible en este momento. "
    "Inténtalo de nuevo en unos minutos."
)
# Rutas que no se registran en el log (ruido de Docker y de la documentacion).
_SILENT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

logger = logging.getLogger("agent.api")


class _StdoutHandler(logging.StreamHandler):
    """Escribe en el sys.stdout de cada momento (asi funciona con la captura de pytest)."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = _StdoutHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def create_app(
    orchestrator: Optional[Orchestrator] = None,
    config: Optional[Config] = None,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    """Crea la aplicacion. Los parametros permiten inyectar un orquestador
    con LLM falso, una configuracion y un reloj en los tests.
    """
    config = config or get_config()
    _configure_logging()

    app = FastAPI(
        title="API del agente",
        description="Asistente conversacional para el análisis de datos de las tres sedes.",
        version="1.0.0",
    )
    sessions = SessionStore(
        ttl_s=SESSION_TTL_S, max_turns=config.max_history_turns, clock=clock
    )
    holder: dict[str, Optional[Orchestrator]] = {"orchestrator": orchestrator}
    holder_lock = threading.Lock()

    def current_orchestrator() -> Orchestrator:
        # Se crea la primera vez que se usa: asi importar el modulo no necesita
        # la clave del LLM ni las herramientas registradas.
        with holder_lock:
            if holder["orchestrator"] is None:
                holder["orchestrator"] = get_orchestrator()
            return holder["orchestrator"]

    def check_token(x_api_key: Optional[str] = Header(default=None)) -> None:
        expected = config.agent_api_token
        if not expected:
            return  # modo desarrollo
        if x_api_key is None or not secrets.compare_digest(
            x_api_key.encode(), expected.encode()
        ):
            raise HTTPException(
                status_code=401,
                detail="Falta la cabecera X-API-Key o no es válida.",
            )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        request.state.log = {}
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            if request.url.path not in _SILENT_PATHS:
                entry: dict[str, Any] = {
                    "event": "request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    **request.state.log,
                }
                logger.info(json.dumps(entry, ensure_ascii=False, default=str))

    @app.get("/health")
    def health() -> dict[str, str]:
        """Comprobación de vida, sin token (healthcheck de Docker)."""
        return {"status": "ok"}

    @app.get("/status", dependencies=[Depends(check_token)])
    def platform_status() -> dict[str, Any]:
        """Estado de la plataforma (resultado de `get_platform_status`).

        Si no se puede obtener, responde 200 con `error` y `detail` en lugar
        de las claves `data`, `meta` y `block`, para que la interfaz lo pinte.
        """
        if orchestrator is None:
            register_all_tools()
        output = invoke_tool("get_platform_status", {})
        if isinstance(output, ToolError):
            return {"error": output.error, "detail": output.detail}
        return output.model_dump(mode="json")

    @app.post("/chat", response_model=ChatResponse, dependencies=[Depends(check_token)])
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        """Una pregunta del usuario y la respuesta del agente (con bloques, fuentes y avisos)."""
        request_id = uuid.uuid4().hex
        log = request.state.log
        log.update(
            request_id=request_id,
            session_id=body.session_id,
            message_chars=len(body.message),
        )

        history = sessions.history(body.session_id)
        try:
            result = current_orchestrator().run(
                body.message, history=history, request_id=request_id
            )
        except LLMUnavailable as error:
            log.update(error="llm_unavailable", detail=str(error)[:300])
            raise HTTPException(status_code=503, detail=LLM_UNAVAILABLE_MESSAGE)

        response = result.response
        sessions.add_turn(body.session_id, body.message, response.reply)
        log.update(
            tools=[
                {
                    "tool": source.tool,
                    "args": source.args,
                    "served_by": source.served_by,
                    "partial": source.partial,
                    "latency_ms": source.latency_ms,
                }
                for source in response.sources
            ],
            warnings=len(response.warnings),
            model=result.model,
            tool_rounds=result.tool_rounds,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            cost=result.usage.cost,
            agent_latency_ms=response.latency_ms,
        )
        return response

    return app


app = create_app()
