"""TowerMap /api/* JSON endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request

from app.models import (
    ContainerInfo,
    GluetunOverview,
    HealthResponse,
    OverviewResponse,
    PortBinding,
    PortCheckResponse,
    RefreshResponse,
    RouteEntry,
)
from app.services.port_service import check_port_availability, extract_ports
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api", tags=["towermap"])


def get_snapshot_service(request: Request) -> SnapshotService:
    """Retrieve the app-scoped SnapshotService."""
    return request.app.state.snapshot_service


SnapshotServiceDep = Annotated[SnapshotService, Depends(get_snapshot_service)]


@router.get("/health", response_model=HealthResponse)
async def get_health(service: SnapshotServiceDep) -> HealthResponse:
    mode: Literal["mock", "live"] = "mock" if service.settings.mock_mode else "live"
    return HealthResponse(status="ok", mode=mode)


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(service: SnapshotServiceDep) -> OverviewResponse:
    return await service.get_overview()


@router.get("/containers", response_model=list[ContainerInfo])
async def get_containers(
    service: SnapshotServiceDep,
    stack: Annotated[
        str | None, Query(description="Filter by Compose stack name")
    ] = None,
    state: Annotated[
        str | None, Query(description="Filter by container state")
    ] = None,
    gluetun_only: Annotated[
        bool, Query(description="Only return containers attached to gluetun")
    ] = False,
    q: Annotated[str | None, Query(description="Free-text search query")] = None,
) -> list[ContainerInfo]:
    snapshot = await service.get_snapshot()
    results = snapshot.containers

    if stack:
        stack_lower = stack.strip().lower()
        results = [
            c
            for c in results
            if (c.stack_name or "standalone").lower() == stack_lower
        ]

    if state:
        state_lower = state.strip().lower()
        results = [c for c in results if c.state.lower() == state_lower]

    if gluetun_only:
        results = [c for c in results if c.gluetun_attached]

    if q:
        needle = q.strip().lower()
        results = [
            c
            for c in results
            if needle in c.name.lower()
            or needle in c.image.lower()
            or needle in (c.stack_name or "").lower()
            or needle in (c.service_name or "").lower()
            or needle in c.id.lower()
            or any(needle in str(p.host_port) for p in c.ports)
        ]

    return results


@router.get("/ports", response_model=list[PortBinding])
async def get_ports(
    service: SnapshotServiceDep,
    protocol: Annotated[
        Literal["tcp", "udp"] | None,
        Query(description="Filter by protocol (tcp or udp)"),
    ] = None,
    q: Annotated[
        str | None, Query(description="Search by port, container, or stack")
    ] = None,
) -> list[PortBinding]:
    snapshot = await service.get_snapshot()
    return extract_ports(snapshot.containers, protocol=protocol, query=q)


@router.get("/ports/check", response_model=PortCheckResponse)
async def check_port(
    service: SnapshotServiceDep,
    port: Annotated[
        int, Query(ge=1, le=65535, description="Host port number to check")
    ],
) -> PortCheckResponse:
    snapshot = await service.get_snapshot()
    return check_port_availability(
        port,
        snapshot.ports,
        suggest_start=service.settings.suggest_port_start,
        suggest_end=service.settings.suggest_port_end,
    )


@router.get("/gluetun", response_model=GluetunOverview)
async def get_gluetun(service: SnapshotServiceDep) -> GluetunOverview:
    snapshot = await service.get_snapshot()
    return snapshot.gluetun


@router.get("/routes", response_model=list[RouteEntry])
async def get_routes(
    service: SnapshotServiceDep,
    status: Annotated[
        str | None, Query(description="Filter by route status")
    ] = None,
    q: Annotated[
        str | None, Query(description="Search by domain, target, or container")
    ] = None,
) -> list[RouteEntry]:
    snapshot = await service.get_snapshot()
    results = snapshot.routes

    if status:
        status_lower = status.strip().lower()
        results = [r for r in results if r.status.lower() == status_lower]

    if q:
        needle = q.strip().lower()
        results = [
            r
            for r in results
            if needle in r.domain.lower()
            or needle in (r.dns_target or "").lower()
            or needle in (r.proxy_target or "").lower()
            or needle in (r.matched_container or "").lower()
        ]

    return results


@router.post("/cache/refresh", response_model=RefreshResponse)
async def refresh_cache(service: SnapshotServiceDep) -> RefreshResponse:
    snapshot = await service.get_snapshot(force_refresh=True)
    return RefreshResponse(status="ok", refreshed_at=snapshot.collected_at)
