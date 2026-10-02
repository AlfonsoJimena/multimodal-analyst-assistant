"""Tests de la base de conocimiento (P3-05): zonas, pagos y glosario."""

from pathlib import Path

import pytest

from src.knowledge import PAYMENT_TYPES, find_zone, payment_name, zone_name
from src.knowledge.zones import ZONES_CSV, load_zones

GLOSSARY = Path(__file__).resolve().parent.parent / "src" / "knowledge" / "glosario.md"


# ------------------------------------------------------------
# Tabla de zonas
# ------------------------------------------------------------

def test_zone_table_is_the_official_one():
    zones = load_zones()
    assert ZONES_CSV.exists()
    assert len(zones) == 265
    assert set(zones) == set(range(1, 266))


def test_zone_name_known_id():
    assert zone_name(161) == {"id": 161, "zone": "Midtown Center", "borough": "Manhattan"}


def test_zone_name_accepts_text_ids():
    assert zone_name("132")["zone"] == "JFK Airport"


@pytest.mark.parametrize("bad_id", [0, 999, -1, None, "abc"])
def test_zone_name_unknown_id_does_not_fail(bad_id):
    result = zone_name(bad_id)
    assert result["zone"] == "zona desconocida"


@pytest.mark.parametrize("query", ["jfk", "JFK", "  Jfk  ", "jfk airport", "JFK Aírport"])
def test_find_zone_ignores_case_accents_and_spaces(query):
    assert find_zone(query)[0] == {"id": 132, "zone": "JFK Airport", "borough": "Queens"}


def test_find_zone_exact_name_comes_first():
    assert find_zone("Midtown Center")[0]["id"] == 161


def test_find_zone_partial_words():
    assert find_zone("times sq")[0]["zone"] == "Times Sq/Theatre District"


def test_find_zone_returns_every_homonym_first():
    # "Corona" son dos zonas distintas (56 y 57); "Flushing Meadows-Corona
    # Park" también contiene la palabra, pero va detrás de las exactas.
    ids = [z["id"] for z in find_zone("corona")]
    assert ids[:2] == [56, 57]


@pytest.mark.parametrize("query", ["", "   ", "barcelona", "zzz"])
def test_find_zone_without_match_returns_empty(query):
    assert find_zone(query) == []


# ------------------------------------------------------------
# Métodos de pago
# ------------------------------------------------------------

def test_payment_codes_follow_the_tlc_dictionary():
    assert set(PAYMENT_TYPES) == {0, 1, 2, 3, 4, 5, 6}
    assert payment_name(1) == "tarjeta"
    assert payment_name(2) == "efectivo"
    assert payment_name("4") == "disputa"


@pytest.mark.parametrize("code", [7, 99, None, "x"])
def test_unknown_payment_code_does_not_fail(code):
    assert payment_name(code) == f"código {code}"


# ------------------------------------------------------------
# Glosario
# ------------------------------------------------------------

def test_glossary_lists_every_payment_code():
    text = GLOSSARY.read_text(encoding="utf-8")
    for code, (name, original) in PAYMENT_TYPES.items():
        assert f"| {code} | {name} | {original} |" in text, code


@pytest.mark.parametrize("term", ["central", "chamartin", "atocha", "PULocationID % 3", "millas", "dólares"])
def test_glossary_covers_sites_and_units(term):
    assert term in GLOSSARY.read_text(encoding="utf-8")
