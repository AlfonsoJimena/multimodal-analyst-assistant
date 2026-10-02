"""Cliente del coordinador de la parte 2, con failover.

Es lo UNICO del chatbot que habla con la parte 2 (lo fija ARQUITECTURA.md
de la parte 2). Cumple el contrato de `scripts/coordinator_failover.py`:

  - prueba las replicas en orden de failover (central -> chamartin -> atocha);
  - salta a la siguiente si no conecta, hay timeout o devuelve 5xx;
  - con 4xx NO reintenta (todas ejecutan el mismo codigo): es un error de
    parametros -> CoordinatorParamError;
  - si sites_ok viene vacio, lo trata como «sin datos», no como exito;
  - si no responde ninguna replica -> CoordinatorUnavailable;
  - el timeout (10 s por defecto) es MAYOR que los 5 s que el coordinador
    espera a cada sede, para no descartar respuestas parciales (fallo S4 de M1).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from ..agent.config import get_config


class CoordinatorUnavailable(Exception):
    """Ninguna replica del coordinador respondio."""


class CoordinatorParamError(Exception):
    """El coordinador devolvio un 4xx (error de parametros); no se hace failover."""


@dataclass
class CoordinatorResult:
    """Respuesta del coordinador mas trazabilidad."""

    served_by: str
    skipped: list[str]
    latency_ms: int
    sites_ok: list[str]
    sites_failed: list[str]
    partial: bool
    data: list[dict] = field(default_factory=list)

    @property
    def no_data(self) -> bool:
        """True si ninguna sede aporto datos (sites_ok vacio)."""
        return not self.sites_ok


def _fmt(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class CoordinatorClient:
    def __init__(self, urls: Optional[list[str]] = None,
                 timeout_s: Optional[float] = None,
                 transport: Optional[httpx.BaseTransport] = None):
        config = get_config()
        self.urls = urls if urls is not None else config.coordinator_urls
        self.timeout_s = timeout_s if timeout_s is not None else config.coordinator_timeout_s
        self._transport = transport

    # ---- HTTP con failover ----

    def _request(self, path: str, params: dict) -> tuple[str, httpx.Response, list[str], int]:
        skipped: list[str] = []
        start = time.monotonic()

        for url in self.urls:
            try:
                with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
                    response = client.get(f"{url}{path}", params=params)
            except httpx.HTTPError as error:
                skipped.append(f"{url}: {type(error).__name__}")
                continue

            if response.status_code >= 500:
                skipped.append(f"{url}: HTTP {response.status_code}")
                continue

            if response.status_code >= 400:
                # 4xx: error de parametros, no se reintenta en las demas.
                raise CoordinatorParamError(
                    f"HTTP {response.status_code} en {url}: {response.text[:200]}"
                )

            latency_ms = int((time.monotonic() - start) * 1000)
            return url, response, skipped, latency_ms

        raise CoordinatorUnavailable(
            "Ninguna replica respondio: " + ("; ".join(skipped) or "sin replicas")
        )

    def _metrics(self, path: str, params: dict) -> CoordinatorResult:
        clean = {k: v for k, v in params.items() if v is not None}
        url, response, skipped, latency_ms = self._request(path, clean)
        body = response.json()
        return CoordinatorResult(
            served_by=url,
            skipped=skipped,
            latency_ms=latency_ms,
            sites_ok=body.get("sites_ok", []),
            sites_failed=body.get("sites_failed", []),
            partial=body.get("partial", False),
            data=body.get("data", []),
        )

    # ---- Metodos tipados ----

    def hourly(self, date_from=None, date_to=None, breakdown: str = "none") -> CoordinatorResult:
        return self._metrics("/metrics/hourly", {
            "date_from": _fmt(date_from), "date_to": _fmt(date_to), "breakdown": breakdown,
        })

    def daily(self, date_from=None, date_to=None, breakdown: str = "none") -> CoordinatorResult:
        return self._metrics("/metrics/daily", {
            "date_from": _fmt(date_from), "date_to": _fmt(date_to), "breakdown": breakdown,
        })

    def zone(self, pu_location_id=None, breakdown: str = "none") -> CoordinatorResult:
        return self._metrics("/metrics/zone", {
            "pu_location_id": pu_location_id, "breakdown": breakdown,
        })

    def payment(self, payment_type=None, breakdown: str = "none") -> CoordinatorResult:
        return self._metrics("/metrics/payment", {
            "payment_type": payment_type, "breakdown": breakdown,
        })

    def health_all(self) -> list[dict]:
        """Consulta /health de cada replica por separado (sin failover)."""
        out = []
        for url in self.urls:
            try:
                with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
                    response = client.get(f"{url}/health")
            except httpx.HTTPError as error:
                out.append({"url": url, "ok": False, "error": type(error).__name__})
                continue
            if response.status_code == 200:
                body = response.json()
                out.append({
                    "url": url, "ok": True,
                    "site_id": body.get("site_id"),
                    "failover_priority": body.get("failover_priority"),
                })
            else:
                out.append({"url": url, "ok": False, "error": f"HTTP {response.status_code}"})
        return out
