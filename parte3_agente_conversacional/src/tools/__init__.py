"""Herramientas del agente.

El orquestador (P3-09) solo necesita dos cosas:

    from src.tools import register_all_tools, invoke_tool
    from src.tools.base import tools_schema

    register_all_tools()          # una vez al arrancar
    tools_schema()                # esquemas para el LLM
    invoke_tool(name, arguments)  # ToolResult o ToolError, nunca lanza
"""

from .common import invoke_tool


def register_all_tools() -> None:
    """Registra todas las herramientas del agente (idempotente)."""
    from . import breakdowns, metrics, status

    metrics.register()
    breakdowns.register()
    status.register()


__all__ = ["invoke_tool", "register_all_tools"]
