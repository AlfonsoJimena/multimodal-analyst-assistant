"""Hablar con el agente desde la terminal (depuración y prueba con el LLM real).

    python -m src.agent "¿Cuántos viajes hubo en la sede central?"
    python -m src.agent --json "Compara las tres sedes"

Usa el LLM de OpenRouter (OPENROUTER_API_KEY, LLM_MODEL...) y las herramientas
contra COORDINATOR_URLS (con el mock: http://localhost:8190). Las variables se
leen del entorno; para cargar tu .env:

    set -a; source .env; set +a

Cada pregunta gasta al menos 2 peticiones del limite diario de la cuenta.
"""

from __future__ import annotations

import argparse
import sys

from .llm import LLMUnavailable
from .orchestrator import get_orchestrator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.agent",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("question", help="pregunta para el agente")
    parser.add_argument(
        "--json", action="store_true", help="imprime el ChatResponse completo en JSON"
    )
    opts = parser.parse_args(argv)

    orchestrator = get_orchestrator()
    try:
        result = orchestrator.run(opts.question)
    except LLMUnavailable as error:
        print(f"LLM no disponible: {error}", file=sys.stderr)
        return 2

    response = result.response
    if opts.json:
        print(response.model_dump_json(indent=2))
        return 0

    print(f"Pregunta:  {opts.question}")
    print(f"Respuesta: {response.reply}")

    print(f"\nBloques ({len(response.blocks)}):")
    for block in response.blocks:
        print(f"  - [{block.type}] {block.title}")

    print(f"\nFuentes ({len(response.sources)}):")
    for source in response.sources:
        estado = "PARCIAL" if source.partial else "ok"
        print(
            f"  - {source.tool} {source.args} -> {estado}, "
            f"servido por {source.served_by}, sedes ok={source.sites_ok} "
            f"caidas={source.sites_failed}, {source.latency_ms} ms"
        )

    print(f"\nAvisos ({len(response.warnings)}):")
    for warning in response.warnings:
        print(f"  - {warning}")

    usage = result.usage
    print(
        f"\nModelo: {result.model} | rondas: {result.tool_rounds} | "
        f"tokens: {usage.total_tokens} | latencia: {response.latency_ms} ms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
