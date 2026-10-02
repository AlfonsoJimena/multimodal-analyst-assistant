"""Llamar a las herramientas a mano, sin LLM (relevo B -> C y depuración).

    python -m src.tools --list
    python -m src.tools get_kpis '{"sites": ["central"], "date_from": "2026-09-25"}'
    python -m src.tools get_zone '{"zone_name": "JFK Airport"}'

Usa COORDINATOR_URLS (por defecto, el coordinador real en 8100-8102). Con el
mock: COORDINATOR_URLS=http://localhost:8190 python -m src.tools ...
"""

from __future__ import annotations

import argparse
import json
import sys

from . import invoke_tool, register_all_tools
from .base import ToolResult, all_tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.tools", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", nargs="?", help="nombre de la herramienta")
    parser.add_argument("args", nargs="?", default="{}", help="argumentos en JSON (por defecto {})")
    parser.add_argument("--list", action="store_true", help="lista las herramientas registradas")
    opts = parser.parse_args(argv)

    register_all_tools()
    if opts.list or not opts.name:
        for tool in all_tools():
            print(f"{tool.name:24} {tool.description[:90]}…")
        return 0

    result = invoke_tool(opts.name, opts.args)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if isinstance(result, ToolResult) else 1


if __name__ == "__main__":
    sys.exit(main())
