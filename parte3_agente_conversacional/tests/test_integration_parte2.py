"""Pruebas de integración contra la Parte 2 real.

Estas pruebas requieren que la infraestructura de Parte 2 esté levantada
y se ejecutan únicamente con pytest --integration.

Los escenarios de fallo se seleccionan mediante la variable de entorno
INTEGRATION_FAILURE_SCENARIO:
- sin definir: infraestructura completa disponible
- site_down: una sede está caída
- coordinator_failover: el coordinador Central está caído
"""

import os

import pytest

from src.data.coordinator_client import CoordinatorClient, CoordinatorResult


pytestmark = pytest.mark.integration

FAILURE_SCENARIO = os.getenv("INTEGRATION_FAILURE_SCENARIO")


@pytest.mark.skipif(
    FAILURE_SCENARIO is not None,
    reason="Este test requiere la infraestructura completa disponible.",
)
def test_parte2_real_tres_sedes_disponibles():
    """El coordinador real responde con datos de las tres sedes."""
    client = CoordinatorClient()

    result = client.daily(breakdown="site")

    assert isinstance(result, CoordinatorResult)
    assert result.served_by
    assert result.partial is False
    assert result.sites_failed == []
    assert set(result.sites_ok) == {"central", "chamartin", "atocha"}

    sites_in_data = {row["site_id"] for row in result.data}
    assert sites_in_data == {"central", "chamartin", "atocha"}


@pytest.mark.skipif(
    FAILURE_SCENARIO != "site_down",
    reason="Requiere ejecutar con INTEGRATION_FAILURE_SCENARIO=site_down.",
)
def test_parte2_real_respuesta_parcial_con_sede_caida():
    """Con una sede caída, el coordinador devuelve las restantes como parcial."""
    client = CoordinatorClient()

    result = client.daily(breakdown="site")

    assert isinstance(result, CoordinatorResult)
    assert result.partial is True
    assert result.sites_failed

    failed = set(result.sites_failed)
    assert failed < {"central", "chamartin", "atocha"}

    sites_in_data = {row["site_id"] for row in result.data}

    assert sites_in_data == set(result.sites_ok)
    assert sites_in_data.isdisjoint(failed)


@pytest.mark.skipif(
    FAILURE_SCENARIO != "coordinator_failover",
    reason="Requiere ejecutar con INTEGRATION_FAILURE_SCENARIO=coordinator_failover.",
)
def test_parte2_real_failover_coordinador_central():
    """Si cae el coordinador Central, el cliente hace failover a Chamartín."""
    client = CoordinatorClient()

    result = client.daily(breakdown="site")

    assert isinstance(result, CoordinatorResult)

    # Central falla y el cliente continúa con la siguiente réplica: Chamartín.
    assert result.served_by == "http://localhost:8101"
    assert any(
        "http://localhost:8100" in skipped
        for skipped in result.skipped
    )

    # La caída de una réplica no implica perder ninguna sede.
    assert result.partial is False
    assert result.sites_failed == []
    assert set(result.sites_ok) == {"central", "chamartin", "atocha"}

    sites_in_data = {row["site_id"] for row in result.data}
    assert sites_in_data == {"central", "chamartin", "atocha"}
