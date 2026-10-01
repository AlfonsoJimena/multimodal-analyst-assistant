"""Formato y registro de herramientas de la parte 3.

Cada herramienta (bloques B) valida sus argumentos con un modelo
Pydantic, pide datos a la capa de datos (P3-04) y devuelve un
`ToolResult` (o un `ToolError` si algo va mal). El registro genera el
esquema JSON de tool calling (formato OpenAI) a partir del modelo de
argumentos, para pasárselo al LLM en P3-09.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field

from ..api.schemas import Block


class ToolMeta(BaseModel):
    """Metadatos de trazabilidad que acompañan a todo resultado."""

    sites_ok: list[str] = Field(default_factory=list)
    sites_failed: list[str] = Field(default_factory=list)
    partial: bool = False
    served_by: Optional[str] = None
    period: Optional[str] = None
    note: Optional[str] = None


class ToolResult(BaseModel):
    """Resultado correcto de una herramienta."""

    data: Any
    meta: ToolMeta
    block: Optional[Block] = None


class ToolError(BaseModel):
    """Error controlado de una herramienta (se devuelve al LLM como dato)."""

    error: str
    detail: Optional[str] = None


# Lo que devuelve la funcion de una herramienta.
ToolOutput = Union[ToolResult, ToolError]


@dataclass
class RegisteredTool:
    """Una herramienta registrada: metadatos + modelo de args + funcion."""

    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[BaseModel], ToolOutput]


# Registro global de herramientas.
_REGISTRY: dict[str, RegisteredTool] = {}


def register_tool(
    name: str,
    description: str,
    args_model: type[BaseModel],
    fn: Callable[[BaseModel], ToolOutput],
) -> RegisteredTool:
    """Registra una herramienta y la devuelve."""

    tool = RegisteredTool(
        name=name, description=description, args_model=args_model, fn=fn
    )
    _REGISTRY[name] = tool
    return tool


def get_tool(name: str) -> Optional[RegisteredTool]:
    return _REGISTRY.get(name)


def all_tools() -> list[RegisteredTool]:
    return list(_REGISTRY.values())


def clear_registry() -> None:
    """Vacia el registro (util en tests)."""

    _REGISTRY.clear()


def tool_to_openai_schema(tool: RegisteredTool) -> dict[str, Any]:
    """Genera el esquema de tool calling (formato OpenAI) de una herramienta."""

    parameters = tool.args_model.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters,
        },
    }


def tools_schema() -> list[dict[str, Any]]:
    """Esquema de todas las herramientas registradas, para pasar al LLM."""

    return [tool_to_openai_schema(tool) for tool in all_tools()]
