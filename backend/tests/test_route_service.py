"""Unit tests for DNS -> NPM -> Docker route correlation edge cases."""

from app.models import ContainerInfo, DnsRecord, NpmProxyHost, PortBinding
from app.services.route_service import correlate_routes

TOWER_HOSTS = {"192.168.68.62", "127.0.0.1", "localhost", "tower"}


def _sample_containers() -> list[ContainerInfo]:
    return [
        ContainerInfo(
            id="1",
            name="sonarr",
            image="lscr.io/linuxserver/sonarr",
            stack_name="media-vpn",
            state="running",
            ports=[
                PortBinding(
                    host_port=8989,
                    container_port=8989,
                    protocol="tcp",
                    container_name="sonarr",
                    stack_name="media-vpn",
                    via_gluetun=True,
                )
            ],
        ),
        ContainerInfo(
            id="2",
            name="paperless-ngx",
            image="ghcr.io/paperless-ngx/paperless-ngx",
            stack_name="paperless",
            state="exited",
            ports=[
                PortBinding(
                    host_port=4012,
                    container_port=8000,
                    protocol="tcp",
                    container_name="paperless-ngx",
                    stack_name="paperless",
                )
            ],
        ),
        ContainerInfo(
            id="3",
            name="homepage",
            image="ghcr.io/gethomepage/homepage",
            stack_name="homelab-apps",
            state="running",
            ports=[
                PortBinding(
                    host_port=3000,
                    container_port=3000,
                    protocol="tcp",
                    container_name="homepage",
                    stack_name="homelab-apps",
                )
            ],
        ),
    ]


def test_correlate_routes_covers_all_statuses() -> None:
    dns_records = [
        DnsRecord(domain="sonarr.ook4mi.ovh", record_type="A", target="192.168.68.62"),
        DnsRecord(domain="home.ook4mi.ovh", record_type="CNAME", target="tower.ook4mi.ovh"),
        DnsRecord(domain="docs.ook4mi.ovh", record_type="A", target="192.168.68.62"),
        DnsRecord(domain="missing-port.ook4mi.ovh", record_type="A", target="192.168.68.62"),
        DnsRecord(domain="disabled.ook4mi.ovh", record_type="A", target="192.168.68.62"),
        DnsRecord(domain="old-wiki.ook4mi.ovh", record_type="A", target="192.168.68.62"),
        DnsRecord(domain="nas.ook4mi.ovh", record_type="A", target="192.168.68.50"),
        DnsRecord(domain="router.ook4mi.ovh", record_type="A", target="192.168.68.62"),
    ]
    proxy_hosts = [
        # Healthy host IP + port match
        NpmProxyHost(
            domain_names=["sonarr.ook4mi.ovh"],
            forward_host="192.168.68.62",
            forward_port=8989,
            ssl_enabled=True,
            enabled=True,
        ),
        # Healthy direct container hostname match
        NpmProxyHost(
            domain_names=["home.ook4mi.ovh"],
            forward_host="homepage",
            forward_port=3000,
            ssl_enabled=True,
            enabled=True,
        ),
        # Stopped container -> target_down
        NpmProxyHost(
            domain_names=["docs.ook4mi.ovh"],
            forward_host="192.168.68.62",
            forward_port=4012,
            ssl_enabled=True,
            enabled=True,
        ),
        # Unbound port on tower -> target_down
        NpmProxyHost(
            domain_names=["missing-port.ook4mi.ovh"],
            forward_host="192.168.68.62",
            forward_port=9999,
            ssl_enabled=False,
            enabled=True,
        ),
        # Disabled proxy host -> target_down
        NpmProxyHost(
            domain_names=["disabled.ook4mi.ovh"],
            forward_host="192.168.68.62",
            forward_port=8989,
            ssl_enabled=True,
            enabled=False,
        ),
        # NPM host without DNS record -> orphan_proxy
        NpmProxyHost(
            domain_names=["grafana.ook4mi.ovh"],
            forward_host="192.168.68.62",
            forward_port=3002,
            ssl_enabled=False,
            enabled=True,
        ),
        # NPM forwards to another LAN host -> external
        NpmProxyHost(
            domain_names=["router.ook4mi.ovh"],
            forward_host="192.168.68.1",
            forward_port=80,
            ssl_enabled=True,
            enabled=True,
        ),
    ]

    routes = correlate_routes(
        dns_records,
        proxy_hosts,
        _sample_containers(),
        tower_hosts=TOWER_HOSTS,
        default_domain="ook4mi.ovh",
    )
    by_domain = {r.domain: r for r in routes}

    assert by_domain["sonarr.ook4mi.ovh"].status == "ok"
    assert by_domain["sonarr.ook4mi.ovh"].matched_container == "sonarr"
    assert by_domain["sonarr.ook4mi.ovh"].ssl_enabled is True

    assert by_domain["home.ook4mi.ovh"].status == "ok"
    assert by_domain["home.ook4mi.ovh"].matched_container == "homepage"

    assert by_domain["docs.ook4mi.ovh"].status == "target_down"
    assert by_domain["docs.ook4mi.ovh"].matched_container == "paperless-ngx"

    assert by_domain["missing-port.ook4mi.ovh"].status == "target_down"
    assert by_domain["missing-port.ook4mi.ovh"].matched_container is None

    assert by_domain["disabled.ook4mi.ovh"].status == "target_down"
    assert by_domain["disabled.ook4mi.ovh"].proxy_enabled is False

    assert by_domain["old-wiki.ook4mi.ovh"].status == "orphan_dns"
    assert by_domain["old-wiki.ook4mi.ovh"].proxy_target is None

    assert by_domain["grafana.ook4mi.ovh"].status == "orphan_proxy"
    assert by_domain["grafana.ook4mi.ovh"].dns_target is None

    assert by_domain["nas.ook4mi.ovh"].status == "external"
    assert by_domain["router.ook4mi.ovh"].status == "external"
