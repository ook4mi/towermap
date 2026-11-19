"""Unit tests for Gluetun VPN collector and blast-radius correlation."""

import httpx
import pytest

from app.collectors.gluetun_collector import GluetunCollector, build_gluetun_overview
from app.models import ContainerInfo


def test_build_gluetun_overview_detects_stale_id_and_earlier_start() -> None:
    current_gluetun_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    stale_gluetun_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    containers = [
        ContainerInfo(
            id=current_gluetun_id[:12],
            name="gluetun",
            image="qmcgaw/gluetun:latest",
            stack_name="media-vpn",
            state="running",
            health="healthy",
            started_at="2026-11-18T10:00:00Z",
            network_mode="media-vpn_default",
        ),
        ContainerInfo(
            id="c1",
            name="sonarr",
            image="lscr.io/linuxserver/sonarr",
            stack_name="media-vpn",
            state="running",
            health="healthy",
            started_at="2026-11-18T10:00:15Z",
            network_mode=f"container:{current_gluetun_id}",
            gluetun_attached=True,
        ),
        ContainerInfo(
            id="c2",
            name="radarr",
            image="lscr.io/linuxserver/radarr",
            stack_name="media-vpn",
            state="running",
            health="unhealthy",
            started_at="2026-11-17T08:00:00Z",
            network_mode=f"container:{stale_gluetun_id}",
            gluetun_attached=True,
        ),
    ]

    overview = build_gluetun_overview(
        containers,
        gluetun_full_id=current_gluetun_id,
        vpn_data={
            "vpn_status": "running",
            "public_ip": "185.220.101.42",
            "country": "Switzerland",
        },
        configured=True,
        reachable=True,
    )

    assert overview.container_state == "running"
    assert overview.vpn_status == "running"
    assert overview.public_ip == "185.220.101.42"
    assert len(overview.attached_containers) == 2
    assert any("stale gluetun container ID" in w for w in overview.warnings)
    assert any("started before gluetun's last restart" in w for w in overview.warnings)
    assert any("unhealthy" in w for w in overview.warnings)


def test_build_gluetun_overview_warns_when_api_unreachable() -> None:
    overview = build_gluetun_overview(
        [],
        configured=True,
        reachable=False,
        api_error="Connection refused",
    )
    assert overview.container_state == "not_found"
    assert overview.reachable is False
    assert any("Connection refused" in w for w in overview.warnings)


@pytest.mark.asyncio
async def test_gluetun_collector_fetches_status_and_public_ip() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-API-Key") == "secret-key"
        if request.url.path == "/v1/vpn/status":
            return httpx.Response(200, json={"status": "running"})
        if request.url.path == "/v1/publicip/ip":
            return httpx.Response(
                200,
                json={
                    "public_ip": "198.51.100.10",
                    "country": "Netherlands",
                    "region": "North Holland",
                    "organization": "ProtonVPN",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    collector = GluetunCollector(
        base_url="http://192.168.68.62:8000",
        api_key="secret-key",
    )

    async with httpx.AsyncClient(transport=transport) as client:
        data, reachable, error = await collector.fetch_status(client=client)

    assert reachable is True
    assert error is None
    assert data is not None
    assert data["vpn_status"] == "running"
    assert data["public_ip"] == "198.51.100.10"
    assert data["country"] == "Netherlands"


@pytest.mark.asyncio
async def test_gluetun_collector_handles_connection_error_gracefully() -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    transport = httpx.MockTransport(failing_handler)
    collector = GluetunCollector(base_url="http://192.168.68.62:8000")

    async with httpx.AsyncClient(transport=transport) as client:
        data, reachable, error = await collector.fetch_status(client=client)

    assert data is None
    assert reachable is False
    assert error is not None
    assert "unreachable" in error.lower()
