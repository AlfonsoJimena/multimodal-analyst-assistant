"""Códigos de método de pago (campo `payment_type` del dataset de la TLC).

Único mapa del proyecto: lo usan las herramientas, el glosario y el prompt.
Comprobado con el diccionario de datos oficial de la TLC para los yellow
taxis (versión del 18/03/2025), que añade el código 0 (Flex Fare):
https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf

La muestra de la parte 2 (enero de 2020) solo contiene los códigos 1 a 4.
"""

from __future__ import annotations

# código -> (nombre en español, nombre original de la TLC)
PAYMENT_TYPES: dict[int, tuple[str, str]] = {
    0: ("tarifa Flex Fare", "Flex Fare trip"),
    1: ("tarjeta", "Credit card"),
    2: ("efectivo", "Cash"),
    3: ("sin cargo", "No charge"),
    4: ("disputa", "Dispute"),
    5: ("desconocido", "Unknown"),
    6: ("anulado", "Voided trip"),
}


def payment_name(code) -> str:
    """Nombre en español de un código de pago; "código N" si no se conoce."""
    try:
        return PAYMENT_TYPES[int(code)][0]
    except (KeyError, TypeError, ValueError):
        return f"código {code}"
