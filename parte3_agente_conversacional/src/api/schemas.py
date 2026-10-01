"""Contratos compartidos de la parte 3 (formato de /chat).

Estos modelos son el contrato entre la API del agente (P3-11) y la
interfaz (P3-12/13). Las herramientas (bloque B) producen `Block` y
`Source`; el orquestador (P3-09) los ensambla en un `ChatResponse`.

Todas las cifras de los bloques salen SIEMPRE de las herramientas,
nunca del texto del LLM.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Tipos de bloque visual que entiende la interfaz (P3-13).
BlockType = Literal["kpi", "table", "line", "bar"]


class Block(BaseModel):
    """Bloque visual para pintar en la interfaz.

    - kpi:   data = lista de métricas {label, value, unit?}
    - table: data = {columns: [...], rows: [[...], ...]}
    - line:  data = {x: [...], series: [{name, points}]}
    - bar:   data = {categories: [...], series: [{name, values}]}
    El consumidor (interfaz) decide cómo renderizar cada tipo.
    """

    type: BlockType
    title: str
    data: Any
    unit: Optional[str] = None


class Source(BaseModel):
    """Trazabilidad de una llamada a herramienta (de dónde salen las cifras)."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    served_by: Optional[str] = None
    sites_ok: list[str] = Field(default_factory=list)
    sites_failed: list[str] = Field(default_factory=list)
    partial: bool = False
    latency_ms: int = 0


class ChatRequest(BaseModel):
    """Petición entrante a POST /chat."""

    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """Respuesta de POST /chat."""

    request_id: str
    reply: str
    blocks: list[Block] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    latency_ms: int = 0
