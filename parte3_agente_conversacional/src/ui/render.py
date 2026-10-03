"""Pintado de las respuestas del agente en Streamlit (P3-13).

Pinta TODO lo que devuelve /chat, ademas del texto:

  - blocks:   kpi -> st.metric en columnas, table -> st.dataframe,
              line -> st.line_chart, bar -> st.bar_chart;
  - warnings: st.warning encima de la respuesta;
  - sources:  desplegable «Cómo se ha obtenido esta respuesta» (render_trace).

Y el estado de la plataforma de la barra lateral (GET /status).

Las cifras de los bloques salen de las herramientas, nunca del LLM: aqui
solo se les da formato. Las transformaciones (bloque -> DataFrame, formato
de cifras, rangos de fechas) son funciones puras, testeables sin Streamlit.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from ..api.schemas import Block, ChatResponse, Source

# Unidades de las herramientas -> como se escriben en pantalla.
UNIT_NAMES = {"$": "$", "mi": "millas", "%": "%"}
TRIPS_LABEL = "Viajes"
KPI_COLUMNS = 3  # metricas por fila: legibles a 1280x720
CHART_HEIGHT = 300  # px: grafico + tabla caben en una pantalla de 720
BAR_HEIGHT_PER_CATEGORY = 45
TRACE_TITLE = "Cómo se ha obtenido esta respuesta"

SITE_ICONS = {"responde": "🟢", "no responde": "🔴"}
REPLICA_ICONS = {"activa": "🟢", "caída": "🔴"}
UNKNOWN_ICON = "⚪"


# ============================================================
# Formato (funciones puras)
# ============================================================

def md(text: Any) -> str:
    """Texto para st.markdown: escapa `$`, que Streamlit toma por LaTeX."""
    return str(text).replace("$", r"\$")


def format_value(value: Any, unit: Optional[str] = None, label: Optional[str] = None) -> str:
    """Cifra con dos decimales y su unidad: $1234.56, 2.35 millas, 1500 viajes."""
    if value is None:
        return "—"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, int) and unit is None:
        return f"{value} viajes" if label == TRIPS_LABEL else str(value)
    if unit == "$":
        return f"${value:.2f}"
    if unit in UNIT_NAMES:
        return f"{value:.2f} {UNIT_NAMES[unit]}"
    return f"{value:.2f}"


def column_name(name: str) -> str:
    """Cabecera de tabla con la unidad completa: «Distancia media (mi)» -> «(millas)»."""
    return str(name).replace("(mi)", "(millas)")


def axis_label(name: str, unit: Optional[str]) -> str:
    return f"{name} ({UNIT_NAMES.get(unit, unit)})" if unit else name


def table_frame(block: Block) -> pd.DataFrame:
    data = block.data or {}
    columns = [column_name(c) for c in data.get("columns", [])]
    return pd.DataFrame(data.get("rows", []), columns=columns)


def table_column_config(frame: pd.DataFrame) -> dict:
    """Dos decimales en las columnas con decimales; enteros tal cual."""
    config = {}
    for name in frame.columns:
        if pd.api.types.is_bool_dtype(frame[name]):
            continue
        if pd.api.types.is_integer_dtype(frame[name]):
            config[name] = st.column_config.NumberColumn(name, format="%d")
        elif pd.api.types.is_float_dtype(frame[name]):
            config[name] = st.column_config.NumberColumn(name, format="%.2f")
    return config


def _time_index(x: list) -> pd.Index:
    """Eje X como fechas si se puede (series por hora o por dia)."""
    parsed = pd.to_datetime(pd.Series(x, dtype="object"), errors="coerce")
    if len(x) and not parsed.isna().any():
        return pd.DatetimeIndex(parsed, name="Fecha")
    return pd.Index(x, name="Fecha")


def line_frame(block: Block) -> pd.DataFrame:
    data = block.data or {}
    series = {s["name"]: s.get("points", []) for s in data.get("series", [])}
    return pd.DataFrame(series, index=_time_index(data.get("x", []))).astype("float")


def bar_frame(block: Block) -> pd.DataFrame:
    data = block.data or {}
    series = {s["name"]: s.get("values", []) for s in data.get("series", [])}
    return pd.DataFrame(series, index=pd.Index(data.get("categories", []), name="Categoría"))


def date_ranges(dates: list[str]) -> list[tuple[str, str]]:
    """Agrupa dias consecutivos: [d1, d2, d5] -> [(d1, d2), (d5, d5)]."""
    days = sorted({date.fromisoformat(str(d)[:10]) for d in dates})
    ranges: list[list[date]] = []
    for day in days:
        if ranges and day - ranges[-1][1] == timedelta(days=1):
            ranges[-1][1] = day
        else:
            ranges.append([day, day])
    return [(start.isoformat(), end.isoformat()) for start, end in ranges]


def replica_name(replica: dict) -> str:
    """«central (localhost:8100)» o, si no se sabe la sede, solo el host."""
    host = urlparse(replica.get("url") or "").netloc or replica.get("url") or "?"
    site = replica.get("site_id")
    return f"{site} ({host})" if site else host


def source_line(source: Source) -> str:
    """Una linea de trazabilidad por llamada a herramienta."""
    args = json.dumps(source.args, ensure_ascii=False) if source.args else "sin argumentos"
    parts = [f"**{source.tool}** `{args}`"]
    if source.served_by:
        parts.append(f"respondió {replica_name({'url': source.served_by})}")
    if source.sites_ok:
        parts.append("sedes: " + ", ".join(source.sites_ok))
    if source.sites_failed:
        parts.append("**caídas: " + ", ".join(source.sites_failed) + "**")
    parts.append(f"{source.latency_ms} ms")
    return md(" · ".join(parts))


# ============================================================
# Bloques
# ============================================================

def _render_kpi(block: Block) -> None:
    metrics = list(block.data or [])
    for start in range(0, len(metrics), KPI_COLUMNS):
        for column, metric in zip(st.columns(KPI_COLUMNS), metrics[start:start + KPI_COLUMNS]):
            label = metric.get("label", "")
            column.metric(label, format_value(metric.get("value"), metric.get("unit"), label))


def _render_table(block: Block) -> None:
    frame = table_frame(block)
    st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        column_config=table_column_config(frame),
    )


def _render_line(block: Block) -> None:
    frame = line_frame(block)
    name = frame.columns[0] if len(frame.columns) else ""
    st.line_chart(frame, x_label="Fecha", y_label=axis_label(name, block.unit), height=CHART_HEIGHT)


def _render_bar(block: Block) -> None:
    frame = bar_frame(block)
    name = frame.columns[0] if len(frame.columns) else ""
    # Barras horizontales: los nombres (sedes, métodos de pago) se leen sin girar.
    height = min(CHART_HEIGHT, 80 + BAR_HEIGHT_PER_CATEGORY * len(frame))
    st.bar_chart(frame, x_label=axis_label(name, block.unit), y_label="", horizontal=True, height=height)


_RENDERERS = {
    "kpi": _render_kpi,
    "table": _render_table,
    "line": _render_line,
    "bar": _render_bar,
}


def render_block(block: Block) -> None:
    st.markdown(f"**{md(block.title)}**")
    try:
        _RENDERERS[block.type](block)
    except Exception:  # noqa: BLE001 - un bloque raro no tumba la conversacion
        st.info("No se ha podido dibujar este elemento.")


# ============================================================
# Respuesta completa
# ============================================================

def render_trace(response: ChatResponse) -> None:
    """Desplegable con las herramientas usadas, la réplica y las sedes."""
    with st.expander(TRACE_TITLE):
        for source in response.sources:
            st.markdown("- " + source_line(source))
        st.caption(f"Respuesta en {response.latency_ms} ms · petición {response.request_id}")


def render_answer(response: ChatResponse) -> None:
    """Avisos, texto, bloques y trazabilidad de una respuesta de /chat."""
    for warning in response.warnings:
        st.warning(md(warning), icon="⚠️")
    st.markdown(md(response.reply))
    for block in response.blocks:
        render_block(block)
    if response.sources:
        render_trace(response)


# ============================================================
# Estado de la plataforma (barra lateral)
# ============================================================

def render_status(status: Any) -> None:
    """Sedes, réplicas del coordinador y fechas con datos (resultado de /status)."""
    if not isinstance(status, dict):  # AgentError
        st.warning(md(getattr(status, "message", status)))
        return

    if status.get("coordinator") == "no disponible":
        st.error("Coordinador no disponible: no responde ninguna réplica.")

    lines = []
    for site in status.get("sites", []):
        icon = SITE_ICONS.get(site.get("status"), UNKNOWN_ICON)
        lines.append(f"{icon} **{site.get('site')}** · {site.get('status')}")
    st.markdown("**Sedes**  \n" + "  \n".join(lines))

    replicas = status.get("replicas", [])
    lines = [
        f"{REPLICA_ICONS.get(r.get('status'), UNKNOWN_ICON)} {replica_name(r)}"
        for r in replicas
    ]
    up = status.get("replicas_up", 0)
    st.markdown(
        f"**Coordinador** ({up} de {len(replicas)} réplicas activas)  \n" + "  \n".join(lines)
    )

    ranges = date_ranges(status.get("dates_with_data") or [])
    if ranges:
        text = "  \n".join(start if start == end else f"{start} a {end}" for start, end in ranges)
        st.markdown("**Fechas con datos**  \n" + text)
    else:
        st.markdown("**Fechas con datos**  \nninguna")

    if status.get("note"):
        st.caption(md(status["note"]))
