"""Herramientas de pagos y zonas (P3-07): get_payment_breakdown, get_zones, get_zone.

Los endpoints /metrics/payment y /metrics/zone del coordinador no admiten
fechas: los datos son acumulados de todo el periodo y `meta.note` lo dice.

Privacidad: se ocultan las celdas (método de pago o zona) con menos de
MIN_TRIPS_PER_CELL viajes. Los porcentajes de pago se calculan sobre el
total, incluidas las celdas ocultas, así que los visibles pueden no sumar 100.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from pydantic import Field, model_validator

from ..agent.config import get_config
from ..api.schemas import Block
from ..data.aggregation import combine
from ..data.coordinator_client import CoordinatorClient
from ..data.privacy import suppress_small_cells
from ..knowledge import find_zone, payment_name, zone_name
from ..knowledge.zones import _normalize
from .base import ToolError, ToolOutput, ToolResult, register_tool
from .common import (
    ACCUMULATED_NOTE,
    ACCUMULATED_PERIOD,
    METRICS,
    SITES,
    SITES_DESCRIPTION,
    MetricName,
    SiteName,
    StrictArgs,
    build_meta,
    call_coordinator,
    metric_label,
    metric_values,
    privacy_note,
    requested_sites,
    scope,
    site_of_zone,
    sites_label,
)
from .metrics import NO_DATA_NOTE

NOT_ENOUGH_DATA_NOTE = "No hay datos suficientes para mostrar esta zona (privacidad)."


def _pct(part, total) -> float:
    """Porcentaje con un decimal, calculado con Decimal."""
    if not total:
        return 0.0
    value = Decimal(str(part)) * 100 / Decimal(str(total))
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


# ============================================================
# get_payment_breakdown
# ============================================================

class PaymentArgs(StrictArgs):
    sites: list[SiteName] = Field(default_factory=list, description=SITES_DESCRIPTION)


def get_payment_breakdown(args: PaymentArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    wanted = requested_sites(args.sites)
    by_site = len(wanted) < len(SITES)

    result = call_coordinator(client.payment, breakdown="site" if by_site else "none")
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, wanted, by_site)
    if isinstance(scoped, ToolError):
        return scoped
    if not scoped.rows:
        return ToolResult(data=None, meta=build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE, NO_DATA_NOTE))

    groups: dict = defaultdict(list)
    for row in scoped.rows:
        code = row.get("payment_type")
        groups[int(code) if code is not None else None].append(row)
    cells = [{"payment_type": code, **combine(rows)} for code, rows in groups.items()]

    # Totales con TODAS las celdas (también las que se ocultan).
    total_trips = sum(c["trip_count"] for c in cells)
    total_revenue = sum(c["sum_total_amount"] for c in cells)

    min_trips = get_config().min_trips_per_cell
    kept, hidden = suppress_small_cells(cells, min_trips)
    meta = build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE, privacy_note(hidden, min_trips))
    if not kept:
        return ToolResult(data=None, meta=meta)

    data = []
    for cell in sorted(kept, key=lambda c: (-c["trip_count"], c["payment_type"] is None, c["payment_type"] or 0)):
        code = cell["payment_type"]
        values = metric_values(cell)
        data.append({
            "payment_type": code,
            "name": payment_name(code) if code is not None else "sin informar",
            "trips": values["trips"],
            "pct_trips": _pct(cell["trip_count"], total_trips),
            "revenue": values["revenue"],
            "pct_revenue": _pct(cell["sum_total_amount"], total_revenue),
            "avg_total": values["avg_total"],
        })

    title = f"Métodos de pago · {sites_label(scoped.sites_ok)}"
    bar = Block(
        type="bar",
        title=f"% de viajes por método de pago · {sites_label(scoped.sites_ok)}",
        data={"categories": [d["name"] for d in data],
              "series": [{"name": "% de viajes", "values": [d["pct_trips"] for d in data]}]},
        unit="%",
    )
    table = Block(
        type="table",
        title=title,
        data={
            "columns": ["Método de pago", "Código", "Viajes", "% viajes", "Ingresos ($)",
                        "% ingresos", "Importe medio ($)"],
            "rows": [[d["name"], d["payment_type"], d["trips"], d["pct_trips"], d["revenue"],
                      d["pct_revenue"], d["avg_total"]] for d in data],
        },
    )
    return ToolResult(data=data, meta=meta, block=bar, extra_blocks=[table])


# ============================================================
# get_zones (ranking)
# ============================================================

class ZonesArgs(StrictArgs):
    metric: MetricName = Field(
        ...,
        description=(
            "Métrica por la que se ordena el ranking: trips (viajes), revenue (ingresos, $), "
            "avg_fare (tarifa media, $), avg_distance (distancia media, millas), "
            "avg_tip (propina media, $) o avg_total (importe medio por viaje, $)."
        ),
    )
    n: int = Field(10, ge=1, le=20, description="Número de zonas del ranking, de 1 a 20.")
    sites: list[SiteName] = Field(default_factory=list, description=SITES_DESCRIPTION)


def get_zones(args: ZonesArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    wanted = requested_sites(args.sites)

    # Siempre por sede: así cada zona trae la sede de la que salen sus viajes.
    result = call_coordinator(client.zone, breakdown="site")
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, wanted, by_site=True)
    if isinstance(scoped, ToolError):
        return scoped
    if not scoped.rows:
        return ToolResult(data=None, meta=build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE, NO_DATA_NOTE))

    groups: dict[int, list[dict]] = defaultdict(list)
    for row in scoped.rows:
        groups[int(row["pu_location_id"])].append(row)
    cells = []
    for zone_id, rows in groups.items():
        sites = [s for s in SITES if any(r.get("site_id") == s for r in rows)]
        cells.append({"zone_id": zone_id, "sites": sites, **combine(rows)})

    min_trips = get_config().min_trips_per_cell
    kept, hidden = suppress_small_cells(cells, min_trips)
    meta = build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE, privacy_note(hidden, min_trips))
    if not kept:
        return ToolResult(data=None, meta=meta)

    ranked = []
    for cell in kept:
        values = metric_values(cell)
        info = zone_name(cell["zone_id"])
        ranked.append({
            "zone_id": cell["zone_id"],
            "zone": info["zone"],
            "borough": info["borough"],
            "site": ", ".join(cell["sites"]),
            **values,
        })
    ranked.sort(key=lambda z: (-z[args.metric], z["zone_id"]))
    top = [{"rank": i + 1, **z} for i, z in enumerate(ranked[: args.n])]

    label, unit = METRICS[args.metric]
    columns = ["#", "Zona", "Distrito", "Sede", metric_label(args.metric)]
    if args.metric != "trips":
        columns.append("Viajes")
    rows = []
    for z in top:
        row = [z["rank"], z["zone"], z["borough"], z["site"], z[args.metric]]
        if args.metric != "trips":
            row.append(z["trips"])
        rows.append(row)

    block = Block(
        type="table",
        title=f"Top {len(top)} zonas de recogida por {label.lower()} · {sites_label(scoped.sites_ok)}",
        data={"columns": columns, "rows": rows},
        unit=unit,
    )
    data = {"metric": args.metric, "zones_with_data": len(kept), "ranking": top}
    return ToolResult(data=data, meta=meta, block=block)


# ============================================================
# get_zone
# ============================================================

class ZoneArgs(StrictArgs):
    zone_id: Optional[int] = Field(
        None, ge=1, le=265, description="ID de la zona de la TLC (1-265), p. ej. 132 para JFK Airport."
    )
    zone_name: Optional[str] = Field(
        None, min_length=2, max_length=80,
        description="Nombre (o parte) de la zona en inglés, p. ej. «JFK Airport» o «Times Sq».",
    )

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.zone_id is None) == (self.zone_name is None):
            raise ValueError("indica zone_id o zone_name (solo uno de los dos)")
        return self


def _resolve_zone(args: ZoneArgs):
    """Devuelve {id, zone, borough} o un ToolError si no existe o es ambigua."""
    if args.zone_id is not None:
        return zone_name(args.zone_id)

    candidates = find_zone(args.zone_name, limit=10)
    if not candidates:
        return ToolError(
            error="zona_no_encontrada",
            detail=f"Ninguna zona de la TLC coincide con {args.zone_name!r}.",
        )
    wanted = _normalize(args.zone_name)
    exact = [c for c in candidates if _normalize(c["zone"]) == wanted]
    chosen = exact or candidates
    if len(chosen) > 1:
        options = "; ".join(f"{c['id']} {c['zone']} ({c['borough']})" for c in chosen)
        return ToolError(
            error="zona_ambigua",
            detail=f"Varias zonas coinciden: {options}. Pregunta cuál o usa zone_id.",
        )
    return chosen[0]


def get_zone(args: ZoneArgs, client: Optional[CoordinatorClient] = None) -> ToolOutput:
    client = client or CoordinatorClient()
    zone = _resolve_zone(args)
    if isinstance(zone, ToolError):
        return zone

    # Cada zona vive en UNA sede (PULocationID % 3): solo importa que responda esa.
    site = site_of_zone(zone["id"])
    result = call_coordinator(client.zone, pu_location_id=zone["id"], breakdown="site")
    if isinstance(result, ToolError):
        return result
    scoped = scope(result, [site], by_site=True)
    if isinstance(scoped, ToolError):
        return ToolError(
            error="sedes_no_disponibles",
            detail=f"Los viajes de {zone['zone']} se guardan en la sede {site}, que no ha respondido.",
        )

    identity = {"zone_id": zone["id"], "zone": zone["zone"], "borough": zone["borough"], "site": site}
    min_trips = get_config().min_trips_per_cell
    combined = combine(scoped.rows) if scoped.rows else None
    # Sin viajes o por debajo del umbral: el mismo mensaje, para no revelar
    # si la zona tiene 0 viajes o solo unos pocos.
    if combined is None or combined["trip_count"] < min_trips:
        return ToolResult(
            data=identity,
            meta=build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE, NOT_ENOUGH_DATA_NOTE),
        )

    values = metric_values(combined)
    block = Block(
        type="kpi",
        title=f"{zone['zone']} ({zone['borough']}) · sede {site}",
        data=[{"label": METRICS[m][0], "value": v, "unit": METRICS[m][1]} for m, v in values.items()],
    )
    return ToolResult(
        data={**identity, **values},
        meta=build_meta(scoped, ACCUMULATED_PERIOD, ACCUMULATED_NOTE),
        block=block,
    )


# ============================================================
# Registro
# ============================================================

GET_PAYMENT_BREAKDOWN_DESCRIPTION = (
    "Reparto de los viajes por método de pago (tarjeta, efectivo, sin cargo, disputa…): "
    "viajes, ingresos ($) y porcentaje de cada método sobre el total. Datos acumulados "
    "de todo el periodo (no admite fechas). Puede filtrar por sedes."
)

GET_ZONES_DESCRIPTION = (
    "Ranking de las zonas de recogida de Nueva York (con nombre y distrito) según una "
    "métrica: las que más viajes, más ingresos o mayor tarifa media tienen, etc. "
    "Datos acumulados de todo el periodo (no admite fechas). n = tamaño del ranking (1-20)."
)

GET_ZONE_DESCRIPTION = (
    "Métricas agregadas de UNA zona de recogida: viajes, ingresos y medias por viaje. "
    "Se puede pedir por zone_id o por zone_name (p. ej. «JFK Airport»). Si el nombre "
    "coincide con varias zonas, devuelve las opciones para preguntar al usuario. "
    "Úsala también cuando pidan un viaje concreto: no hay datos de viajes individuales, "
    "solo agregados por zona. Datos acumulados de todo el periodo."
)


def register() -> None:
    """Registra las tres herramientas (idempotente)."""
    register_tool("get_payment_breakdown", GET_PAYMENT_BREAKDOWN_DESCRIPTION, PaymentArgs, get_payment_breakdown)
    register_tool("get_zones", GET_ZONES_DESCRIPTION, ZonesArgs, get_zones)
    register_tool("get_zone", GET_ZONE_DESCRIPTION, ZoneArgs, get_zone)
