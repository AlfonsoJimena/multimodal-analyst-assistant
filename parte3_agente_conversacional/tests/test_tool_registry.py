"""Tests del registro de herramientas y su esquema de tool calling (P3-01)."""

from pydantic import BaseModel, Field

from src.tools.base import (
    ToolMeta,
    ToolResult,
    all_tools,
    clear_registry,
    get_tool,
    register_tool,
    tool_to_openai_schema,
    tools_schema,
)


class _ArgsJuguete(BaseModel):
    """Argumentos de una herramienta de ejemplo."""

    sites: list[str] = Field(default_factory=list, description="Sedes a consultar")
    n: int = Field(5, ge=1, le=20, description="Numero de filas")


def _fn_juguete(args: _ArgsJuguete) -> ToolResult:
    return ToolResult(data=[], meta=ToolMeta(), block=None)


def test_registrar_y_recuperar():
    clear_registry()
    register_tool("juguete", "Una herramienta de juguete", _ArgsJuguete, _fn_juguete)
    tool = get_tool("juguete")
    assert tool is not None
    assert tool.description == "Una herramienta de juguete"
    assert len(all_tools()) == 1


def test_esquema_tool_calling_valido():
    clear_registry()
    register_tool("juguete", "Una herramienta de juguete", _ArgsJuguete, _fn_juguete)
    schema = tool_to_openai_schema(get_tool("juguete"))

    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "juguete"
    assert fn["description"]  # no vacia: forma parte del prompt
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "sites" in params["properties"]
    assert "n" in params["properties"]


def test_tools_schema_es_lista():
    clear_registry()
    register_tool("juguete", "desc", _ArgsJuguete, _fn_juguete)
    todos = tools_schema()
    assert isinstance(todos, list)
    assert len(todos) == 1
    assert todos[0]["function"]["name"] == "juguete"
