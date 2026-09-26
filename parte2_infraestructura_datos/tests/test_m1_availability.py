"""
M1 - Availability with sites down (issue #66, restriction E2).

E2 asks us to "specify the behaviour when a location is not available".
Our answer has two layers, and M1 measures both:

  1. A site_api is down or hung -> any coordinator replica still
     answers with the other sites' aggregates, flagged with
     partial=true and the missing site in sites_failed.
  2. A coordinator replica is down -> the caller fails over
     central -> chamartin -> atocha (scripts/coordinator_failover.py).

Metric definitions (reported per scenario in tests/results/m1_availability.md):

  availability   = queries answered with HTTP 200 / queries sent
  completeness   = answered queries with partial=false / answered queries
  flag accuracy  = answered queries whose sites_failed is exactly the set
                   of sites we took down / answered queries

Target: availability = 100 % and flag accuracy = 100 % in every scenario
where at least one site (and therefore one coordinator replica) is up.
With all three sites down the expected availability is 0 %.

Unit tests (default `pytest`) simulate the sites with httpx.MockTransport.
Integration tests (`pytest --integration`) stop/pause real containers.
"""

import asyncio
import os
import statistics
import time
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    COORDINATOR_URLS,
    SITE_API_URLS,
    SITES,
    docker,
    wait_until_healthy,
    write_results,
)


# ============================================================
# Synthetic site data (unit tests)
# Volumes are deliberately very different so that a wrong
# "average of averages" would not go unnoticed.
# ============================================================

ENDPOINT_KEYS = {
    "/metrics/hourly": ("trip_hour", "2020-01-01T10:00:00"),
    "/metrics/daily": ("trip_date", "2020-01-01"),
    "/metrics/zone": ("pu_location_id", 138),
    "/metrics/payment": ("payment_type", 1),
}

SITE_TRIP_COUNT = {"central": 10, "chamartin": 30, "atocha": 60}
SITE_SUM_FARE = {"central": "100.00", "chamartin": "450.00", "atocha": "600.00"}


def _row(site: str, key: str, key_value) -> dict:
    count = SITE_TRIP_COUNT[site]
    return {
        key: key_value,
        "trip_count": count,
        # site_api serialises Decimal as a JSON string, floats as numbers
        "sum_fare_amount": SITE_SUM_FARE[site],
        "sum_trip_distance": 2.0 * count,
        "sum_tip_amount": f"{count}.00",
        "sum_total_amount": f"{3 * count}.00",
    }


def build_payloads() -> dict:
    return {
        site: {
            path: [_row(site, key, value)]
            for path, (key, value) in ENDPOINT_KEYS.items()
        }
        for site in SITES
    }


@pytest.fixture
def coordinator(fake_sites):
    from src.coordinator.main import app

    sites = fake_sites(build_payloads())
    with TestClient(app) as client:
        yield client, sites


def _expected_totals(alive: list[str]) -> tuple[int, Decimal]:
    count = sum(SITE_TRIP_COUNT[s] for s in alive)
    fare = sum((Decimal(SITE_SUM_FARE[s]) for s in alive), Decimal("0"))
    return count, fare


# ============================================================
# Unit tests - layer 1: a site is down, the coordinator degrades
# ============================================================

@pytest.mark.parametrize("path", list(ENDPOINT_KEYS))
def test_all_sites_up_gives_complete_answer(coordinator, path):
    client, _ = coordinator

    response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is False
    assert body["sites_failed"] == []
    assert sorted(body["sites_ok"]) == sorted(SITES)
    assert body["data"][0]["trip_count"] == 100


@pytest.mark.parametrize("path", list(ENDPOINT_KEYS))
@pytest.mark.parametrize("failure", ["down", "timeout", "error"])
@pytest.mark.parametrize("failed_site", SITES)
def test_one_site_failing_gives_partial_answer_not_an_error(
    coordinator, path, failure, failed_site
):
    client, sites = coordinator
    sites.behaviour[failed_site] = failure
    alive = [s for s in SITES if s != failed_site]

    response = client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is True
    assert body["sites_failed"] == [failed_site]
    assert sorted(body["sites_ok"]) == sorted(alive)

    # The surviving sites' figures are still combined correctly,
    # including the weighted average (sum / count, never avg of avgs).
    expected_count, expected_fare = _expected_totals(alive)
    row = body["data"][0]
    assert row["trip_count"] == expected_count
    assert Decimal(row["sum_fare_amount"]) == expected_fare
    assert Decimal(row["avg_fare_amount"]) == pytest.approx(
        expected_fare / expected_count
    )


@pytest.mark.parametrize("failed_sites", list(combinations(SITES, 2)))
def test_two_sites_failing_still_answers_with_the_third(coordinator, failed_sites):
    client, sites = coordinator
    for site in failed_sites:
        sites.behaviour[site] = "down"
    (alive,) = [s for s in SITES if s not in failed_sites]

    response = client.get("/metrics/daily")

    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is True
    assert sorted(body["sites_failed"]) == sorted(failed_sites)
    assert body["sites_ok"] == [alive]
    assert body["data"][0]["trip_count"] == SITE_TRIP_COUNT[alive]


def test_all_sites_failing_returns_empty_partial_answer(coordinator):
    """
    Documents the CURRENT contract: with no site reachable the
    coordinator still answers 200 with partial=true and no data
    (it does not return 503). The caller must therefore check
    sites_ok, not only the status code.
    """
    client, sites = coordinator
    for site in SITES:
        sites.behaviour[site] = "down"

    response = client.get("/metrics/daily")

    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is True
    assert body["sites_ok"] == []
    assert sorted(body["sites_failed"]) == sorted(SITES)
    assert body["data"] == []


def test_sites_are_queried_concurrently(monkeypatch):
    """
    A slow site must not add its latency to the others: the three
    calls run in parallel, so the total is ~one delay, not three.
    """
    from src.coordinator import clients

    delay = 0.3
    real_async_client = httpx.AsyncClient

    async def slow_handler(request):
        await asyncio.sleep(delay)
        return httpx.Response(200, json=[])

    def patched_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(slow_handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(clients.httpx, "AsyncClient", patched_async_client)

    start = time.perf_counter()
    results = asyncio.run(clients.fetch_all_sites("/metrics/daily", {}))
    elapsed = time.perf_counter() - start

    assert all(result.ok for result in results)
    assert elapsed < 2 * delay, f"calls look sequential: {elapsed:.2f}s"


# ============================================================
# Unit tests - layer 2: a coordinator replica is down, the
# caller fails over central -> chamartin -> atocha
# ============================================================

class FakeReplicas:
    """Stands in for httpx.get inside scripts.coordinator_failover."""

    def __init__(self, behaviour: dict):
        self.behaviour = behaviour  # base_url -> "down" | "timeout" | int status
        self.calls = []

    def get(self, url, params=None, timeout=None):
        base_url = next(b for b in self.behaviour if url.startswith(b))
        self.calls.append(base_url)
        request = httpx.Request("GET", url)
        outcome = self.behaviour[base_url]
        if outcome == "down":
            raise httpx.ConnectError("simulated", request=request)
        if outcome == "timeout":
            raise httpx.ReadTimeout("simulated", request=request)
        return httpx.Response(outcome, json={"replica": base_url}, request=request)


@pytest.fixture
def failover(monkeypatch):
    from scripts import coordinator_failover

    def install(outcomes: list):
        urls = coordinator_failover.COORDINATOR_URLS
        fake = FakeReplicas(dict(zip(urls, outcomes)))
        monkeypatch.setattr(coordinator_failover.httpx, "get", fake.get)
        return coordinator_failover, urls, fake

    return install


def test_failover_uses_primary_when_it_is_up(failover):
    module, urls, fake = failover([200, 200, 200])

    base_url, response, skipped = module.get_with_failover("/health")

    assert base_url == urls[0]
    assert skipped == []
    assert fake.calls == [urls[0]]


@pytest.mark.parametrize("primary_failure", ["down", "timeout", 503])
def test_failover_skips_primary_when_it_fails(failover, primary_failure):
    module, urls, fake = failover([primary_failure, 200, 200])

    base_url, response, skipped = module.get_with_failover("/metrics/daily")

    assert base_url == urls[1]
    assert response.status_code == 200
    assert len(skipped) == 1


def test_failover_reaches_last_replica(failover):
    module, urls, _ = failover(["down", "timeout", 200])

    base_url, _, skipped = module.get_with_failover("/metrics/daily")

    assert base_url == urls[2]
    assert len(skipped) == 2


def test_failover_does_not_retry_client_errors(failover):
    module, urls, fake = failover([422, 200, 200])

    base_url, response, _ = module.get_with_failover("/metrics/zone")

    assert response.status_code == 422
    assert fake.calls == [urls[0]]


def test_failover_raises_when_every_replica_is_down(failover):
    module, _, _ = failover(["down", "down", 500])

    with pytest.raises(module.AllCoordinatorsDown):
        module.get_with_failover("/health")


def test_client_timeout_is_longer_than_coordinator_site_timeout():
    """
    Regression guard for the bug M1 found in scenario S4: with equal
    timeouts, one hung site made the caller drop every replica's valid
    partial answer (availability 0 %). The caller must wait longer than
    the coordinator waits for a site.
    """
    from scripts import coordinator_failover
    from src.coordinator import clients

    assert coordinator_failover.TIMEOUT_SECONDS > clients.SITE_API_TIMEOUT_SECONDS


# ============================================================
# Integration - real containers (pytest --integration)
# ============================================================

REQUESTS_PER_SCENARIO = int(os.getenv("M1_REQUESTS", "20"))
QUERY_PATHS = list(ENDPOINT_KEYS)


@dataclass
class Scenario:
    """
    down_sites:  site_api AND coordinator of the site stopped, i.e.
                 everything the site exposes to the outside is gone.
    down_apis:   only the site_api stopped (its coordinator stays up).
    paused_apis: site_api frozen with `docker pause` -> TCP accepts but
                 never answers, which exercises the coordinator timeout.
    """

    name: str
    description: str
    down_sites: list = field(default_factory=list)
    down_apis: list = field(default_factory=list)
    paused_apis: list = field(default_factory=list)

    @property
    def expected_failed(self) -> set:
        return set(self.down_sites) | set(self.down_apis) | set(self.paused_apis)

    @property
    def expected_replica(self):
        alive = [s for s in SITES if s not in self.down_sites]
        return alive[0] if alive else None


SCENARIOS = [
    Scenario("S0_todo_ok", "Las tres sedes en pie"),
    Scenario("S1_api_central_caida", "site_api de Central parada", down_apis=["central"]),
    Scenario("S2_api_chamartin_caida", "site_api de Chamartín parada", down_apis=["chamartin"]),
    Scenario("S3_api_atocha_caida", "site_api de Atocha parada", down_apis=["atocha"]),
    Scenario("S4_api_atocha_colgada", "site_api de Atocha congelada (docker pause)", paused_apis=["atocha"]),
    Scenario("S5_sede_central_caida", "Central entera (API + coordinador primario)", down_sites=["central"]),
    Scenario("S6_dos_sedes_caidas", "Chamartín y Atocha enteras", down_sites=["chamartin", "atocha"]),
    Scenario("S7_central_y_chamartin_caidas", "Central y Chamartín enteras", down_sites=["central", "chamartin"]),
    Scenario("S8_tres_sedes_caidas", "Las tres sedes caídas", down_sites=list(SITES)),
]


def _containers(scenario: Scenario) -> tuple[list, list]:
    stopped = [f"{s}-site-api" for s in scenario.down_sites + scenario.down_apis]
    stopped += [f"{s}-coordinator" for s in scenario.down_sites]
    paused = [f"{s}-site-api" for s in scenario.paused_apis]
    return stopped, paused


def _run_queries(scenario: Scenario) -> dict:
    from scripts.coordinator_failover import AllCoordinatorsDown, get_with_failover

    replica_by_url = {url: site for site, url in COORDINATOR_URLS.items()}
    answered = complete = flag_ok = 0
    answered_by = {}
    latencies_ms = []

    for i in range(REQUESTS_PER_SCENARIO):
        path = QUERY_PATHS[i % len(QUERY_PATHS)]
        start = time.perf_counter()
        try:
            base_url, response, _ = get_with_failover(path)
        except AllCoordinatorsDown:
            continue
        finally:
            latencies_ms.append((time.perf_counter() - start) * 1000)

        if response.status_code != 200:
            continue

        body = response.json()
        answered += 1
        complete += body["partial"] is False
        flag_ok += (
            set(body["sites_failed"]) == scenario.expected_failed
            and body["partial"] == bool(scenario.expected_failed)
        )
        replica = replica_by_url.get(base_url, base_url)
        answered_by[replica] = answered_by.get(replica, 0) + 1

    sent = REQUESTS_PER_SCENARIO
    latencies_ms.sort()
    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "sites_down": sorted(scenario.expected_failed),
        "coordinators_down": sorted(scenario.down_sites),
        "requests": sent,
        "answered": answered,
        "availability": answered / sent,
        "completeness": complete / answered if answered else 0.0,
        "flag_accuracy": flag_ok / answered if answered else 0.0,
        "answered_by": answered_by,
        "expected_replica": scenario.expected_replica,
        "latency_ms_p50": statistics.median(latencies_ms),
        "latency_ms_p95": latencies_ms[max(0, int(0.95 * len(latencies_ms)) - 1)],
        "latency_ms_max": latencies_ms[-1],
    }


def _markdown(rows: list) -> str:
    lines = [
        "# M1 · Disponibilidad con sedes caídas",
        "",
        f"{REQUESTS_PER_SCENARIO} consultas por escenario, repartidas entre "
        "/metrics/hourly, /daily, /zone y /payment, lanzadas con el cliente "
        "de failover (central → chamartín → atocha).",
        "",
        "| Escenario | Sedes sin API | Coordinadores caídos | Disponibilidad | "
        "Completas | Marcado correcto | Responde | p50 (ms) | p95 (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['description']} | {', '.join(r['sites_down']) or '—'} | "
            f"{', '.join(r['coordinators_down']) or '—'} | "
            f"{r['availability']:.0%} | {r['completeness']:.0%} | "
            f"{r['flag_accuracy']:.0%} | "
            f"{', '.join(r['answered_by']) or '—'} | "
            f"{r['latency_ms_p50']:.0f} | {r['latency_ms_p95']:.0f} |"
        )
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def m1_report():
    rows = []
    yield rows
    if rows:
        path = write_results("m1_availability", {"scenarios": rows}, _markdown(rows))
        print(f"\nM1 results written to {path}")


@pytest.mark.integration
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_m1_availability_scenario(deployment_up, m1_report, scenario):
    stopped, paused = _containers(scenario)
    all_urls = list(SITE_API_URLS.values()) + list(COORDINATOR_URLS.values())

    try:
        for name in stopped:
            docker("stop", name)
        for name in paused:
            docker("pause", name)

        result = _run_queries(scenario)
        m1_report.append(result)
    finally:
        for name in paused:
            docker("unpause", name)
        for name in stopped:
            docker("start", name)
        wait_until_healthy(all_urls)

    if scenario.expected_replica is None:
        assert result["availability"] == 0.0
        return

    assert result["availability"] == 1.0, result
    assert result["flag_accuracy"] == 1.0, result
    assert set(result["answered_by"]) == {scenario.expected_replica}, result
