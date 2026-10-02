"""Combinacion de agregados: Sigma sumas / Sigma conteos.

Las medias se calculan SIEMPRE como suma_total / conteo_total (nunca media
de medias), y el dinero se maneja con Decimal (nunca float), porque los
importes llegan del coordinador como texto. Se redondea solo al presentar.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

MONEY_FIELDS = ("sum_fare_amount", "sum_tip_amount", "sum_total_amount")


def to_decimal(value) -> Decimal:
    """Convierte un importe (texto o numero) a Decimal sin pasar por float."""
    return Decimal(str(value))


def combine(rows: Iterable[dict]) -> dict:
    """Combina varias filas de agregados en una sola.

    Suma conteos y sumas, y calcula las medias como Sigma sumas / Sigma
    conteos. Devuelve importes como Decimal (sin redondear): el redondeo se
    hace solo al presentar, con round_money().
    """
    count = 0
    sums = {field: Decimal("0") for field in MONEY_FIELDS}
    distance = Decimal("0")

    for row in rows:
        count += int(row["trip_count"])
        for field in MONEY_FIELDS:
            sums[field] += to_decimal(row[field])
        distance += to_decimal(row["sum_trip_distance"])

    result = {
        "trip_count": count,
        "sum_trip_distance": float(distance),
        **sums,
    }
    for field in MONEY_FIELDS:
        avg_field = field.replace("sum_", "avg_")
        result[avg_field] = sums[field] / count if count else Decimal("0")
    result["avg_trip_distance"] = float(distance) / count if count else 0.0
    return result


def round_money(value, places: int = 2) -> Decimal:
    """Redondea un importe a `places` decimales (solo para presentar)."""
    quantum = Decimal(10) ** -places
    return to_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
