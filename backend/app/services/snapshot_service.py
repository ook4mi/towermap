"""Orchestrates data collectors, TTL caching, and summary computation."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from app.cache import TTLCache
from app.collectors.dns_collector import DnsCollector
from app.collectors.docker_collector import DockerCollector
from app.collectors.gluetun_collector import GluetunCollector, build_gluetun_overview
from app.collectors.mock_data import (
    MOCK_GLUETUN_FULL_ID,
    get_mock_containers,
    get_mock_dns_records,
    get_mock_gluetun_api_data,
    get_mock_npm_proxy_hosts,
)
from app.collectors.npm_collector import NpmCollector
from app.config import Settings
from app.models import (
    ContainerInfo,
    GluetunOverview,
    IntegrationStatus,
    OverviewResponse,
    PortBinding,
    RouteEntry,
)
from app.services.port_service import extract_ports
from app.services.route_service import correlate_routes

SNAPSHOT_CACHE_KEY = "towermap_snapshot"


@dataclass
class TowerSnapshot:
    containers: list[ContainerInfo]
    ports: list[PortBinding]
    gluetun: GluetunOverview
    routes: list[RouteEntry]
    integrations: IntegrationStatus
    collected_at: str


class SnapshotService:
    """Fetches and caches unified TowerMap snapshots across all integrations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: TTLCache[TowerSnapshot] = TTLCache(
            ttl_seconds=settings.cache_ttl_seconds
        )
        self._docker_collector = DockerCollector(docker_host=settings.docker_host)
        self._gluetun_collector = GluetunCollector(
            base_url=settings.gluetun_url,
            api_key=settings.gluetun_api_key,
            timeout=settings.http_timeout_seconds,
        )
        self._npm_collector = NpmCollector(
            base_url=settings.npm_url,
            identity=settings.npm_identity,
            secret=settings.npm_secret,
            timeout=settings.http_timeout_seconds,
        )
        self._dns_collector = DnsCollector(
            base_url=settings.technitium_url,
            api_token=settings.technitium_api_token,
            zone_domain=settings.default_domain,
            timeout=settings.http_timeout_seconds,
        )

    @property
    def settings(self) -> Settings:
        return self._settings

    async def get_snapshot(self, *, force_refresh: bool = False) -> TowerSnapshot:
        if force_refresh:
            self._cache.invalidate(SNAPSHOT_CACHE_KEY)
        return await self._cache.get_or_load(SNAPSHOT_CACHE_KEY, self._collect_snapshot)

    def invalidate_cache(self) -> None:
        self._cache.invalidate()

    async def _collect_snapshot(self) -> TowerSnapshot:
        now_iso = datetime.now(UTC).isoformat()

        if self._settings.mock_mode:
            containers = get_mock_containers()
            gluetun_api_data = get_mock_gluetun_api_data()
            gluetun = build_gluetun_overview(
                containers,
                gluetun_full_id=MOCK_GLUETUN_FULL_ID,
                vpn_data=gluetun_api_data,
                configured=True,
                reachable=True,
            )
            dns_records = get_mock_dns_records(self._settings.default_domain)
            npm_hosts = get_mock_npm_proxy_hosts(self._settings.default_domain)
            routes = correlate_routes(
                dns_records,
                npm_hosts,
                containers,
                tower_hosts=self._settings.tower_hosts,
                default_domain=self._settings.default_domain,
            )
            ports = extract_ports(containers)
            integrations = IntegrationStatus(
                docker="mock",
                gluetun="mock",
                npm="mock",
                dns="mock",
            )
            return TowerSnapshot(
                containers=containers,
                ports=ports,
                gluetun=gluetun,
                routes=routes,
                integrations=integrations,
                collected_at=now_iso,
            )

        # Live mode: run collectors concurrently and degrade gracefully on optional ones
        docker_status = "ok"
        try:
            docker_result, gluetun_result, npm_result, dns_result = await asyncio.gather(
                self._docker_collector.collect(),
                self._gluetun_collector.fetch_status(),
                self._npm_collector.fetch_proxy_hosts(),
                self._dns_collector.fetch_records(),
                return_exceptions=True,
            )
        except Exception:
            docker_result = ([], None)
            gluetun_result = (None, False, "Unexpected collector error")
            npm_result = ([], "error")
            dns_result = ([], "error")

        if isinstance(docker_result, BaseException):
            docker_status = "error"
            containers, gluetun_full_id = [], None
        else:
            containers, gluetun_full_id = docker_result

        if isinstance(gluetun_result, BaseException):
            vpn_data, gluetun_reachable, gluetun_err = None, False, str(gluetun_result)
        else:
            vpn_data, gluetun_reachable, gluetun_err = gluetun_result

        if isinstance(npm_result, BaseException):
            npm_hosts, npm_status = [], "error"
        else:
            npm_hosts, npm_status = npm_result

        if isinstance(dns_result, BaseException):
            dns_records, dns_status = [], "error"
        else:
            dns_records, dns_status = dns_result

        gluetun_configured = self._gluetun_collector.is_configured
        if not gluetun_configured:
            gluetun_status = "unconfigured"
        elif gluetun_reachable:
            gluetun_status = "ok"
        else:
            gluetun_status = "error"

        gluetun = build_gluetun_overview(
            containers,
            gluetun_full_id=gluetun_full_id,
            vpn_data=vpn_data,
            configured=gluetun_configured,
            reachable=gluetun_reachable,
            api_error=gluetun_err,
        )
        routes = correlate_routes(
            dns_records,
            npm_hosts,
            containers,
            tower_hosts=self._settings.tower_hosts,
            default_domain=self._settings.default_domain,
        )
        ports = extract_ports(containers)
        integrations = IntegrationStatus(
            docker=docker_status,
            gluetun=gluetun_status,
            npm=npm_status,
            dns=dns_status,
        )
        return TowerSnapshot(
            containers=containers,
            ports=ports,
            gluetun=gluetun,
            routes=routes,
            integrations=integrations,
            collected_at=now_iso,
        )

    async def get_overview(self) -> OverviewResponse:
        snapshot = await self.get_snapshot()
        stacks = {c.stack_name or "standalone" for c in snapshot.containers}
        running = sum(1 for c in snapshot.containers if c.state == "running")
        stopped = len(snapshot.containers) - running
        unhealthy = sum(1 for c in snapshot.containers if c.health == "unhealthy")
        route_alerts = sum(
            1
            for r in snapshot.routes
            if r.status in {"orphan_dns", "orphan_proxy", "target_down"}
        )
        gluetun_warnings = len(snapshot.gluetun.warnings)
        active_alerts = route_alerts + gluetun_warnings

        mode: str = "mock" if self._settings.mock_mode else "live"
        return OverviewResponse(
            mode=mode,  # type: ignore[arg-type]
            total_stacks=len(stacks),
            total_containers=len(snapshot.containers),
            running_containers=running,
            stopped_containers=stopped,
            unhealthy_containers=unhealthy,
            used_ports_count=len(snapshot.ports),
            gluetun_attached_count=len(snapshot.gluetun.attached_containers),
            gluetun_vpn_status=snapshot.gluetun.vpn_status,
            gluetun_public_ip=snapshot.gluetun.public_ip,
            gluetun_country=snapshot.gluetun.country,
            gluetun_warnings_count=gluetun_warnings,
            routes_total=len(snapshot.routes),
            route_alerts_count=route_alerts,
            active_alerts=active_alerts,
            last_updated=snapshot.collected_at,
            integrations=snapshot.integrations,
        )
