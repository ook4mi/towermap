"""Technitium DNS Server REST API collector."""

import logging

import httpx

from app.models import DnsRecord

logger = logging.getLogger(__name__)

SUPPORTED_RECORD_TYPES = {"A", "AAAA", "CNAME"}


class DnsCollector:
    """Fetches A, AAAA, and CNAME records from Technitium DNS."""

    def __init__(
        self,
        base_url: str | None,
        api_token: str | None = None,
        zone_domain: str = "ook4mi.ovh",
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._api_token = api_token or None
        self._zone_domain = zone_domain.strip().lower()
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_token)

    async def fetch_records(
        self, client: httpx.AsyncClient | None = None
    ) -> tuple[list[DnsRecord], str]:
        """Return (dns_records, integration_status) where status is ok|unconfigured|error."""
        if not self.is_configured:
            return [], "unconfigured"

        assert self._base_url and self._api_token
        owns_client = client is None
        http_client = client or httpx.AsyncClient(timeout=self._timeout)

        try:
            resp = await http_client.get(
                f"{self._base_url}/api/zones/records/get",
                params={
                    "token": self._api_token,
                    "domain": self._zone_domain,
                    "listZone": "true",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("status") != "ok":
                error_msg = payload.get("errorMessage") or "unknown Technitium API error"
                raise ValueError(error_msg)

            raw_records = (payload.get("response") or {}).get("records") or []
            records: list[DnsRecord] = []
            for item in raw_records:
                if not isinstance(item, dict):
                    continue
                if item.get("disabled"):
                    continue
                record_type = str(item.get("type") or "").upper()
                if record_type not in SUPPORTED_RECORD_TYPES:
                    continue
                name = str(item.get("name") or "").strip().lower().rstrip(".")
                r_data = item.get("rData") or {}
                target = str(
                    r_data.get("ipAddress")
                    or r_data.get("cname")
                    or r_data.get("value")
                    or ""
                ).strip().rstrip(".")
                if not name or not target:
                    continue
                records.append(
                    DnsRecord(
                        domain=name,
                        record_type=record_type,
                        target=target,
                    )
                )

            return records, "ok"
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Technitium DNS collector failed (%s): %s", self._base_url, exc)
            return [], "error"
        finally:
            if owns_client:
                await http_client.aclose()
