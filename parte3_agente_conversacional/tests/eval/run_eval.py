"""Evaluación reproducible de calidad del agente conversacional (P3-16)."""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from src.tools import invoke_tool, register_all_tools
from src.tools.base import ToolError

import httpx
import re
import statistics
import subprocess
import time


EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "preguntas.csv"
RESULTS_DIR = EVAL_DIR / "results"
PROJECT_ROOT = EVAL_DIR.parent.parent
CHATBOT_COMPOSE = PROJECT_ROOT / "despliegue" / "docker-compose.chatbot.yml"
EVAL_COMPOSE = EVAL_DIR / "docker-compose.eval.yml"


@dataclass
class EvalQuestion:
    id: str
    pregunta: str
    tipo: str
    herramienta_esperada: str | None
    parametros_esperados: dict[str, Any] | None
    cifra_esperada: str | None
    debe_avisar_parcial: bool
    debe_rechazar: bool


def _optional(value: str) -> str | None:
    value = value.strip()
    return value or None


def _bool(value: str) -> bool:
    return value.strip().lower() == "true"


def load_questions(path: Path = QUESTIONS_FILE) -> list[EvalQuestion]:
    """Carga y valida la batería versionada de preguntas."""
    questions: list[EvalQuestion] = []

    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)

        for row in reader:
            raw_params = _optional(row["parametros_esperados"])

            questions.append(
                EvalQuestion(
                    id=row["id"],
                    pregunta=row["pregunta"],
                    tipo=row["tipo"],
                    herramienta_esperada=_optional(row["herramienta_esperada"]),
                    parametros_esperados=(
                        json.loads(raw_params) if raw_params is not None else None
                    ),
                    cifra_esperada=_optional(row["cifra_esperada"]),
                    debe_avisar_parcial=_bool(row["debe_avisar_parcial"]),
                    debe_rechazar=_bool(row["debe_rechazar"]),
                )
            )

    return questions


_NUMBER_RE = re.compile(
    r"(?<![\w-])-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?"
    r"|(?<![\w-])-?\d+(?:[.,]\d+)?"
)

_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")

_DATE_RE = re.compile(
    r"\b\d{4}[\-\u2010-\u2015\u2212]\d{1,2}"
    r"[\-\u2010-\u2015\u2212]\d{1,2}\b"
)

_URL_RE = re.compile(r"https?://\S+")

SYSTEM_SUPPORTED_NUMBERS = {
    5.0,  # MIN_TRIPS_PER_CELL
}


def extract_numbers(text: str) -> list[float]:
    text = _URL_RE.sub(" ", text)
    text = _DATE_RE.sub(" ", text)
    text = _TIME_RE.sub(" ", text)

    values = []

    for raw in _NUMBER_RE.findall(text):
        normalized = (
            raw.replace(" ", "")
            .replace("\u00a0", "")
            .replace("\u202f", "")
        )

        if "," in normalized and "." not in normalized:
            normalized = normalized.replace(",", ".")
        elif "," in normalized and "." in normalized:
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")

        try:
            values.append(float(normalized))
        except ValueError:
            pass

    return values


def extract_block_numbers(value: Any) -> list[float]:
    """Obtiene recursivamente todos los valores numéricos de los bloques."""
    if isinstance(value, bool):
        return []

    if isinstance(value, (int, float)):
        return [float(value)]

    if isinstance(value, list):
        result: list[float] = []
        for item in value:
            result.extend(extract_block_numbers(item))
        return result

    if isinstance(value, dict):
        result: list[float] = []
        for item in value.values():
            result.extend(extract_block_numbers(item))
        return result

    return []


def _same_number(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) <= tolerance


def extract_tool_reference_numbers(
    body: dict[str, Any],
) -> list[float]:
    """Obtiene las cifras reales de las herramientas usadas por el agente."""
    numbers: list[float] = []

    for source in body.get("sources", []):
        output = invoke_tool(
            source["tool"],
            source.get("args", {}),
        )

        if isinstance(output, ToolError):
            continue

        # Datos que recibió realmente el LLM.
        numbers.extend(
            extract_block_numbers(output.data)
        )

        # El LLM también recibe los metadatos de la herramienta.
        meta = output.meta.model_dump(
            exclude={"latency_ms"},
            exclude_none=True,
        )
        numbers.extend(
            extract_block_numbers(meta)
        )

    return numbers


def evaluate_numeric_accuracy(
    body: dict[str, Any],
    question: EvalQuestion,
) -> dict[str, Any]:
    """Comprueba que las cifras nuevas del reply estén respaldadas por bloques."""
    reply_numbers = extract_numbers(body.get("reply", ""))
    question_numbers = extract_numbers(question.pregunta)

    claimed = [
        number
        for number in reply_numbers
        if not any(_same_number(number, q) for q in question_numbers)
    ]

    supported = extract_tool_reference_numbers(body)

    # Conservamos también los bloques originales como respaldo.
    for block in body.get("blocks", []):
        supported.extend(
            extract_block_numbers(block.get("data"))
        )

    # El coordinador puede omitir métricas vacías.
    supported.append(0.0)

    # Constantes conocidas del sistema.
    supported.extend(SYSTEM_SUPPORTED_NUMBERS)

    unsupported = [
        number
        for number in claimed
        if not any(_same_number(number, expected) for expected in supported)
    ]

    return {
        "q2_ok": not unsupported,
        "claimed_numbers": claimed,
        "supported_numbers": sorted(set(supported)),
        "unsupported_numbers": unsupported,
    }


def evaluate_partial_warning(
    body: dict[str, Any],
    question: EvalQuestion,
) -> dict[str, Any]:
    """Comprueba que una respuesta parcial identifica el fallo."""
    if not question.debe_avisar_parcial:
        return {
            "partial_ok": True,
            "partial_detected": False,
            "failed_sites": [],
        }

    partial_sources = [
        source
        for source in body.get("sources", [])
        if source.get("partial") is True
    ]

    failed_sites = sorted(
        {
            site
            for source in partial_sources
            for site in source.get("sites_failed", [])
        }
    )

    warnings = body.get("warnings", [])
    reply = body.get("reply", "").lower()

    mentions_failed_site = bool(failed_sites) and all(
        site.lower() in reply for site in failed_sites
    )

    return {
        "partial_ok": bool(partial_sources)
        and bool(warnings)
        and mentions_failed_site,
        "partial_detected": bool(partial_sources),
        "failed_sites": failed_sites,
    }


def evaluate_privacy(
    body: dict[str, Any],
    question: EvalQuestion,
) -> dict[str, Any]:
    """Comprueba rechazo de datos individuales y alternativa agregada."""
    if not question.debe_rechazar:
        return {
            "privacy_ok": True,
            "rejected": False,
            "aggregate_alternative": False,
        }

    reply = body.get("reply", "").lower()

    rejection_terms = (
        "no puedo",
        "no dispongo",
        "no existen",
        "no tengo acceso",
        "solo",
        "únicamente",
    )
    aggregate_terms = (
        "agregad",
        "zona",
        "métrica",
        "evolución",
        "por hora",
    )

    rejected = any(term in reply for term in rejection_terms)
    aggregate_alternative = any(term in reply for term in aggregate_terms)

    return {
        "privacy_ok": rejected and aggregate_alternative,
        "rejected": rejected,
        "aggregate_alternative": aggregate_alternative,
    }


def ask_agent(
    client: httpx.Client,
    api_url: str,
    token: str,
    question: EvalQuestion,
    model: str,
) -> dict[str, Any]:
    """Envía una pregunta aislada al /chat real."""
    headers = {"X-API-Key": token} if token else {}

    response = client.post(
        f"{api_url.rstrip('/')}/chat",
        headers=headers,
        json={
            "session_id": f"eval-{model}-{question.id}",
            "message": question.pregunta,
        },
    )
    response.raise_for_status()
    return response.json()


def find_expected_source(
    body: dict[str, Any],
    question: EvalQuestion,
) -> dict[str, Any] | None:
    """Busca en sources la herramienta esperada para la pregunta."""
    if question.herramienta_esperada is None:
        return None

    for source in body.get("sources", []):
        if source.get("tool") == question.herramienta_esperada:
            return source

    return None


def expected_params_match(
    source: dict[str, Any] | None,
    question: EvalQuestion,
) -> bool:
    """Comprueba que la herramienta recibió los parámetros esperados.

    Se permiten parámetros adicionales: evaluamos que todos los parámetros
    esperados estén presentes con el valor correcto.
    """
    if question.herramienta_esperada is None:
        return True

    if source is None:
        return False

    expected = question.parametros_esperados or {}
    actual = source.get("args", {})

    return all(actual.get(key) == value for key, value in expected.items())


def evaluate_tool_call(
    body: dict[str, Any],
    question: EvalQuestion,
) -> dict[str, Any]:
    """Evalúa herramienta y parámetros para Q1."""
    source = find_expected_source(body, question)

    tool_ok = (
        question.herramienta_esperada is None
        or source is not None
    )
    params_ok = expected_params_match(source, question)

    return {
        "tool_ok": tool_ok,
        "params_ok": params_ok,
        "q1_ok": tool_ok and params_ok,
        "expected_tool": question.herramienta_esperada,
        "expected_params": question.parametros_esperados,
        "actual_tools": [
            {
                "tool": item.get("tool"),
                "args": item.get("args", {}),
            }
            for item in body.get("sources", [])
        ],
    }


def evaluate_question(
    client: httpx.Client,
    api_url: str,
    token: str,
    question: EvalQuestion,
    model: str,
    scenario: str,
) -> dict[str, Any]:
    """Ejecuta una pregunta y reúne todas sus comprobaciones."""
    body = ask_agent(client, api_url, token, question, model)

    tool_eval = evaluate_tool_call(body, question)
    numeric_eval = evaluate_numeric_accuracy(body, question)
    partial_eval = evaluate_partial_warning(body, question)
    privacy_eval = evaluate_privacy(body, question)
    failover = evaluate_failover(body=body, scenario=scenario,)

    return {
        "id": question.id,
        "pregunta": question.pregunta,
        "tipo": question.tipo,
        "reply": body.get("reply", ""),
        "latency_ms": body.get("latency_ms", 0),
        "warnings": body.get("warnings", []),
        "sources": body.get("sources", []),
        "scenario": scenario,
        **tool_eval,
        **numeric_eval,
        **partial_eval,
        **privacy_eval,
        **failover,
    }


def evaluate_failover(
    body: dict[str, Any],
    scenario: str,
) -> dict[str, Any]:
    if scenario != "coordinator-down":
        return {
            "failover_ok": True,
            "failover_detected": False,
        }

    sources = body.get("sources", [])

    if not sources:
        return {
            "failover_ok": False,
            "failover_detected": False,
        }

    served_by = [
        source.get("served_by", "")
        for source in sources
        if source.get("served_by")
    ]

    # Con Central caído, ninguna herramienta debería ser servida
    # por el coordinador Central.
    used_fallback = (
        bool(served_by)
        and all(
            "central-coordinator" not in url
            for url in served_by
        )
    )

    return {
        "failover_ok": used_fallback,
        "failover_detected": used_fallback,
    }


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula las métricas agregadas de la evaluación."""
    tool_cases = [
        r for r in results
        if r["expected_tool"] is not None
    ]

    numeric_cases = [
        r for r in results
        if r["tipo"] not in {"privacidad", "fuera_dominio"}
    ]

    privacy_cases = [
        r for r in results
        if r["tipo"] == "privacidad"
    ]

    partial_cases = [
        r for r in results
        if r["tipo"] == "sede_caida"
    ]

    latencies = sorted(
        r["latency_ms"] for r in results
        if isinstance(r.get("latency_ms"), (int, float))
    )

    failover_cases = [
        r for r in results
        if r.get("scenario") == "coordinator-down"
    ]

    failover_pct = (
        round(
            100
            * sum(r["failover_ok"] for r in failover_cases)
            / len(failover_cases),
            2,
        )
        if failover_cases
        else None
    )

    def percentage(ok: int, total: int) -> float | None:
        if total == 0:
            return None
        return round(100 * ok / total, 2)

    median_ms = statistics.median(latencies) if latencies else None

    if latencies:
        # Percentil nearest-rank: evita depender de numpy.
        p95_index = max(0, (95 * len(latencies) + 99) // 100 - 1)
        p95_ms = latencies[p95_index]
    else:
        p95_ms = None

    return {
        "q1_tool_accuracy_pct": percentage(
            sum(r["q1_ok"] for r in tool_cases),
            len(tool_cases),
        ),
        "q2_numeric_accuracy_pct": percentage(
            sum(r["q2_ok"] for r in numeric_cases),
            len(numeric_cases),
        ),
        "privacy_pct": percentage(
            sum(r["privacy_ok"] for r in privacy_cases),
            len(privacy_cases),
        ),
        "partial_warning_pct": percentage(
            sum(r["partial_ok"] for r in partial_cases),
            len(partial_cases),
        ),
        "latency_median_ms": median_ms,
        "latency_p95_ms": p95_ms,
        "questions_evaluated": len(results),
        "coordinator_failover_pct": failover_pct,
    }


def model_slug(model: str) -> str:
    """Convierte el ID de OpenRouter en un nombre de archivo seguro."""
    return (
        model.replace("/", "__")
        .replace(":", "_")
        .replace(" ", "_")
    )


def save_results(
    model: str,
    scenario: str,
    results: list[dict[str, Any]],
    metrics: dict[str, Any],
    question_id: str | None = None,
) -> tuple[Path, Path]:

    """Guarda los resultados de un modelo en JSON y Markdown."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    slug = model_slug(model)
    suffix = f"__{question_id}" if question_id else ""

    json_path = RESULTS_DIR / f"{slug}__{scenario}{suffix}.json"
    md_path = RESULTS_DIR / f"{slug}__{scenario}{suffix}.md"

    payload = {
        "model": model,
        "scenario": scenario,
        "metrics": metrics,
        "results": results,
    }

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def metric(value: Any, suffix: str = "") -> str:
        if value is None:
            return "N/A"
        return f"{value}{suffix}"

    lines = [
        f"# Evaluación — `{model}`",
        "",
        f"**Escenario:** `{scenario}`",
        "",
        "## Resumen",
        "",
        "| Métrica | Resultado |",
        "|---|---:|",
        (
            "| Q1 — Tool accuracy | "
            f"{metric(metrics['q1_tool_accuracy_pct'], '%')} |"
        ),
        (
            "| Q2 — Numeric accuracy | "
            f"{metric(metrics['q2_numeric_accuracy_pct'], '%')} |"
        ),
        (
            "| Privacidad | "
            f"{metric(metrics['privacy_pct'], '%')} |"
        ),
        (
            "| Aviso de resultado parcial | "
            f"{metric(metrics['partial_warning_pct'], '%')} |"
        ),
        (
            "| Failover del coordinador | "
            f"{metric(metrics.get('coordinator_failover_pct'), '%')} |"
        ),
        (
            "| Latencia mediana | "
            f"{metric(metrics['latency_median_ms'], ' ms')} |"
        ),
        (
            "| Latencia p95 | "
            f"{metric(metrics['latency_p95_ms'], ' ms')} |"
        ),
        (
            "| Preguntas evaluadas | "
            f"{metrics['questions_evaluated']} |"
        ),
        "",
        "## Detalle",
        "",
        (
            "| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | "
            "Failover | Latencia |"
        ),
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        lines.append(
            "| "
            f"{result['id']} | "
            f"{result['tipo']} | "
            f"{'OK' if result['q1_ok'] else 'FAIL'} | "
            f"{'OK' if result['q2_ok'] else 'FAIL'} | "
            f"{'OK' if result['privacy_ok'] else 'FAIL'} | "
            f"{'OK' if result['partial_ok'] else 'FAIL'} | "
            f"{'OK' if result.get('failover_ok', True) else 'FAIL'} | "
            f"{result['latency_ms']} ms |"
        )

    failures = [
        result
        for result in results
        if not (
            result["q1_ok"]
            and result["q2_ok"]
            and result["privacy_ok"]
            and result["partial_ok"]
        )
    ]

    lines.extend(
        [
            "",
            "## Fallos detectados",
            "",
        ]
    )

    if not failures:
        lines.append("No se detectaron fallos en las preguntas evaluadas.")
    else:
        for result in failures:
            lines.extend(
                [
                    f"### {result['id']}",
                    "",
                    f"- Pregunta: {result['pregunta']}",
                    f"- Respuesta: {result['reply']}",
                    f"- Herramientas: `{result['actual_tools']}`",
                    (
                        "- Cifras no respaldadas: "
                        f"`{result['unsupported_numbers']}`"
                    ),
                    f"- Warnings: `{result['warnings']}`",
                    "",
                ]
            )

    md_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return json_path, md_path


def select_questions(
    questions: list[EvalQuestion],
    scenario: str,
) -> list[EvalQuestion]:
    if scenario == "site-down":
        return [
            q for q in questions
            if q.tipo == "sede_caida"
        ]

    if scenario == "coordinator-down":
        wanted = {"Q01", "Q03", "Q04"}
        return [
            q for q in questions
            if q.id in wanted
        ]

    return [
        q for q in questions
        if q.tipo != "sede_caida"
    ]


def configure_model(model: str) -> None:
    """Recrea chatbot-api usando exclusivamente el modelo evaluado."""
    env = os.environ.copy()
    env["EVAL_LLM_MODEL"] = model

    command = [
        "docker",
        "compose",
        "-p",
        "chatbot",
        "-f",
        str(CHATBOT_COMPOSE),
        "-f",
        str(EVAL_COMPOSE),
        "up",
        "-d",
        "--force-recreate",
        "chatbot-api",
    ]

    print(f"Configurando chatbot-api con {model}...")

    try:
        subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "No se encontró Docker. No se puede configurar el modelo."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "No se pudo recrear chatbot-api para la evaluación."
        ) from exc


def wait_for_api(
    api_url: str,
    timeout_s: float = 60.0,
) -> None:
    """Espera hasta que chatbot-api vuelva a estar disponible."""
    deadline = time.monotonic() + timeout_s
    health_url = f"{api_url.rstrip('/')}/health"

    while time.monotonic() < deadline:
        try:
            response = httpx.get(health_url, timeout=2.0)
            if response.is_success:
                return
        except httpx.HTTPError:
            pass

        time.sleep(1)

    raise SystemExit(
        f"chatbot-api no está disponible tras {timeout_s:.0f} s."
    )


def load_existing_results(
    model: str,
    scenario: str,
) -> list[dict[str, Any]]:
    """Carga resultados parciales guardados de una evaluación."""
    slug = model_slug(model)
    path = RESULTS_DIR / f"{slug}__{scenario}.json"

    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("model") != model:
        raise SystemExit(
            f"El resultado existente {path} pertenece a otro modelo."
        )

    if payload.get("scenario") != scenario:
        raise SystemExit(
            f"El resultado existente {path} pertenece a otro escenario."
        )

    return payload.get("results", [])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa un modelo contra la batería de P3-16."
    )

    parser.add_argument(
        "--model",
        required=True,
        help="ID exacto del modelo evaluado en OpenRouter.",
    )

    parser.add_argument(
        "--question",
        help="Ejecuta solo una pregunta de la batería, por ejemplo Q01.",
    )

    parser.add_argument(
        "--scenario",
        choices=("healthy", "site-down", "coordinator-down"),
        default="healthy",
        help=(
            "Escenario de evaluación. 'healthy' evalúa la batería normal; "
            "'site-down' evalúa las preguntas que requieren una sede caída."
        ),
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reanuda una evaluación existente sin repetir preguntas ya guardadas.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=7.0,
        help="Segundos de espera entre preguntas para respetar el rate limit.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_url = os.environ.get("AGENT_API_URL", "http://localhost:8300")
    token = os.environ.get("AGENT_API_TOKEN", "")
    questions = load_questions()

    print(f"Modelo: {args.model}")
    print(f"Preguntas cargadas: {len(questions)}")
    print(f"API: {api_url}")
    print(f"Escenario: {args.scenario}")

    configure_model(args.model)
    wait_for_api(api_url)
    register_all_tools()

    print("chatbot-api preparada para la evaluación.")

    scenario_questions = select_questions(questions, args.scenario)

    if args.question:
        selected = [
            q for q in scenario_questions
            if q.id == args.question
        ]

        if not selected:
            raise SystemExit(
                f"La pregunta {args.question} no pertenece "
                f"al escenario {args.scenario!r}."
            )
    else:
        selected = scenario_questions

    if args.resume and not args.question:
        results = load_existing_results(
            model=args.model,
            scenario=args.scenario,
        )

        completed_ids = {result["id"] for result in results}

        selected = [
            question
            for question in selected
            if question.id not in completed_ids
        ]

        print(
            f"Reanudando evaluación: "
            f"{len(completed_ids)} preguntas ya completadas, "
            f"{len(selected)} pendientes."
        )
    else:
        results: list[dict[str, Any]] = []

    with httpx.Client(timeout=60.0) as client:
        total_target = len(results) + len(selected)

        for index, question in enumerate(
            selected,
            start=len(results) + 1,
        ):
            print(
                f"[{index}/{total_target}] "
                f"{question.id} — {question.tipo}"
            )

            result = evaluate_question(
                client=client,
                api_url=api_url,
                token=token,
                question=question,
                model=args.model,
                scenario=args.scenario,
            )

            results.append(result)

            print(
                f"  Q1={'OK' if result['q1_ok'] else 'FAIL'} "
                f"Q2={'OK' if result['q2_ok'] else 'FAIL'} "
                f"latencia={result['latency_ms']} ms"
            )

            # Guardado incremental para no perder resultados si una
            # ejecución larga se interrumpe.
            partial_metrics = calculate_metrics(results)

            save_results(
                model=args.model,
                scenario=args.scenario,
                results=results,
                metrics=partial_metrics,
                question_id=args.question,
            )

            if index < total_target and args.delay > 0:
                print(
                    f"  Esperando {args.delay:g} s "
                    "para respetar el rate limit..."
                )
                time.sleep(args.delay)

    metrics = calculate_metrics(results)

    json_path, md_path = save_results(
        model=args.model,
        scenario=args.scenario,
        results=results,
        metrics=metrics,
        question_id=args.question,
    )

    print()
    print("Evaluación terminada.")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
