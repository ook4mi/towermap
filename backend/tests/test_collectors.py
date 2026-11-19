"""Unit tests for NPM and Technitium DNS collectors including graceful degradation."""

import httpx
import pytest

from app.collectors.dns_collector import DnsCollector
from app.collectors.npm_collector import NpmCollector


@pytest.mark.asyncio
async def test_npm_collector_authenticates_and_parses_proxy_hosts() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path == "/api/tokens":
            token_calls += 1
            return httpx.Response(
                200,
                json={"token": "jwt-123", "expires": "2099-01-01T00:00:00Z"},
            )
        if request.url.path == "/api/nginx/proxy-hosts":
            assert request.headers.get("Authorization") == "Bearer jwt-123"
            return httpx.Response(
                200,
                json=[
                    {
                        "domain_names": ["sonarr.ook4mi.ovh"],
                        "forward_scheme": "http",
                        "forward_host": "192.168.68.62",
                        "forward_port": 8989,
                        "certificate_id": 4,
                        "enabled": True,
                    }
                ],
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    collector = NpmCollector(
        base_url="http://192.168.68.62:81",
        identity="admin@example.com",
        secret="password",
    )

    async with httpx.AsyncClient(transport=transport) as client:
        hosts, status = await collector.fetch_proxy_hosts(client=client)
        # Second call should reuse cached JWT
        hosts_again, status_again = await collector.fetch_proxy_hosts(client=client)

    assert status == "ok"
    assert status_again == "ok"
    assert token_calls == 1
    assert len(hosts) == 1
    assert len(hosts_again) == 1
    assert hosts[0].domain_names == ["sonarr.ook4mi.ovh"]
    assert hosts[0].ssl_enabled is True


@pytest.mark.asyncio
async def test_npm_collector_returns_unconfigured_without_credentials() -> None:
    collector = NpmCollector(base_url="http://192.168.68.62:81")
    hosts, status = await collector.fetch_proxy_hosts()
    assert hosts == []
    assert status == "unconfigured"


@pytest.mark.asyncio
async def test_dns_collector_parses_a_aaaa_cname_records() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/zones/records/get"
        assert request.url.params.get("token") == "tok-123"
        assert request.url.params.get("domain") == "ook4mi.ovh"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "response": {
                    "records": [
                        {
                            "name": "sonarr.ook4mi.ovh",
                            "type": "A",
                            "rData": {"ipAddress": "192.168.68.62"},
                        },
                        {
                            "name": "home.ook4mi.ovh",
                            "type": "CNAME",
                            "rData": {"cname": "tower.ook4mi.ovh."},
                        },
                        {
                            "name": "ook4mi.ovh",
                            "type": "SOA",
                            "rData": {"primaryNameServer": "ns1.ook4mi.ovh"},
                        },
                        {
                            "name": "disabled.ook4mi.ovh",
                            "type": "A",
                            "disabled": True,
                            "rData": {"ipAddress": "192.168.68.62"},
                        },
                    ]
                },
            },
        )

    transport = httpx.MockTransport(handler)
    collector = DnsCollector(
        base_url="http://192.168.68.62:5380",
        api_token="tok-123",
        zone_domain="ook4mi.ovh",
    )

    async with httpx.AsyncClient(transport=transport) as client:
        records, status = await collector.fetch_records(client=client)

    assert status == "ok"
    assert len(records) == 2
    assert records[0].domain == "sonarr.ook4mi.ovh"
    assert records[0].target == "192.168.68.62"
    assert records[1].domain == "home.ook4mi.ovh"
    assert records[1].target == "tower.ook4mi.ovh"


@pytest.mark.asyncio
async def test_dns_collector_degrades_gracefully_on_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    transport = httpx.MockTransport(handler)
    collector = DnsCollector(
        base_url="http://192.168.68.62:5380",
        api_token="tok-123",
    )

    async with httpx.AsyncClient(transport=transport) as client:
        records, status = await collector.fetch_records(client=client)

    assert records == []
    assert status == "error"
