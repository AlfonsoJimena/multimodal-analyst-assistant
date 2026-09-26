"""
HTTP clients for calling the 3 site_api instances from the coordinator.

Every call goes through fetch_all_sites(), which runs the 3 requests
CONCURRENTLY (asyncio.gather) and gives each one its own timeout and
its own try/except. Without a timeout, a single down/unresponsive
site would hang the coordinator's response indefinitely; without
catching each site's failure independently, one bad site would take
the other two down with it. Neither ever happens here: a failure
becomes a SiteResult(ok=False), never an exception that propagates
out of fetch_all_sites.
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from src.common.schema import VALID_SITE_IDS


# ============================================================
# Configuration
# ============================================================

SITE_API_TIMEOUT_SECONDS = float(os.getenv("SITE_API_TIMEOUT_SECONDS", "5"))

# Placeholder hostnames until deploy/docker-compose.site.yml names the
# real per-site services -- override with SITE_API_URL_<SITE> once it
# does (e.g. SITE_API_URL_CENTRAL=http://central-site-api:8000).
SITE_API_URLS = {
    site_id: os.getenv(
        f"SITE_API_URL_{site_id.upper()}",
        f"http://site-api-{site_id}:8000",
    )
    for site_id in VALID_SITE_IDS
}


# ============================================================
# Configuration validation
# ============================================================

def validate_configuration() -> None:
    if SITE_API_TIMEOUT_SECONDS <= 0:
        raise ValueError(
            "SITE_API_TIMEOUT_SECONDS must be greater than 0."
        )


# ============================================================
# Result type
# ============================================================

@dataclass
class SiteResult:
    site_id: str
    ok: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ============================================================
# HTTP calls
# ============================================================

async def fetch_site(site_id: str, path: str, params: dict) -> SiteResult:
    url = f"{SITE_API_URLS[site_id]}{path}"

    try:
        async with httpx.AsyncClient(timeout=SITE_API_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return SiteResult(site_id=site_id, ok=True, data=response.json())
    except httpx.HTTPError as error:
        return SiteResult(site_id=site_id, ok=False, error=str(error))


async def fetch_all_sites(path: str, params: dict) -> list[SiteResult]:
    tasks = [
        fetch_site(site_id, path, params) for site_id in sorted(VALID_SITE_IDS)
    ]
    return await asyncio.gather(*tasks)
