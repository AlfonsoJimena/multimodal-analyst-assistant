"""Herramientas de métricas (P3-06): get_kpis, compare_sites, get_timeseries.

Todas siguen el mismo patrón:
  1. argumentos ya validados por Pydantic (ver `common.invoke_tool`);
  2. una consulta al coordinador a través de la capa de datos (P3-04);
  3. recorte a las sedes pedidas y combinación con `aggregation.combine`
     (Σ sumas / Σ conteos, nunca media de medias);
  4. supresión de celdas pequeñas a la granularidad que se devuelve;
  5. `ToolResult` con datos, metadatos de trazabilidad y bloque visual.

Cada función acepta `client` para poder inyectar un cliente con un
transporte simulado en los tests.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Optional

from pydantic import Field

from ..agent.config import get_config
from ..api.schemas import Block
from ..data.aggregation import combine
from ..data.coordinator_client import CoordinatorClient
from ..data.privacy import suppress_small_cells
from .base import ToolError, ToolOutput, ToolResult, register_tool
from .common import (
    METRICS,
    SITES,
    SITES_DESCRIPTION,
    MetricName,
    PeriodArgs,
    SiteName,
    build_meta,
    call_coordinator,
    metric_label,
    metric_values,
    period_label,
    privacy_note,
    requested_sites,
    scope,
    sites_label,
)

MAX_POINTS = 200
NO_DATA_NOTE = "No hay viajes en el periodo pedido."

# Columnas de la tabla comparativa (mismo orden que METRICS).
TABLE_COLUMNS = ["Sede"] + [metric_label(m) for m in METRICS]


# ============================================================
# get_kpis
# ============================================================

class KpisArgs(PeriodArgs):
    sites: list[SiteName] = Field(default_factory=list, description=SITES_DESCRIPTION)


def get_kpis(args: KpisArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    wanted = requested_sites(args.sites)
    by_site = len(wanted) < len(SITES)

    result = call_coordinator(
        client.daily, args.date_from, args.date_to, breakdown="site" if by_site else "none"
    )
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, wanted, by_site)
    if isinstance(scoped, ToolError):
        return scoped

    period = period_label(args.date_from, args.date_to, [r["trip_date"] for r in scoped.rows])
    if not scoped.rows:
        return ToolResult(data=None, meta=build_meta(scoped, period, NO_DATA_NOTE))

    combined = combine(scoped.rows)
    min_trips = get_config().min_trips_per_cell
    if combined["trip_count"] < min_trips:
        return ToolResult(data=None, meta=build_meta(scoped, period, privacy_note(1, min_trips)))

    values = metric_values(combined)
    block = Block(
        type="kpi",
        title=f"Indicadores · {sites_label(scoped.sites_ok)} · {period}",
        data=[
            {"label": METRICS[m][0], "value": v, "unit": METRICS[m][1]}
            for m, v in values.items()
        ],
    )
    data = {"sites": scoped.sites_ok, **values}
    return ToolResult(data=data, meta=build_meta(scoped, period), block=block)


# ============================================================
# compare_sites
# ============================================================

class CompareSitesArgs(PeriodArgs):
    pass


def compare_sites(args: CompareSitesArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    wanted = list(SITES)

    result = call_coordinator(client.daily, args.date_from, args.date_to, breakdown="site")
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, wanted, by_site=True)
    if isinstance(scoped, ToolError):
        return scoped

    period = period_label(args.date_from, args.date_to, [r["trip_date"] for r in scoped.rows])
    if not scoped.rows:
        return ToolResult(data=None, meta=build_meta(scoped, period, NO_DATA_NOTE))

    rows_by_site: dict[str, list[dict]] = defaultdict(list)
    for row in scoped.rows:
        rows_by_site[row["site_id"]].append(row)

    # Una fila combinada por sede que ha respondido y tiene viajes.
    per_site = []
    for site in scoped.sites_ok:
        if rows_by_site[site]:
            per_site.append({"site": site, **combine(rows_by_site[site])})
    empty = [s for s in scoped.sites_ok if not rows_by_site[s]]

    min_trips = get_config().min_trips_per_cell
    kept, hidden = suppress_small_cells(per_site, min_trips)

    notes = [privacy_note(hidden, min_trips)]
    if empty:
        notes.append("Sin viajes en el periodo: " + ", ".join(empty) + ".")
    meta = build_meta(scoped, period, *notes)
    if not kept:
        return ToolResult(data=None, meta=meta)

    data = [{"site": row["site"], **metric_values(row)} for row in kept]
    sites = [row["site"] for row in data]

    bar = Block(
        type="bar",
        title=f"Viajes por sede · {period}",
        data={"categories": sites, "series": [{"name": "Viajes", "values": [r["trips"] for r in data]}]},
    )
    table = Block(
        type="table",
        title=f"Comparativa entre sedes · {period}",
        data={
            "columns": TABLE_COLUMNS,
            "rows": [[r["site"]] + [r[m] for m in METRICS] for r in data],
        },
    )
    return ToolResult(data=data, meta=meta, block=bar, extra_blocks=[table])


# ============================================================
# get_timeseries
# ============================================================

class TimeseriesArgs(PeriodArgs):
    metric: MetricName = Field(
        ...,
        description=(
            "Métrica de la serie: trips (viajes), revenue (ingresos, $), "
            "avg_fare (tarifa media, $), avg_distance (distancia media, millas), "
            "avg_tip (propina media, $) o avg_total (importe medio por viaje, $)."
        ),
    )
    granularity: Literal["hour", "day"] = Field(
        ..., description="hour = un punto por hora; day = un punto por día."
    )
    sites: list[SiteName] = Field(default_factory=list, description=SITES_DESCRIPTION)


def get_timeseries(args: TimeseriesArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    wanted = requested_sites(args.sites)
    by_site = len(wanted) < len(SITES)
    breakdown = "site" if by_site else "none"

    if args.granularity == "hour":
        key = "trip_hour"
        # El coordinador compara datetimes: date_to sin hora sería medianoche
        # y solo entraría la primera hora del último día.
        result = call_coordinator(
            client.hourly,
            f"{args.date_from.isoformat()}T00:00:00" if args.date_from else None,
            f"{args.date_to.isoformat()}T23:59:59" if args.date_to else None,
            breakdown=breakdown,
        )
    else:
        key = "trip_date"
        result = call_coordinator(client.daily, args.date_from, args.date_to, breakdown=breakdown)
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, wanted, by_site)
    if isinstance(scoped, ToolError):
        return scoped

    period = period_label(args.date_from, args.date_to, [str(r[key]) for r in scoped.rows])
    if not scoped.rows:
        return ToolResult(data=None, meta=build_meta(scoped, period, NO_DATA_NOTE))

    # Un punto por instante, sumando las sedes pedidas.
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in scoped.rows:
        groups[str(row[key])].append(row)

    min_trips = get_config().min_trips_per_cell
    points, hidden = [], 0
    for t in sorted(groups):
        combined = combine(groups[t])
        if combined["trip_count"] < min_trips:
            hidden += 1
            points.append({"t": t, "value": None})
        else:
            points.append({"t": t, "value": metric_values(combined)[args.metric]})

    visible = [p for p in points if p["value"] is not None]
    # Máximo de toda la serie (en empate, el primero): la hora punta con trips.
    peak = max(visible, key=lambda p: p["value"]) if visible else None

    notes = [privacy_note(hidden, min_trips)]
    if len(points) > MAX_POINTS:
        notes.append(
            f"La serie tiene {len(points)} puntos; se muestran los {MAX_POINTS} más recientes. "
            "Acota las fechas o usa granularity=day para verla entera."
        )
        points = points[-MAX_POINTS:]
    meta = build_meta(scoped, period, *notes)

    label, unit = METRICS[args.metric]
    data = {
        "metric": args.metric,
        "granularity": args.granularity,
        "sites": scoped.sites_ok,
        "points": points,
        "peak": peak,
    }
    block = Block(
        type="line",
        title=f"{label} por {'hora' if args.granularity == 'hour' else 'día'} · "
              f"{sites_label(scoped.sites_ok)} · {period}",
        data={"x": [p["t"] for p in points], "series": [{"name": label, "points": [p["value"] for p in points]}]},
        unit=unit,
    )
    return ToolResult(data=data, meta=meta, block=block)


# ============================================================
# Registro
# ============================================================

GET_KPIS_DESCRIPTION = (
    "Indicadores agregados de los viajes en taxi de Nueva York de un periodo: "
    "número de viajes, ingresos totales ($) y medias por viaje (tarifa $, "
    "distancia en millas, propina $ e importe total $). Úsala para preguntas "
    "como «¿cuántos viajes hubo…?» o «¿cuál fue la tarifa media…?». Puede "
    "filtrar por sedes y por fechas; sin fechas usa todo el periodo disponible."
)

COMPARE_SITES_DESCRIPTION = (
    "Compara las tres sedes (central, chamartin, atocha) en un periodo: una fila "
    "por sede con viajes, ingresos y medias. Úsala cuando se pregunte qué sede "
    "tiene más viajes o ingresos, o se pida comparar sedes. Si alguna sede no "
    "responde, el resultado es parcial y meta.sites_failed dice cuál falta."
)

GET_TIMESERIES_DESCRIPTION = (
    "Evolución temporal de una métrica, por hora o por día, con su máximo "
    "(peak). Úsala para «evolución», «tendencia», «hora punta» o «qué día hubo "
    "más…». Para un solo día usa granularity=hour con date_from = date_to. "
    "Devuelve como máximo 200 puntos."
)


def register() -> None:
    """Registra las tres herramientas (idempotente)."""
    register_tool("get_kpis", GET_KPIS_DESCRIPTION, KpisArgs, get_kpis)
    register_tool("compare_sites", COMPARE_SITES_DESCRIPTION, CompareSitesArgs, compare_sites)
    register_tool("get_timeseries", GET_TIMESERIES_DESCRIPTION, TimeseriesArgs, get_timeseries)
