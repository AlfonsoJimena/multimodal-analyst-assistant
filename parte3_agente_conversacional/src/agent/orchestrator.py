"""Orquestador del dialogo (P3-09): el bucle de tool calling.

Recibe el historial y la pregunta, llama al LLM con los esquemas de las
herramientas registradas, ejecuta las que pida el modelo, le devuelve los
resultados y repite hasta tener la respuesta final (o hasta agotar
MAX_TOOL_ROUNDS).

`blocks`, `sources` y `warnings` de la respuesta se construyen SIEMPRE a
partir de los resultados de las herramientas, nunca del texto del LLM:
asi un grafico no lleva una cifra inventada y el aviso de resultado
parcial aparece aunque el modelo se olvide de mencionarlo.

Las herramientas se descubren del registro (`tools_schema()`), asi que
anadir una no obliga a tocar este fichero.

Uso:

    orchestrator = get_orchestrator()      # registra las herramientas
    result = orchestrator.run("¿Cuántos viajes hubo ayer?", history)
    result.response                        # ChatResponse para la API (P3-11)

Si ni el modelo principal ni el de respaldo responden, `run` deja subir
`LLMUnavailable` (P3-11 la convierte en un 503).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from ..api.schemas import Block, ChatResponse, Source
from ..tools import invoke_tool, register_all_tools
from ..tools.base import ToolError, ToolOutput, ToolResult, tools_schema
from .config import Config, get_config
from .llm import ChatLLM, LLMUsage, get_llm

# Prompt minimo provisional: lo sustituye el definitivo de P3-10.
SYSTEM_PROMPT_PROVISIONAL = (
    "Eres un asistente que ayuda a analistas de datos a consultar métricas "
    "de viajes en taxi de tres sedes (central, chamartin y atocha). "
    "Responde siempre en español. Usa las herramientas para obtener "
    "cualquier cifra y no inventes datos. Si una herramienta devuelve un "
    "resultado parcial o un error, dilo con claridad. Si la pregunta es "
    "ambigua, pide que la concreten."
)

LIMIT_REPLY = (
    "No he conseguido completar la consulta en el número de pasos "
    "permitido. ¿Puedes concretar más la pregunta (sede, periodo o métrica)?"
)
EMPTY_REPLY = (
    "No he podido generar una respuesta. ¿Puedes reformular la pregunta?"
)

# Contexto acotado: lo que se manda al LLM de cada resultado.
MAX_ROWS_TO_LLM = 20
MAX_CHARS_TO_LLM = 6000

# Errores de herramienta que significan "no hay datos porque el
# coordinador (o todas las sedes pedidas) no responde".
_DATA_UNAVAILABLE = {"coordinador_no_disponible", "sedes_no_disponibles"}


@dataclass
class OrchestratorResult:
    """Lo que devuelve `run`: la respuesta de la API y los datos para el log."""

    response: ChatResponse
    model: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)
    tool_rounds: int = 0


@dataclass
class _Collected:
    """Bloques, fuentes y avisos acumulados de los resultados de herramientas."""

    blocks: list[Block] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def add(self, name: str, args: dict[str, Any], output: ToolOutput) -> None:
        if isinstance(output, ToolError):
            if output.error in _DATA_UNAVAILABLE:
                self.warn(
                    f"No se han podido obtener datos con {name}: "
                    f"{output.detail or output.error}"
                )
            return

        for block in output.blocks:
            if block not in self.blocks:
                self.blocks.append(block)

        meta = output.meta
        self.sources.append(
            Source(
                tool=name,
                args=args,
                served_by=meta.served_by,
                sites_ok=list(meta.sites_ok),
                sites_failed=list(meta.sites_failed),
                partial=meta.partial,
                latency_ms=meta.latency_ms,
            )
        )
        if meta.partial:
            failed = ", ".join(meta.sites_failed) or "alguna sede"
            self.warn(
                f"Resultado parcial de {name}: no han respondido {failed}; "
                "las cifras no incluyen esas sedes."
            )


# ============================================================
# Utilidades (sin estado)
# ============================================================

def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _compact(value: Any, max_rows: int) -> Any:
    """Resume las listas largas (series) para no gastar contexto del LLM."""
    if isinstance(value, list):
        if len(value) > max_rows:
            tail = max(1, max_rows // 4)
            head = max_rows - tail
            return {
                "total_elementos": len(value),
                "primeros": [_compact(v, max_rows) for v in value[:head]],
                "ultimos": [_compact(v, max_rows) for v in value[-tail:]],
                "nota": "Lista resumida: solo se muestran los primeros y los últimos.",
            }
        return [_compact(v, max_rows) for v in value]
    if isinstance(value, dict):
        return {k: _compact(v, max_rows) for k, v in value.items()}
    return value


def _dump(payload: dict[str, Any], max_rows: int) -> str:
    return json.dumps(
        _compact(payload, max_rows), ensure_ascii=False, default=_json_default
    )


def _tool_content(output: ToolOutput) -> str:
    """Texto (JSON) que se devuelve al LLM como mensaje role="tool"."""
    if isinstance(output, ToolError):
        return _dump({"error": output.error, "detail": output.detail}, MAX_ROWS_TO_LLM)

    meta = output.meta.model_dump(exclude={"latency_ms"}, exclude_none=True)
    payload = {"data": output.data, "meta": meta}
    text = ""
    for max_rows in (MAX_ROWS_TO_LLM, 6, 2):
        text = _dump(payload, max_rows)
        if len(text) <= MAX_CHARS_TO_LLM:
            return text
    return text[:MAX_CHARS_TO_LLM] + " …(recortado)"


def _parse_args(raw: str) -> dict[str, Any]:
    """Argumentos tal como los mandó el modelo (para `sources`); {} si no son un objeto JSON."""
    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_calls(tool_calls: list[Any], round_index: int) -> list[dict[str, str]]:
    """Pasa los tool_calls del SDK a dicts simples (id, nombre, argumentos en texto)."""
    calls = []
    for position, call in enumerate(tool_calls):
        function = getattr(call, "function", None)
        raw = getattr(function, "arguments", None)
        if raw is None:
            raw = "{}"
        elif not isinstance(raw, str):
            raw = json.dumps(raw, ensure_ascii=False, default=_json_default)
        calls.append(
            {
                "id": getattr(call, "id", None) or f"call_{round_index}_{position}",
                "name": getattr(function, "name", None) or "",
                "arguments": raw,
            }
        )
    return calls


def _assistant_message(content: Optional[str], calls: list[dict[str, str]]) -> dict[str, Any]:
    """Mensaje del asistente con sus tool_calls (va ANTES de los role="tool")."""
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"]},
            }
            for call in calls
        ],
    }


def _history_messages(history: Optional[list[dict]], max_turns: int) -> list[dict]:
    """Ultimos `max_turns` turnos (usuario + asistente) del historial."""
    if max_turns <= 0:
        return []
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"]
    ]
    return clean[-2 * max_turns :]


def _add_usage(total: LLMUsage, usage: LLMUsage) -> None:
    total.prompt_tokens += usage.prompt_tokens
    total.completion_tokens += usage.completion_tokens
    total.total_tokens += usage.total_tokens
    total.cost += usage.cost


# ============================================================
# Orquestador
# ============================================================

class Orchestrator:
    """Gestion del dialogo: LLM + herramientas -> ChatResponse."""

    def __init__(
        self,
        llm: Optional[ChatLLM] = None,
        config: Optional[Config] = None,
        client: Any = None,
        system_prompt: str = SYSTEM_PROMPT_PROVISIONAL,
    ) -> None:
        self._config = config or get_config()
        self._llm = llm or get_llm()
        self._client = client  # cliente del coordinador, se pasa tal cual a las tools
        self._system_prompt = system_prompt

    def run(
        self,
        message: str,
        history: Optional[list[dict]] = None,
        request_id: Optional[str] = None,
    ) -> OrchestratorResult:
        started = time.perf_counter()
        max_rounds = self._config.max_tool_rounds

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
            *_history_messages(history, self._config.max_history_turns),
            {"role": "user", "content": message},
        ]
        schemas = tools_schema()
        collected = _Collected()
        usage = LLMUsage()
        model = ""
        rounds = 0
        reply: Optional[str] = None
        limit_reached = False

        # Hasta max_rounds rondas con herramientas + una llamada final.
        for attempt in range(max_rounds + 1):
            response = self._llm.chat(messages, schemas or None)
            model = response.model
            _add_usage(usage, response.usage)

            assistant = response.message
            tool_calls = list(getattr(assistant, "tool_calls", None) or [])
            if not tool_calls:
                reply = (getattr(assistant, "content", None) or "").strip()
                break
            if attempt == max_rounds:
                limit_reached = True
                break

            rounds += 1
            calls = _normalize_calls(tool_calls, attempt)
            messages.append(
                _assistant_message(getattr(assistant, "content", None), calls)
            )
            for call in calls:
                output = invoke_tool(call["name"], call["arguments"], client=self._client)
                collected.add(call["name"], _parse_args(call["arguments"]), output)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": _tool_content(output),
                    }
                )

        if limit_reached:
            reply = LIMIT_REPLY
            collected.warn(
                f"Se alcanzó el límite de {max_rounds} rondas de herramientas "
                "sin llegar a una respuesta final."
            )
        elif not reply:
            reply = EMPTY_REPLY

        chat_response = ChatResponse(
            request_id=request_id or uuid.uuid4().hex,
            reply=reply,
            blocks=collected.blocks,
            sources=collected.sources,
            warnings=collected.warnings,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return OrchestratorResult(
            response=chat_response, model=model, usage=usage, tool_rounds=rounds
        )


def get_orchestrator() -> Orchestrator:
    """Registra las herramientas y devuelve un orquestador con el LLM real."""
    register_all_tools()
    return Orchestrator()
