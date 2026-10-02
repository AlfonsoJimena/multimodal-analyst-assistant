"""Herramienta de estado de la plataforma (P3-07): get_platform_status.

Responde a «¿está todo funcionando?» y, sobre todo, le dice al agente qué
fechas tienen datos antes de contestar a «¿y ayer?» (en la base de datos
conviven el histórico de 2020 y el tiempo real de 2026).

NUNCA lanza ni devuelve ToolError: si no responde ninguna réplica, eso es
precisamente el estado que hay que contar («coordinador no disponible»).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from ..api.schemas import Block
from ..data.coordinator_client import (
    CoordinatorClient,
    CoordinatorParamError,
    CoordinatorUnavailable,
)
from .base import ToolMeta, ToolResult, register_tool
from .common import SITES, StrictArgs

logger = logging.getLogger(__name__)

# Fechas con datos que se listan como máximo (las más recientes).
MAX_DATES = 31


class StatusArgs(StrictArgs):
    pass


def get_platform_status(args: Optional[StatusArgs] = None,
                        client: Optional[CoordinatorClient] = None) -> ToolResult:
    try:
        return _status(client or CoordinatorClient())
    except Exception as error:  # noqa: BLE001 - el estado nunca lanza
        logger.exception("Fallo inesperado comprobando el estado")
        return ToolResult(
            data={"coordinator": "desconocido", "detail": type(error).__name__},
            meta=ToolMeta(note="No se ha podido comprobar el estado de la plataforma."),
        )


def _status(client: CoordinatorClient) -> ToolResult:
    # 1) Réplicas del coordinador, una a una (sin failover).
    replicas = []
    for r in client.health_all():
        replicas.append({
            "url": r["url"],
            "status": "activa" if r["ok"] else "caída",
            "site_id": r.get("site_id"),
            "detail": None if r["ok"] else r.get("error"),
        })
    replicas_down = [r["url"] for r in replicas if r["status"] != "activa"]

    # 2) Sedes y fechas con datos, a través del coordinador (con failover).
    try:
        res = client.daily(breakdown="site")
    except (CoordinatorUnavailable, CoordinatorParamError) as error:
        res, coordinator_error = None, str(error)
    else:
        coordinator_error = None

    notes = []
    if replicas_down and len(replicas_down) < len(replicas):
        notes.append(
            f"{len(replicas_down)} de {len(replicas)} réplicas del coordinador caídas; "
            "el failover sigue sirviendo las consultas."
        )

    if res is None:
        notes.insert(0, "Coordinador no disponible: no responde ninguna réplica, no se pueden consultar datos.")
        data = {
            "coordinator": "no disponible",
            "detail": coordinator_error,
            "replicas": replicas,
            "replicas_up": len(replicas) - len(replicas_down),
            "replicas_total": len(replicas),
            "sites": [{"site": s, "status": "desconocido", "first_date": None, "last_date": None} for s in SITES],
            "first_date": None,
            "last_date": None,
            "dates_with_data": [],
        }
        meta = ToolMeta(sites_failed=[], partial=False, note=" ".join(notes))
        return ToolResult(data=data, meta=meta, block=_table(data))

    dates_by_site: dict[str, set] = defaultdict(set)
    for row in res.data:
        dates_by_site[row.get("site_id")].add(str(row["trip_date"]))
    all_dates = sorted(set().union(*dates_by_site.values())) if dates_by_site else []

    sites = []
    for s in SITES:
        dates = sorted(dates_by_site.get(s, ()))
        if s in res.sites_ok:
            status = "responde"
        elif s in res.sites_failed:
            status = "no responde"
        else:
            status = "desconocido"
        sites.append({
            "site": s,
            "status": status,
            "first_date": dates[0] if dates else None,
            "last_date": dates[-1] if dates else None,
        })

    if res.sites_failed:
        notes.append(
            "No responde(n): " + ", ".join(res.sites_failed)
            + ". Las respuestas serán parciales hasta que vuelvan."
        )
    if not res.sites_ok:
        notes.append("Ninguna sede responde: no hay datos disponibles ahora mismo.")
    if len(all_dates) > MAX_DATES:
        notes.append(f"Hay {len(all_dates)} días con datos; se listan los {MAX_DATES} más recientes.")

    data = {
        "coordinator": "disponible",
        "served_by": res.served_by,
        "replicas": replicas,
        "replicas_up": len(replicas) - len(replicas_down),
        "replicas_total": len(replicas),
        "sites": sites,
        "first_date": all_dates[0] if all_dates else None,
        "last_date": all_dates[-1] if all_dates else None,
        "dates_with_data": all_dates[-MAX_DATES:],
    }
    period = (
        f"{data['first_date']} a {data['last_date']}" if all_dates else None
    )
    meta = ToolMeta(
        sites_ok=[s for s in SITES if s in res.sites_ok],
        sites_failed=[s for s in SITES if s in res.sites_failed],
        partial=bool(res.sites_failed),
        served_by=res.served_by,
        period=period,
        note=" ".join(notes) or None,
        latency_ms=res.latency_ms,
    )
    return ToolResult(data=data, meta=meta, block=_table(data))


def _table(data: dict) -> Block:
    rows = []
    for r in data["replicas"]:
        rows.append([f"Coordinador {r['url']}", r["status"], r["site_id"] or r["detail"] or ""])
    for s in data["sites"]:
        if s["first_date"]:
            detail = f"datos del {s['first_date']} al {s['last_date']}"
        else:
            detail = "sin datos"
        rows.append([f"Sede {s['site']}", s["status"], detail])
    return Block(
        type="table",
        title="Estado de la plataforma",
        data={"columns": ["Componente", "Estado", "Detalle"], "rows": rows},
    )


GET_PLATFORM_STATUS_DESCRIPTION = (
    "Estado de la plataforma distribuida: qué réplicas del coordinador están activas, "
    "qué sedes responden y qué fechas tienen datos (primera, última y lista de días). "
    "Úsala ante «¿funciona todo?», cuando otra herramienta devuelva un resultado "
    "parcial o un error, y ANTES de responder a fechas relativas como «ayer» u «hoy» "
    "para saber qué días existen en los datos. No necesita argumentos."
)


def register() -> None:
    register_tool("get_platform_status", GET_PLATFORM_STATUS_DESCRIPTION, StatusArgs, get_platform_status)
