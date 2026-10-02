"""Zonas de taxi de Nueva York (tabla oficial de la TLC).

Los datos de la parte 2 solo traen `pu_location_id` (por ejemplo, 161).
Esta tabla lo traduce a un nombre y un distrito (borough) legibles
("Midtown Center", "Manhattan") y permite buscar una zona por su nombre
("jfk" -> 132, JFK Airport).

Fuente: NYC Taxi & Limousine Commission, Taxi Zone Lookup Table
https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
(columnas LocationID, Borough, Zone, service_zone; 265 zonas).
"""

from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ZONES_CSV = Path(__file__).with_name("taxi_zone_lookup.csv")

UNKNOWN_ZONE = "zona desconocida"
UNKNOWN_BOROUGH = "desconocido"


def _normalize(text: str) -> str:
    """Minúsculas, sin tildes y con cualquier signo convertido en espacio."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


@lru_cache(maxsize=None)
def load_zones(path: Path = ZONES_CSV) -> dict[int, dict]:
    """Lee la tabla una sola vez: {location_id: {id, zone, borough, service_zone}}."""
    zones = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            location_id = int(row["LocationID"])
            zones[location_id] = {
                "id": location_id,
                "zone": row["Zone"],
                "borough": row["Borough"],
                "service_zone": row["service_zone"],
            }
    return zones


def zone_name(location_id) -> dict:
    """
    {id, zone, borough} de una zona. Un ID que no está en la tabla (o que
    no es un número) devuelve "zona desconocida" en lugar de fallar.
    """
    try:
        location_id = int(location_id)
    except (TypeError, ValueError):
        return {"id": location_id, "zone": UNKNOWN_ZONE, "borough": UNKNOWN_BOROUGH}

    zone = load_zones().get(location_id)
    if zone is None:
        return {"id": location_id, "zone": UNKNOWN_ZONE, "borough": UNKNOWN_BOROUGH}
    return {"id": zone["id"], "zone": zone["zone"], "borough": zone["borough"]}


def find_zone(query: str, limit: int = 5) -> list[dict]:
    """
    Busca zonas por nombre, sin distinguir mayúsculas ni tildes.

    Devuelve una lista de {id, zone, borough} ordenada por relevancia:
    1) nombre idéntico, 2) nombre que empieza por la búsqueda,
    3) todas las palabras de la búsqueda aparecen en el nombre.
    Lista vacía si no hay coincidencias. Puede haber varias: por ejemplo,
    "Corona" son dos zonas (56 y 57) y quien llama debe decidir o preguntar.
    """
    wanted = _normalize(query or "")
    if not wanted:
        return []
    words = wanted.split()

    ranked = []
    for zone in load_zones().values():
        name = _normalize(zone["zone"])
        name_words = name.split()
        if name == wanted:
            rank = 0
        elif name.startswith(wanted):
            rank = 1
        elif all(any(w.startswith(word) for w in name_words) for word in words):
            rank = 2
        else:
            continue
        ranked.append((rank, zone["id"], zone))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [
        {"id": z["id"], "zone": z["zone"], "borough": z["borough"]}
        for _, _, z in ranked[:limit]
    ]
