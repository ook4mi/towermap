"""Nginx Proxy Manager REST API collector with in-memory JWT caching."""

import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.models import NpmProxyHost

logger = logging.getLogger(__name__)


class NpmCollector:
    """Fetches proxy host rules from Nginx Proxy Manager."""

    def __init__(
        self,
        base_url: str | None,
        identity: str | None = None,
        secret: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._identity = identity or None
        self._secret = secret or None
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._identity and self._secret)

    def _has_valid_token(self) -> bool:
        if not self._token or not self._token_expires_at:
            return False
        # Refresh 60 seconds early to avoid race conditions
        return datetime.now(UTC) + timedelta(seconds=60) < self._token_expires_at

    async def _authenticate(self, http_client: httpx.AsyncClient) -> str:
        assert self._base_url and self._identity and self._secret
        resp = await http_client.post(
            f"{self._base_url}/api/tokens",
            json={"identity": self._identity, "secret": self._secret},
        )
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("token")
        if not token:
            raise ValueError("NPM /api/tokens response missing 'token'")

        expires_raw = payload.get("expires")
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        if isinstance(expires_raw, str):
            normalized = expires_raw[:-1] + "+00:00" if expires_raw.endswith("Z") else expires_raw
            try:
                expires_at = datetime.fromisoformat(normalized)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
            except ValueError:
                pass

        self._token = token
        self._token_expires_at = expires_at
        return token

    async def fetch_proxy_hosts(
        self, client: httpx.AsyncClient | None = None
    ) -> tuple[list[NpmProxyHost], str]:
        """Return (proxy_hosts, integration_status) where status is ok|unconfigured|error."""
        if not self.is_configured:
            return [], "unconfigured"

        assert self._base_url is not None
        owns_client = client is None
        http_client = client or httpx.AsyncClient(timeout=self._timeout)

        try:
            token = (
                self._token
                if self._has_valid_token()
                else await self._authenticate(http_client)
            )
            resp = await http_client.get(
                f"{self._base_url}/api/nginx/proxy-hosts",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 401:
                self._token = None
                token = await self._authenticate(http_client)
                resp = await http_client.get(
                    f"{self._base_url}/api/nginx/proxy-hosts",
                    headers={"Authorization": f"Bearer {token}"},
                )
            resp.raise_for_status()
            items = resp.json()
            hosts: list[NpmProxyHost] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                domain_names = [
                    str(d).strip().lower()
                    for d in (item.get("domain_names") or [])
                    if str(d).strip()
                ]
                forward_host = str(item.get("forward_host") or "").strip()
                try:
                    forward_port = int(item.get("forward_port") or 0)
                except (TypeError, ValueError):
                    forward_port = 0
                if not domain_names or not forward_host:
                    continue
                cert_id = item.get("certificate_id")
                ssl_enabled = bool(cert_id and str(cert_id) != "0")
                hosts.append(
                    NpmProxyHost(
                        domain_names=domain_names,
                        forward_scheme=str(item.get("forward_scheme") or "http"),
                        forward_host=forward_host,
                        forward_port=forward_port,
                        ssl_enabled=ssl_enabled,
                        enabled=bool(item.get("enabled", True)),
                    )
                )
            return hosts, "ok"
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("NPM collector failed (%s): %s", self._base_url, exc)
            return [], "error"
        finally:
            if owns_client:
                await http_client.aclose()
