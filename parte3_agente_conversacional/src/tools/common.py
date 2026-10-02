"""Piezas compartidas por las herramientas (P3-06 y P3-07).

- Tipos cerrados para los argumentos: sedes y métricas.
- `PeriodArgs`: fechas AAAA-MM-DD validadas, con date_from <= date_to.
- `scope()`: recorta la respuesta del coordinador a las sedes PEDIDAS.
  `partial` se calcula respecto a esas sedes: si se pregunta por central y
  cae atocha, el resultado no es parcial.
- `metric_values()`: pasa una fila combinada (Decimal) a las métricas
  del glosario, ya redondeadas para presentar.
- `invoke_tool()`: punto de entrada único para el orquestador (P3-09).
  Valida los argumentos y nunca lanza: cualquier problema vuelve como
  `ToolError`, que se le devuelve al LLM como dato.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ..data.aggregation import round_money
from ..data.coordinator_client import (
    CoordinatorClient,
    CoordinatorParamError,
    CoordinatorResult,
    CoordinatorUnavailable,
)
from .base import ToolError, ToolMeta, ToolOutput, get_tool

logger = logging.getLogger(__name__)

# ============================================================
# Sedes y métricas
# ============================================================

SITES: tuple[str, ...] = ("central", "chamartin", "atocha")
SiteName = Literal["central", "chamartin", "atocha"]

# nombre -> (etiqueta para la interfaz, unidad)
METRICS: dict[str, tuple[str, Optional[str]]] = {
    "trips": ("Viajes", None),
    "revenue": ("Ingresos", "$"),
    "avg_fare": ("Tarifa media", "$"),
    "avg_distance": ("Distancia media", "mi"),
    "avg_tip": ("Propina media", "$"),
    "avg_total": ("Importe medio", "$"),
}
MetricName = Literal["trips", "revenue", "avg_fare", "avg_distance", "avg_tip", "avg_total"]


def _money(value) -> float:
    """Importe redondeado a céntimos (Decimal -> float solo al presentar)."""
    return float(round_money(value))


def metric_values(combined: dict) -> dict[str, Union[int, float]]:
    """Métricas del glosario a partir de una fila de `aggregation.combine`."""
    return {
        "trips": int(combined["trip_count"]),
        "revenue": _money(combined["sum_total_amount"]),
        "avg_fare": _money(combined["avg_fare_amount"]),
        "avg_distance": _money(combined["avg_trip_distance"]),
        "avg_tip": _money(combined["avg_tip_amount"]),
        "avg_total": _money(combined["avg_total_amount"]),
    }


def metric_label(metric: str) -> str:
    label, unit = METRICS[metric]
    return f"{label} ({unit})" if unit else label


# ============================================================
# Argumentos comunes
# ============================================================

class StrictArgs(BaseModel):
    """Base de todos los argumentos: rechaza campos que no existen."""

    model_config = ConfigDict(extra="forbid")


class PeriodArgs(StrictArgs):
    date_from: Optional[date] = Field(
        None,
        description=(
            "Primer día incluido, formato AAAA-MM-DD. "
            "Si se omite, desde el primer dato disponible."
        ),
    )
    date_to: Optional[date] = Field(
        None,
        description=(
            "Último día incluido (completo), formato AAAA-MM-DD. "
            "Si se omite, hasta el último dato disponible."
        ),
    )

    @model_validator(mode="after")
    def _check_order(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from no puede ser posterior a date_to")
        return self


SITES_DESCRIPTION = (
    "Sedes a incluir: central, chamartin y/o atocha. "
    "Lista vacía u omitida = las tres sedes."
)


def requested_sites(sites: Optional[list[str]]) -> list[str]:
    """Sedes pedidas, sin duplicados y en el orden canónico. Vacío = todas."""
    wanted = set(sites or [])
    return [s for s in SITES if s in wanted] or list(SITES)


# ============================================================
# Llamada al coordinador y recorte por sedes
# ============================================================

def call_coordinator(fn: Callable[..., CoordinatorResult], *args, **kwargs):
    """Llama a la capa de datos y traduce sus excepciones a ToolError."""
    try:
        return fn(*args, **kwargs)
    except CoordinatorUnavailable as error:
        return ToolError(error="coordinador_no_disponible", detail=str(error))
    except CoordinatorParamError as error:
        return ToolError(error="parametros_rechazados", detail=str(error))


@dataclass
class Scoped:
    """Respuesta del coordinador restringida a las sedes pedidas."""

    rows: list[dict]
    sites: list[str]
    sites_ok: list[str]
    sites_failed: list[str]
    served_by: str
    latency_ms: int

    @property
    def partial(self) -> bool:
        return bool(self.sites_failed)


def scope(result: CoordinatorResult, wanted: list[str], by_site: bool) -> Union[Scoped, ToolError]:
    """Se queda con las filas y el estado de las sedes pedidas.

    `by_site` indica que la consulta se hizo con breakdown=site, así que
    cada fila trae su site_id y se pueden descartar las de otras sedes.
    Si no ha respondido ninguna de las sedes pedidas, devuelve ToolError.
    """
    # En el orden canónico de `wanted` (el coordinador las ordena a su manera).
    ok = [s for s in wanted if s in result.sites_ok]
    failed = [s for s in wanted if s in result.sites_failed]
    if not ok:
        return ToolError(
            error="sedes_no_disponibles",
            detail="No ha respondido ninguna de las sedes pedidas: " + ", ".join(failed or wanted),
        )
    rows = result.data
    if by_site:
        rows = [row for row in rows if row.get("site_id") in ok]
    return Scoped(
        rows=rows,
        sites=wanted,
        sites_ok=ok,
        sites_failed=failed,
        served_by=result.served_by,
        latency_ms=result.latency_ms,
    )


# ============================================================
# Metadatos
# ============================================================

def period_label(date_from: Optional[date], date_to: Optional[date], keys: list[str]) -> str:
    """Periodo efectivo: el pedido o, si falta un extremo, el de los datos."""
    start = date_from.isoformat() if date_from else (min(keys)[:10] if keys else None)
    end = date_to.isoformat() if date_to else (max(keys)[:10] if keys else None)
    if start and end:
        return start if start == end else f"{start} a {end}"
    if start:
        return f"desde {start}"
    if end:
        return f"hasta {end}"
    return "todo el periodo disponible"


def privacy_note(hidden: int, min_trips: int) -> Optional[str]:
    if not hidden:
        return None
    return (
        f"{hidden} valor(es) con menos de {min_trips} viajes ocultos por privacidad."
    )


def build_meta(scoped: Scoped, period: str, *notes: Optional[str]) -> ToolMeta:
    """Metadatos de trazabilidad; añade el aviso de resultado parcial."""
    all_notes = []
    if scoped.partial:
        all_notes.append(
            "Resultado parcial: no han respondido "
            + ", ".join(scoped.sites_failed)
            + "; las cifras no incluyen esas sedes."
        )
    all_notes.extend(n for n in notes if n)
    return ToolMeta(
        sites_ok=scoped.sites_ok,
        sites_failed=scoped.sites_failed,
        partial=scoped.partial,
        served_by=scoped.served_by,
        period=period,
        note=" ".join(all_notes) or None,
        latency_ms=scoped.latency_ms,
    )


def sites_label(sites: list[str]) -> str:
    return "todas las sedes" if len(sites) == len(SITES) else ", ".join(sites)


# ============================================================
# Punto de entrada para el orquestador
# ============================================================

def _validation_detail(error: ValidationError) -> str:
    parts = []
    for err in error.errors():
        loc = ".".join(str(p) for p in err.get("loc", ())) or "argumentos"
        parts.append(f"{loc}: {err.get('msg', 'valor no válido')}")
    return "; ".join(parts)[:500]


def invoke_tool(
    name: str,
    raw_args: Union[str, dict[str, Any], None],
    client: Optional[CoordinatorClient] = None,
) -> ToolOutput:
    """Valida los argumentos (dict o JSON del LLM) y ejecuta la herramienta.

    Nunca lanza: herramienta desconocida, argumentos inválidos o un fallo
    inesperado vuelven como ToolError para que el LLM pueda corregirse.
    """
    tool = get_tool(name)
    if tool is None:
        return ToolError(error="herramienta_desconocida", detail=f"No existe la herramienta {name!r}.")

    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args) if raw_args.strip() else {}
        except json.JSONDecodeError as error:
            return ToolError(error="parametros_invalidos", detail=f"JSON no válido: {error}")

    try:
        args = tool.args_model.model_validate(raw_args or {})
    except ValidationError as error:
        return ToolError(error="parametros_invalidos", detail=_validation_detail(error))

    try:
        return tool.fn(args, client=client)
    except Exception as error:  # noqa: BLE001 - una herramienta nunca tumba el chat
        logger.exception("Fallo inesperado en la herramienta %s", name)
        return ToolError(error="error_interno", detail=type(error).__name__)
