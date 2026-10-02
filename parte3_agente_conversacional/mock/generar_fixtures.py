"""Genera las fixtures del coordinador mock de forma determinista.

Crea `mock/fixtures/<sede>.json` con las tablas hourly/daily/zone/payment
de cada sede, agregadas a partir de una lista de viajes sinteticos. Como
las cuatro tablas salen de los MISMOS viajes, los totales por sede
coinciden entre tablas (daily = hourly = zone = payment). Semilla fija, asi
que regenerar produce ficheros identicos.

    python -m mock.generar_fixtures
"""

import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

SEED = 20260101
FIXTURES_DIR = Path(__file__).parent / "fixtures"

SITES = ["central", "chamartin", "atocha"]

# Volumenes MUY distintos para que una "media de medias" se note.
SITE_TRIPS = {"central": 150, "chamartin": 450, "atocha": 900}

# 7 dias con sus horas: el historico 2020-01-01 y 6 dias "recientes" fijos
# (en la BD real el tiempo real se desplaza a la fecha de arranque; aqui se
# fijan para que las fixtures sean reproducibles).
HISTORICAL_DAY = date(2020, 1, 1)
RECENT_BASE = date(2026, 9, 25)
DAYS = [HISTORICAL_DAY] + [RECENT_BASE + timedelta(days=i) for i in range(6)]

# ~32 zonas (IDs reales de la TLC). Las 3 primeras son raras (<5 viajes),
# para poder probar la supresion de celdas pequenas.
ZONES = [
    4, 12, 13, 24, 41, 42, 43, 45, 48, 50, 68, 74, 79, 87, 88, 90,
    100, 107, 113, 125, 132, 137, 138, 142, 161, 162, 163, 170, 186, 230, 236, 237,
]
RARE_ZONES = 3

# Tipos de pago: 1 tarjeta, 2 efectivo, 3 sin cargo, 4 disputa.
PAYMENT_TYPES = [1, 2, 3, 4]
PAYMENT_WEIGHTS = [70, 25, 3, 2]


def _zone_weights() -> list[int]:
    return [1] * RARE_ZONES + [20] * (len(ZONES) - RARE_ZONES)


def generar_viajes(rng: random.Random, n_trips: int) -> list[dict]:
    viajes = []
    zone_weights = _zone_weights()
    for _ in range(n_trips):
        day = rng.choice(DAYS)
        hour = rng.randint(0, 23)
        ts = datetime(day.year, day.month, day.day, hour, 0, 0)
        zone = rng.choices(ZONES, weights=zone_weights)[0]
        ptype = rng.choices(PAYMENT_TYPES, weights=PAYMENT_WEIGHTS)[0]
        fare = Decimal(rng.randint(500, 5000)) / 100       # 5.00 - 50.00
        tip = Decimal(rng.randint(0, 1500)) / 100          # 0.00 - 15.00
        distance = Decimal(rng.randint(50, 2000)) / 100    # 0.50 - 20.00
        total = fare + tip + Decimal("2.50")               # recargos fijos
        viajes.append(
            {
                "ts": ts,
                "zone": zone,
                "ptype": ptype,
                "fare": fare,
                "tip": tip,
                "distance": distance,
                "total": total,
            }
        )
    return viajes


def _zero() -> dict:
    return {
        "trip_count": 0,
        "sum_fare": Decimal("0"),
        "sum_dist": Decimal("0"),
        "sum_tip": Decimal("0"),
        "sum_total": Decimal("0"),
    }


def _add(agg: dict, v: dict) -> None:
    agg["trip_count"] += 1
    agg["sum_fare"] += v["fare"]
    agg["sum_dist"] += v["distance"]
    agg["sum_tip"] += v["tip"]
    agg["sum_total"] += v["total"]


def _row(key_name: str, key_value, agg: dict) -> dict:
    return {
        key_name: key_value,
        "trip_count": agg["trip_count"],
        # importes Decimal serializados como texto; distancia como numero
        "sum_fare_amount": str(agg["sum_fare"].quantize(Decimal("0.01"))),
        "sum_trip_distance": float(agg["sum_dist"]),
        "sum_tip_amount": str(agg["sum_tip"].quantize(Decimal("0.01"))),
        "sum_total_amount": str(agg["sum_total"].quantize(Decimal("0.01"))),
    }


def agregar(viajes: list[dict]) -> dict:
    tables = {m: defaultdict(_zero) for m in ("hourly", "daily", "zone", "payment")}
    for v in viajes:
        _add(tables["hourly"][v["ts"].isoformat()], v)
        _add(tables["daily"][v["ts"].date().isoformat()], v)
        _add(tables["zone"][v["zone"]], v)
        _add(tables["payment"][v["ptype"]], v)

    return {
        "hourly": [_row("trip_hour", k, a) for k, a in sorted(tables["hourly"].items())],
        "daily": [_row("trip_date", k, a) for k, a in sorted(tables["daily"].items())],
        "zone": [_row("pu_location_id", k, a) for k, a in sorted(tables["zone"].items())],
        "payment": [_row("payment_type", k, a) for k, a in sorted(tables["payment"].items())],
    }


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for i, site in enumerate(SITES):
        rng = random.Random(SEED + i)
        viajes = generar_viajes(rng, SITE_TRIPS[site])
        tablas = agregar(viajes)
        path = FIXTURES_DIR / f"{site}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(tablas, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"{site}: {len(viajes)} viajes -> {path.name}")


if __name__ == "__main__":
    main()
