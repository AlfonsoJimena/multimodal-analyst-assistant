"""
Reference client for the replicated coordinator (issue #59).

The coordinator runs as a stateless replica on each site, and no
replica knows about the others -- failover is the CALLER's job. This
script is the reference implementation of that contract, for whoever
consumes the coordinator (e.g. the conversational agent, #66):

    1st  central    (primary)
    2nd  chamartin  (backup)
    3rd  atocha     (backup)

Each replica is tried in that order. A replica is skipped when it
cannot be reached, times out, or answers 5xx; the first one that
answers is used. A 4xx is returned as-is WITHOUT trying the next
replica: every replica runs the same code, so a bad request would
fail the same way on all of them.

Usage (from parte2_infraestructura_datos/):
    python -m scripts.coordinator_failover                  # /health
    python -m scripts.coordinator_failover /metrics/daily
    python -m scripts.coordinator_failover /metrics/zone pu_location_id=138

Replica URLs default to the host ports published by sites/*.env
(8100/8101/8102). Override with COORDINATOR_URLS, a comma-separated
list IN FAILOVER ORDER, e.g.:
    COORDINATOR_URLS=http://10.0.0.1:8100,http://10.0.0.2:8101,http://10.0.0.3:8102
"""

import json
import os
import sys

import httpx


# ============================================================
# Configuration
# ============================================================

DEFAULT_COORDINATOR_URLS = [
    "http://localhost:8100",  # central   (primary)
    "http://localhost:8101",  # chamartin (backup)
    "http://localhost:8102",  # atocha    (backup)
]

COORDINATOR_URLS = [
    url.strip()
    for url in os.getenv(
        "COORDINATOR_URLS", ",".join(DEFAULT_COORDINATOR_URLS)
    ).split(",")
    if url.strip()
]

TIMEOUT_SECONDS = float(os.getenv("COORDINATOR_TIMEOUT_SECONDS", "5"))


# ============================================================
# Failover
# ============================================================

class AllCoordinatorsDown(Exception):
    pass


def get_with_failover(
    path: str, params: dict | None = None
) -> tuple[str, httpx.Response, list[str]]:
    """
    Returns (url_of_the_replica_that_answered, response, skipped),
    where skipped lists every replica tried before it and why it failed.
    Raises AllCoordinatorsDown if no replica could answer.
    """
    errors = []

    for base_url in COORDINATOR_URLS:
        try:
            response = httpx.get(
                f"{base_url}{path}", params=params, timeout=TIMEOUT_SECONDS
            )
        except httpx.HTTPError as error:
            errors.append(f"{base_url}: {type(error).__name__}")
            continue

        if response.status_code >= 500:
            errors.append(f"{base_url}: HTTP {response.status_code}")
            continue

        return base_url, response, errors

    raise AllCoordinatorsDown("; ".join(errors))


# ============================================================
# Main
# ============================================================

def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "/health"
    params = dict(arg.split("=", 1) for arg in sys.argv[2:])

    try:
        base_url, response, skipped = get_with_failover(path, params)
    except AllCoordinatorsDown as error:
        print(f"ERROR: no coordinator replica answered -> {error}")
        sys.exit(1)

    for reason in skipped:
        print(f"Skipped:     {reason}")
    print(f"Answered by: {base_url} (HTTP {response.status_code})")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
