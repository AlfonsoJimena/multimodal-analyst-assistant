"""
Shared test configuration for the three quality metrics (M1, M2, M3).

Two kinds of tests live in tests/:

  - Unit tests (default): no Docker, no network. Site APIs and
    coordinator replicas are simulated with httpx.MockTransport, so
    they run anywhere in a couple of seconds:

        pytest

  - Integration tests (@pytest.mark.integration): run against the real
    deployment (make up-all-coordinators). They are skipped unless
    --integration is passed, because they stop/pause containers:

        pytest --integration

Every metric writes its measured figures to tests/results/ (JSON +
Markdown) so they can be pasted into the report.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest


# ============================================================
# Paths and deployment constants
# ============================================================

PART2_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = PART2_DIR / "tests" / "results"

# Same order as the coordinator failover (central -> chamartin -> atocha).
SITES = ["central", "chamartin", "atocha"]

# Host-side URLs, as published by sites/<site>.env. Overridable with
# the same variable names the coordinator uses.
SITE_API_URLS = {
    "central": os.getenv("SITE_API_URL_CENTRAL", "http://localhost:8000"),
    "chamartin": os.getenv("SITE_API_URL_CHAMARTIN", "http://localhost:8001"),
    "atocha": os.getenv("SITE_API_URL_ATOCHA", "http://localhost:8002"),
}

COORDINATOR_URLS = {
    "central": "http://localhost:8100",
    "chamartin": "http://localhost:8101",
    "atocha": "http://localhost:8102",
}

HEALTH_TIMEOUT_SECONDS = float(os.getenv("TEST_HEALTH_TIMEOUT_SECONDS", "120"))


# ============================================================
# --integration flag
# ============================================================

def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run tests that need the Docker deployment (they stop/pause containers).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--integration"):
        return

    skip = pytest.mark.skip(reason="needs the Docker deployment: run with --integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# ============================================================
# Unit-test helper: fake site_api instances behind httpx
# ============================================================

class FakeSites:
    """
    Replaces httpx.AsyncClient so that every request the coordinator
    makes to a site_api is answered by an in-memory handler instead of
    the network.

    behaviour[site] is one of:
      "ok"       -> 200 with the rows in payloads[site][path]
      "down"     -> httpx.ConnectError (container stopped)
      "timeout"  -> httpx.ReadTimeout  (container hung)
      "error"    -> HTTP 500           (e.g. its Postgres is down)
    """

    def __init__(self, site_urls: dict, payloads: dict):
        self.payloads = payloads
        self.behaviour = {site: "ok" for site in site_urls}
        self.calls = []

        self._site_by_origin = {}
        for site, url in site_urls.items():
            parsed = httpx.URL(url)
            self._site_by_origin[(parsed.host, parsed.port)] = site

    def handler(self, request: httpx.Request) -> httpx.Response:
        site = self._site_by_origin[(request.url.host, request.url.port)]
        self.calls.append((site, request.url.path))

        behaviour = self.behaviour[site]
        if behaviour == "down":
            raise httpx.ConnectError("simulated: site down", request=request)
        if behaviour == "timeout":
            raise httpx.ReadTimeout("simulated: site hung", request=request)
        if behaviour == "error":
            return httpx.Response(500, json={"detail": "simulated error"})

        return httpx.Response(200, json=self.payloads[site].get(request.url.path, []))


@pytest.fixture
def fake_sites(monkeypatch):
    """
    Usage:
        sites = fake_sites(payloads)
        sites.behaviour["atocha"] = "down"
    """
    from src.coordinator import clients

    real_async_client = httpx.AsyncClient

    def install(payloads: dict) -> FakeSites:
        fake = FakeSites(clients.SITE_API_URLS, payloads)

        def patched_async_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(fake.handler)
            return real_async_client(*args, **kwargs)

        monkeypatch.setattr(clients.httpx, "AsyncClient", patched_async_client)
        return fake

    return install


# ============================================================
# Integration helpers: docker control and health waits
# ============================================================

def docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def is_healthy(url: str) -> bool:
    try:
        return httpx.get(f"{url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def wait_until_healthy(urls: list[str], timeout: float = HEALTH_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    pending = list(urls)
    while pending and time.monotonic() < deadline:
        pending = [url for url in pending if not is_healthy(url)]
        if pending:
            time.sleep(2)
    if pending:
        raise TimeoutError(f"Still unhealthy after {timeout:.0f}s: {pending}")


@pytest.fixture(scope="session")
def deployment_up():
    """Skips the integration tests with a clear message if the stack is not up."""
    all_urls = list(SITE_API_URLS.values()) + list(COORDINATOR_URLS.values())
    down = [url for url in all_urls if not is_healthy(url)]
    if down:
        pytest.skip(
            "Deployment not reachable (run `make up-all-coordinators` and wait "
            f"until it is healthy). Not answering /health: {down}"
        )
    try:
        docker("version", "--format", "{{.Server.Version}}")
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"docker CLI not usable from this shell: {error}")


# ============================================================
# Results
# ============================================================

def write_results(name: str, payload: dict, markdown: str) -> Path:
    """Writes tests/results/<name>.json and <name>.md; returns the .md path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **payload,
    }
    (RESULTS_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path = RESULTS_DIR / f"{name}.md"
    md_path.write_text(markdown, encoding="utf-8")
    return md_path
