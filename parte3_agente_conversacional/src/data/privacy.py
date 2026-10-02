"""Supresion de celdas pequenas (privacidad).

Oculta las filas cuyo numero de viajes es menor que un umbral
(MIN_TRIPS_PER_CELL), para no exponer datos de grupos muy pequenos.
"""

from __future__ import annotations


def suppress_small_cells(rows: list[dict], min_trips: int) -> tuple[list[dict], int]:
    """Devuelve (filas_con_al_menos_min_trips, cuantas_se_han_ocultado)."""
    kept = [row for row in rows if int(row["trip_count"]) >= min_trips]
    hidden = len(rows) - len(kept)
    return kept, hidden
