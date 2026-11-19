"""Gluetun Control Server collector and VPN dependency correlation."""

import logging
from datetime import datetime

import httpx

from app.collectors.docker_collector import is_gluetun_container
from app.models import ContainerInfo, GluetunOverview

logger = logging.getLogger(__name__)


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    if not ts:
        return None
    normalized = ts.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def build_gluetun_overview(
    containers: list[ContainerInfo],
    *,
    gluetun_full_id: str | None = None,
    vpn_data: dict[str, str | None] | None = None,
    configured: bool = False,
    reachable: bool = False,
    api_error: str | None = None,
) -> GluetunOverview:
    """Correlate Docker's gluetun container, attached containers, and Gluetun API state."""
    gluetun_container = next(
        (
            c
            for c in containers
            if is_gluetun_container(c.name, c.image, c.service_name)
        ),
        None,
    )
    attached = [c for c in containers if c.gluetun_attached]
    warnings: list[str] = []

    if gluetun_container is None:
        container_state = "not_found"
        if attached:
            warnings.append(
                f"{len(attached)} container(s) reference gluetun, "
                "but no gluetun container was found."
            )
    else:
        container_state = gluetun_container.state
        if container_state != "running":
            warnings.append(
                f"gluetun container is '{container_state}' — "
                f"{len(attached)} attached container(s) have no VPN network."
            )
        elif gluetun_container.health == "unhealthy":
            warnings.append("gluetun container healthcheck is reporting 'unhealthy'.")

    vpn_status = vpn_data.get("vpn_status") if vpn_data else None
    public_ip = vpn_data.get("public_ip") if vpn_data else None
    country = vpn_data.get("country") if vpn_data else None
    region = vpn_data.get("region") if vpn_data else None
    organization = vpn_data.get("organization") if vpn_data else None

    if configured and not reachable:
        warnings.append(api_error or "Gluetun Control API is unreachable.")
    elif vpn_status and vpn_status.lower() != "running":
        warnings.append(f"Gluetun VPN tunnel status is '{vpn_status}'.")

    gluetun_started_dt = _parse_iso_timestamp(
        gluetun_container.started_at if gluetun_container else None
    )

    for container in attached:
        # 1. Stale container ID detection
        if container.network_mode.lower().startswith("container:") and gluetun_container:
            target = container.network_mode.split(":", 1)[1].strip()
            expected_ids = {
                gluetun_container.id,
                gluetun_container.name,
            }
            if gluetun_full_id:
                expected_ids.add(gluetun_full_id)
            matches_current = (
                target in expected_ids
                or (gluetun_full_id is not None and gluetun_full_id.startswith(target))
            )
            if not matches_current:
                warnings.append(
                    f"'{container.name}' references a stale gluetun container ID "
                    f"({target[:12]}) and must be recreated."
                )

        # 2. Started before gluetun restarted
        container_started_dt = _parse_iso_timestamp(container.started_at)
        if (
            container.state == "running"
            and gluetun_started_dt is not None
            and container_started_dt is not None
            and container_started_dt < gluetun_started_dt
        ):
            warnings.append(
                f"'{container.name}' started before gluetun's last restart — "
                "recreate it if network connectivity was lost."
            )

        # 3. Attached container health/state issues
        if container.state != "running":
            warnings.append(
                f"Attached container '{container.name}' is currently '{container.state}'."
            )
        elif container.health == "unhealthy":
            warnings.append(
                f"Attached container '{container.name}' is unhealthy."
            )

    published_ports = list(gluetun_container.ports) if gluetun_container else []
    for c in attached:
        published_ports.extend(c.ports)
    published_ports.sort(key=lambda item: (item.host_port, item.protocol))

    return GluetunOverview(
        container_state=container_state,
        container_id=gluetun_container.id if gluetun_container else None,
        started_at=gluetun_container.started_at if gluetun_container else None,
        vpn_status=vpn_status,
        public_ip=public_ip,
        country=country,
        region=region,
        organization=organization,
        configured=configured,
        reachable=reachable,
        attached_containers=attached,
        published_ports=published_ports,
        warnings=warnings,
    )


class GluetunCollector:
    """Async client for the Gluetun HTTP Control Server."""

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._api_key = api_key or None
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url)

    async def fetch_status(
        self, client: httpx.AsyncClient | None = None
    ) -> tuple[dict[str, str | None] | None, bool, str | None]:
        """Return (vpn_data, reachable, error_message)."""
        if not self._base_url:
            return None, False, None

        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key

        owns_client = client is None
        http_client = client or httpx.AsyncClient(timeout=self._timeout)

        try:
            status_resp = await http_client.get(
                f"{self._base_url}/v1/vpn/status",
                headers=headers,
            )
            status_resp.raise_for_status()
            status_payload = status_resp.json()
            vpn_status = status_payload.get("status")

            ip_payload: dict[str, str | None] = {}
            try:
                ip_resp = await http_client.get(
                    f"{self._base_url}/v1/publicip/ip",
                    headers=headers,
                )
                ip_resp.raise_for_status()
                ip_payload = ip_resp.json()
            except httpx.HTTPError as exc:
                logger.warning("Gluetun public IP endpoint failed: %s", exc)

            data: dict[str, str | None] = {
                "vpn_status": vpn_status,
                "public_ip": ip_payload.get("public_ip"),
                "country": ip_payload.get("country"),
                "region": ip_payload.get("region"),
                "organization": ip_payload.get("organization"),
            }
            return data, True, None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Gluetun Control API unreachable (%s): %s", self._base_url, exc)
            return None, False, f"Gluetun Control API unreachable: {exc}"
        finally:
            if owns_client:
                await http_client.aclose()
