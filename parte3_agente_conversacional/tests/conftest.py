"""Configuracion de tests de la parte 3.

Dos tipos de test, igual que en la parte 2:

  - Unitarios (por defecto): sin red, sin Docker, sin LLM. Usan
    httpx.MockTransport y LLMs falsos. Corren en segundos:

        pytest

  - De integracion (@pytest.mark.integration): contra el coordinador
    real o el LLM real. Se saltan salvo que se pase --integration:

        pytest --integration
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Corre los tests que necesitan el coordinador real o el LLM.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--integration"):
        return

    skip = pytest.mark.skip(
        reason="necesita el coordinador real o el LLM: corre con --integration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
