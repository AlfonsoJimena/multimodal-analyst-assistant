"""
M2 - Raw data transfer out of each site (issue #67, restriction E2).

E2: "each location keeps its own data and cannot centralise raw records;
answer unified queries without transferring raw data unnecessarily".
M2 checks that nothing trip-level ever leaves a site, from three angles:

  1. Contract (unit, no Docker): every JSON response declared by
     site_api and the coordinator only contains aggregate fields
     (group keys, trip_count, sum_*, avg_*) -- a new trip-level field in
     any endpoint makes this fail before it is ever deployed.
  2. Traffic (integration): every endpoint of every site_api is called
     against real data; a response leaks if it contains a non-aggregate
     field or any real trip_id from data/prepared/.
  3. Exposure surface (integration): which containers publish ports on
     the host and which ones join the shared network pids-interconnect.

Metric definitions (tests/results/m2_transfer.md):

  raw bytes out   = bytes of responses that contain trip-level data (target 0)
  transfer ratio  = bytes served by a full sweep of /metrics/* / bytes of
                    the site's raw CSVs
  exposure        = containers with access to raw data that are reachable
                    from outside the site (target: none)
"""

import csv
import json
import re
from pathlib import Path

import httpx
import pytest

from tests.conftest import (
    COORDINATOR_URLS,
    PART2_DIR,
    SITE_API_URLS,
    SITES,
    docker,
    write_results,
)


# ============================================================
# What is allowed to leave a site
# ============================================================

ENVELOPE_FIELDS = {"sites_ok", "sites_failed", "partial", "data"}
HEALTH_FIELDS = {"status", "site_id", "failover_priority"}
GROUP_KEYS = {"trip_hour", "trip_date", "pu_location_id", "payment_type", "rejection_reason"}
AGGREGATE_FIELDS = {
    "trip_count",
    "rejected_count",
    "sum_fare_amount",
    "sum_trip_distance",
    "sum_tip_amount",
    "sum_total_amount",
    "avg_fare_amount",
    "avg_trip_distance",
    "avg_tip_amount",
    "avg_total_amount",
}
ALLOWED_FIELDS = ENVELOPE_FIELDS | HEALTH_FIELDS | GROUP_KEYS | AGGREGATE_FIELDS

TRIP_ID_PATTERN = re.compile(r"\b[0-9a-f]{64}\b")

METRIC_PATHS = ["/metrics/hourly", "/metrics/daily", "/metrics/zone", "/metrics/payment"]
OTHER_SITE_PATHS = ["/quarantine/summary", "/health", "/prometheus"]

# Services that hold trip-level data inside a site.
RAW_CAPABLE_SERVICES = {
    "postgres",  # silver_rejected stores whole trip rows
    "kafka",
    "producer",
    "spark_stream_bronze",
    "spark_silver",
    "spark_sink_postgres",
}
# producer publishes a port, but only for Prometheus counters (no trip data).
METRICS_ONLY_PORTS = {"producer": {"9000/tcp"}}
INTERCONNECT_ALLOWED = {"site_api", "coordinator"}

# Known exposure, pending a team decision (#61). While it stays exactly
# like this the exposure test is reported as xfail instead of failing.
KNOWN_EXPOSURES = {"postgres"}
KNOWN_EXPOSURE_REASON = (
    "Postgres publica su puerto en el host (5432-5434) con credenciales de "
    "desarrollo y silver_rejected puede guardar filas completas de viajes. "
    "Pendiente de decisión del equipo (#61): quitar el puerto o limitarlo a 127.0.0.1."
)


# ============================================================
# Leak detector (pure functions, unit-tested below)
# ============================================================

def collect_keys(payload) -> set:
    """Every dict key at any depth of a JSON payload."""
    keys = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key)
            keys |= collect_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            keys |= collect_keys(item)
    return keys


def find_leaks(body: bytes, content_type: str, known_trip_ids: set) -> dict:
    """
    Returns {"forbidden_fields": [...], "trip_ids": n}. Empty lists / 0
    mean the response only carries aggregates.
    """
    text = body.decode("utf-8", errors="replace")
    trip_ids = {m for m in TRIP_ID_PATTERN.findall(text) if m in known_trip_ids}

    forbidden = set()
    if "json" in content_type:
        forbidden = collect_keys(json.loads(text)) - ALLOWED_FIELDS

    return {"forbidden_fields": sorted(forbidden), "trip_ids": len(trip_ids)}


# ============================================================
# Unit tests - contract (no Docker)
# ============================================================

def _schema_properties(openapi: dict, schema: dict, seen=None) -> set:
    """All property names reachable from a response schema ($ref resolved)."""
    seen = seen if seen is not None else set()
    names = set()

    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return names
        seen.add(ref)
        target = openapi
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        return _schema_properties(openapi, target, seen)

    for name, sub in schema.get("properties", {}).items():
        names.add(name)
        names |= _schema_properties(openapi, sub, seen)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            names |= _schema_properties(openapi, schema[key], seen)
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(key, []):
            names |= _schema_properties(openapi, sub, seen)
    return names


def _declared_response_fields(app) -> dict:
    openapi = app.openapi()
    fields = {}
    for path, methods in openapi["paths"].items():
        for method in methods.values():
            content = method.get("responses", {}).get("200", {}).get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            fields[path] = _schema_properties(openapi, schema)
    return fields


@pytest.mark.parametrize("service", ["site_api", "coordinator"])
def test_declared_responses_only_contain_aggregates(service):
    if service == "site_api":
        from src.site_api.main import app
    else:
        from src.coordinator.main import app

    declared = _declared_response_fields(app)

    offending = {
        path: sorted(fields - ALLOWED_FIELDS)
        for path, fields in declared.items()
        if fields - ALLOWED_FIELDS
    }
    assert not offending, f"{service} declares non-aggregate fields: {offending}"


@pytest.mark.parametrize("service", ["site_api", "coordinator"])
def test_every_metric_row_carries_a_trip_count(service):
    """A row without trip_count would not be a group of trips."""
    if service == "site_api":
        from src.site_api.main import app
    else:
        from src.coordinator.main import app

    declared = _declared_response_fields(app)
    for path in METRIC_PATHS:
        assert "trip_count" in declared[path], path


def test_leak_detector_flags_trip_level_payloads():
    """A detector that never fires would make M2 pass vacuously."""
    trip_id = "a" * 64
    leaking = json.dumps(
        [{"trip_id": trip_id, "pickup_datetime": "2020-01-01T00:28:15", "fare_amount": "6.00"}]
    ).encode()

    result = find_leaks(leaking, "application/json", {trip_id})

    assert result["forbidden_fields"] == ["fare_amount", "pickup_datetime", "trip_id"]
    assert result["trip_ids"] == 1


def test_leak_detector_accepts_aggregates():
    aggregated = json.dumps(
        {
            "sites_ok": ["central"], "sites_failed": [], "partial": False,
            "data": [{"payment_type": 1, "trip_count": 3, "sum_fare_amount": "30.00"}],
        }
    ).encode()

    assert find_leaks(aggregated, "application/json", {"b" * 64}) == {
        "forbidden_fields": [], "trip_ids": 0,
    }


def test_leak_detector_finds_trip_ids_in_plain_text():
    trip_id = "c" * 64
    body = f"# some metric\nsite_api_requests_total{{id=\"{trip_id}\"}} 1\n".encode()

    assert find_leaks(body, "text/plain", {trip_id})["trip_ids"] == 1


# ============================================================
# Integration - real deployment with data (pytest --integration)
# ============================================================

PREPARED_DIR = PART2_DIR / "data" / "prepared"


def _load_raw(site: str) -> tuple[set, int, int]:
    """(trip_ids, raw bytes held by the site, raw bytes of its realtime file)."""
    site_dir = PREPARED_DIR / site
    files = sorted(site_dir.glob("*.csv"))
    trip_ids = set()
    for path in files:
        with path.open(newline="", encoding="utf-8") as handle:
            trip_ids |= {row["trip_id"] for row in csv.DictReader(handle)}
    realtime = site_dir / "realtime.csv"
    return (
        trip_ids,
        sum(p.stat().st_size for p in files),
        realtime.stat().st_size if realtime.exists() else 0,
    )


def _measure(url: str, path: str, known_trip_ids: set) -> dict:
    response = httpx.get(f"{url}{path}", timeout=15)
    content_type = response.headers.get("content-type", "")
    leaks = find_leaks(response.content, content_type, known_trip_ids)
    leaking = bool(leaks["forbidden_fields"] or leaks["trip_ids"])

    singleton_groups = 0
    if path in METRIC_PATHS and response.status_code == 200:
        body = response.json()
        rows = body["data"] if isinstance(body, dict) else body
        singleton_groups = sum(1 for row in rows if row.get("trip_count") == 1)
        rows_count = len(rows)
        trips = sum(row.get("trip_count", 0) for row in rows)
    else:
        rows_count = trips = 0

    return {
        "path": path,
        "status": response.status_code,
        "bytes": len(response.content),
        "rows": rows_count,
        "trips": trips,
        "leak_bytes": len(response.content) if leaking else 0,
        "singleton_groups": singleton_groups,
        **leaks,
    }


@pytest.fixture(scope="module")
def traffic(deployment_up):
    if not PREPARED_DIR.exists():
        pytest.skip("data/prepared/ not found: run `python -m scripts.prepare_data` first")

    raw = {site: _load_raw(site) for site in SITES}
    all_trip_ids = set().union(*(ids for ids, _, _ in raw.values()))

    sites = {}
    for site in SITES:
        _, raw_bytes, realtime_bytes = raw[site]
        calls = [
            _measure(SITE_API_URLS[site], path, all_trip_ids)
            for path in METRIC_PATHS + OTHER_SITE_PATHS
        ]
        sweep = [c for c in calls if c["path"] in METRIC_PATHS]
        sites[site] = {
            "raw_bytes": raw_bytes,
            "realtime_bytes": realtime_bytes,
            "trip_ids_at_site": len(raw[site][0]),
            "sweep_bytes": sum(c["bytes"] for c in sweep),
            "trips_in_gold": next(c["trips"] for c in sweep if c["path"] == "/metrics/payment"),
            "leak_bytes": sum(c["leak_bytes"] for c in calls),
            "singleton_groups": sum(c["singleton_groups"] for c in sweep),
            "calls": calls,
        }

    coordinator = [
        _measure(COORDINATOR_URLS["central"], path, all_trip_ids) for path in METRIC_PATHS
    ]
    return {"sites": sites, "coordinator": coordinator}


def _container_facts(site: str) -> list[dict]:
    names = docker(
        "ps", "-a", "--filter", f"label=com.docker.compose.project={site}",
        "--format", "{{.Names}}",
    ).split()
    if not names:
        return []

    facts = []
    for info in json.loads(docker("inspect", *names)):
        service = info["Config"]["Labels"].get("com.docker.compose.service", "?")
        bindings = info["HostConfig"].get("PortBindings") or {}
        published = sorted(
            f"{b.get('HostIp') or '0.0.0.0'}:{b['HostPort']}->{port}"
            for port, binds in bindings.items()
            for b in (binds or [])
        )
        networks = sorted((info["NetworkSettings"].get("Networks") or {}).keys())
        facts.append({
            "container": info["Name"].lstrip("/"),
            "service": service,
            "published_ports": published,
            "published_container_ports": sorted(bindings.keys()),
            "networks": networks,
        })
    return facts


@pytest.fixture(scope="module")
def exposure(deployment_up):
    return {site: _container_facts(site) for site in SITES}


def _raw_exposures(facts: list[dict]) -> set:
    offenders = set()
    for fact in facts:
        if fact["service"] not in RAW_CAPABLE_SERVICES or not fact["published_ports"]:
            continue
        allowed = METRICS_ONLY_PORTS.get(fact["service"], set())
        if set(fact["published_container_ports"]) - allowed:
            offenders.add(fact["service"])
    return offenders


def _markdown(traffic: dict, exposure: dict) -> str:
    lines = [
        "# M2 · Transferencia de datos crudos fuera de cada sede",
        "",
        "## Tráfico por sede",
        "",
        "Barrido completo = una llamada a cada `/metrics/*` de la `site_api`. "
        "Bytes crudos de la sede = sus CSV preparados (histórico + realtime).",
        "",
        "| Sede | Bytes crudos en la sede | Bytes que salen (barrido) | Ratio | "
        "Bytes crudos que salen | trip_id filtrados | Viajes en Gold | Grupos con 1 viaje |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for site, s in traffic["sites"].items():
        ratio = s["sweep_bytes"] / s["raw_bytes"] if s["raw_bytes"] else 0
        leaked_ids = sum(c["trip_ids"] for c in s["calls"])
        lines.append(
            f"| {site} | {s['raw_bytes']:,} | {s['sweep_bytes']:,} | {ratio:.2f} | "
            f"**{s['leak_bytes']}** | {leaked_ids} | {s['trips_in_gold']} | {s['singleton_groups']} |"
        )

    lines += [
        "",
        "## Respuestas por endpoint",
        "",
        "| Sede | Endpoint | HTTP | Bytes | Filas | Campos no agregados |",
        "|---|---|---|---|---|---|",
    ]
    for site, s in traffic["sites"].items():
        for c in s["calls"]:
            lines.append(
                f"| {site} | `{c['path']}` | {c['status']} | {c['bytes']:,} | "
                f"{c['rows'] or '—'} | {', '.join(c['forbidden_fields']) or '—'} |"
            )
    for c in traffic["coordinator"]:
        lines.append(
            f"| coordinador | `{c['path']}` | {c['status']} | {c['bytes']:,} | "
            f"{c['rows'] or '—'} | {', '.join(c['forbidden_fields']) or '—'} |"
        )

    lines += [
        "",
        "## Superficie de exposición",
        "",
        "| Sede | Servicio | Puertos publicados | En pids-interconnect | Acceso a datos crudos | Valoración |",
        "|---|---|---|---|---|---|",
    ]
    for site, facts in exposure.items():
        for f in sorted(facts, key=lambda x: x["service"]):
            in_interconnect = any("interconnect" in n for n in f["networks"])
            lines.append(
                f"| {site} | {f['service']} | {', '.join(f['published_ports']) or '—'} | "
                f"{'sí' if in_interconnect else 'no'} | "
                f"{'sí' if f['service'] in RAW_CAPABLE_SERVICES else 'no'} | "
                f"{_verdict(f)} |"
            )
    lines += [
        "",
        "`producer` tiene acceso a los viajes, pero el puerto que publica solo sirve "
        "contadores de Prometheus. La única salida con datos no agregados es el puerto "
        "de Postgres (pendiente de decisión, #61).",
    ]
    return "\n".join(lines) + "\n"


def _verdict(fact: dict) -> str:
    service = fact["service"]
    if not fact["published_ports"]:
        return "interno"
    if service in INTERCONNECT_ALLOWED:
        return "OK: solo agregados"
    if service in METRICS_ONLY_PORTS and not (
        set(fact["published_container_ports"]) - METRICS_ONLY_PORTS[service]
    ):
        return "OK: solo métricas técnicas"
    if service in RAW_CAPABLE_SERVICES:
        return "⚠ expone datos no agregados"
    return "revisar"


@pytest.fixture(scope="module")
def m2_report(traffic, exposure):
    yield
    path = write_results(
        "m2_transfer", {"traffic": traffic, "exposure": exposure}, _markdown(traffic, exposure)
    )
    print(f"\nM2 results written to {path}")


@pytest.mark.integration
def test_m2_deployment_has_data(traffic, m2_report):
    """Without data in Gold, '0 raw bytes' would prove nothing."""
    empty = [site for site, s in traffic["sites"].items() if s["trips_in_gold"] == 0]
    assert not empty, (
        f"No trips in Gold for {empty}: run the full pipeline "
        "(make up-all-coordinators) and wait for data before measuring M2"
    )


@pytest.mark.integration
def test_m2_no_raw_bytes_leave_any_site(traffic, m2_report):
    for site, s in traffic["sites"].items():
        bad = [c for c in s["calls"] if c["leak_bytes"] or c["status"] >= 500]
        assert not bad, f"{site}: {bad}"
    bad = [c for c in traffic["coordinator"] if c["leak_bytes"] or c["status"] != 200]
    assert not bad, f"coordinator: {bad}"


@pytest.mark.integration
def test_m2_only_apis_join_the_shared_network(exposure, m2_report):
    for site, facts in exposure.items():
        assert facts, f"no containers found for compose project '{site}'"
        joined = {
            f["service"] for f in facts
            if any("interconnect" in n for n in f["networks"])
        }
        assert joined <= INTERCONNECT_ALLOWED, f"{site}: {sorted(joined)}"


@pytest.mark.integration
def test_m2_no_raw_capable_service_is_published(exposure, m2_report):
    offenders = set().union(*(_raw_exposures(f) for f in exposure.values()))
    unknown = offenders - KNOWN_EXPOSURES
    assert not unknown, f"services with raw data published on the host: {sorted(unknown)}"
    if offenders:
        pytest.xfail(KNOWN_EXPOSURE_REASON)
