"""Integration tests for TowerMap FastAPI endpoints in mock mode."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _make_client() -> TestClient:
    settings = Settings(
        mock_mode=True,
        cache_ttl_seconds=15,
        default_domain="ook4mi.ovh",
        suggest_port_start=4010,
        suggest_port_end=4099,
    )
    app = create_app(settings=settings)
    return TestClient(app)


def test_health_endpoint() -> None:
    client = _make_client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "mode": "mock"}


def test_overview_endpoint() -> None:
    client = _make_client()
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "mock"
    assert data["total_stacks"] >= 5
    assert data["total_containers"] > 10
    assert data["gluetun_vpn_status"] == "running"
    assert data["gluetun_public_ip"] == "185.220.101.42"
    assert data["route_alerts_count"] >= 3


def test_containers_endpoint_filters() -> None:
    client = _make_client()

    all_resp = client.get("/api/containers")
    assert all_resp.status_code == 200
    all_containers = all_resp.json()
    assert len(all_containers) > 10

    gluetun_resp = client.get("/api/containers", params={"gluetun_only": "true"})
    assert gluetun_resp.status_code == 200
    gluetun_containers = gluetun_resp.json()
    assert len(gluetun_containers) >= 5
    assert all(c["gluetun_attached"] is True for c in gluetun_containers)

    exited_resp = client.get("/api/containers", params={"state": "exited"})
    assert exited_resp.status_code == 200
    assert any(c["name"] == "paperless-ngx" for c in exited_resp.json())

    search_resp = client.get("/api/containers", params={"q": "sonarr"})
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["name"] == "sonarr"


def test_ports_and_port_check_endpoints() -> None:
    client = _make_client()

    ports_resp = client.get("/api/ports")
    assert ports_resp.status_code == 200
    ports = ports_resp.json()
    assert len(ports) > 10
    host_ports = [p["host_port"] for p in ports]
    assert host_ports == sorted(host_ports)

    udp_resp = client.get("/api/ports", params={"protocol": "udp"})
    assert udp_resp.status_code == 200
    assert all(p["protocol"] == "udp" for p in udp_resp.json())

    used_check = client.get("/api/ports/check", params={"port": 4010})
    assert used_check.status_code == 200
    used_data = used_check.json()
    assert used_data["available"] is False
    assert used_data["conflicts"][0]["container_name"] == "towermap"
    assert used_data["next_free_port"] == 4013

    free_check = client.get("/api/ports/check", params={"port": 4050})
    assert free_check.status_code == 200
    assert free_check.json()["available"] is True

    invalid_check = client.get("/api/ports/check", params={"port": 70000})
    assert invalid_check.status_code == 422


def test_gluetun_routes_and_cache_refresh_endpoints() -> None:
    client = _make_client()

    gluetun_resp = client.get("/api/gluetun")
    assert gluetun_resp.status_code == 200
    gluetun = gluetun_resp.json()
    assert gluetun["vpn_status"] == "running"
    assert len(gluetun["attached_containers"]) >= 5
    assert len(gluetun["warnings"]) >= 1

    routes_resp = client.get("/api/routes")
    assert routes_resp.status_code == 200
    statuses = {r["status"] for r in routes_resp.json()}
    assert {"ok", "orphan_dns", "orphan_proxy", "target_down", "external"}.issubset(statuses)

    refresh_resp = client.post("/api/cache/refresh")
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["status"] == "ok"
