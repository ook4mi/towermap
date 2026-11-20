"""Unit tests for Docker port parsing and PortService logic."""

from app.collectors.docker_collector import parse_port_bindings, parse_raw_containers
from app.models import ContainerInfo, PortBinding
from app.services.port_service import check_port_availability, extract_ports, find_next_free_port


def test_parse_port_bindings_extracts_and_deduplicates() -> None:
    raw_ports = {
        "80/tcp": [
            {"HostIp": "::", "HostPort": "8080"},
            {"HostIp": "0.0.0.0", "HostPort": "8080"},
            {"HostIp": "0.0.0.0", "HostPort": "8080"},
        ],
        "53/udp": [{"HostIp": "0.0.0.0", "HostPort": "53"}],
        "9000/tcp": None,
    }

    bindings = parse_port_bindings(
        raw_ports,
        container_name="test-app",
        stack_name="core",
        via_gluetun=False,
    )

    assert len(bindings) == 2
    assert bindings[0].host_port == 53
    assert bindings[0].protocol == "udp"
    assert bindings[1].host_port == 8080
    assert bindings[1].container_port == 80
    assert bindings[1].protocol == "tcp"
    assert bindings[1].host_ip == "0.0.0.0"


def test_parse_raw_containers_marks_gluetun_ports_and_attachments() -> None:
    gluetun_id = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    raw = [
        {
            "Id": gluetun_id,
            "Name": "/gluetun",
            "Config": {
                "Image": "qmcgaw/gluetun:latest",
                "Labels": {
                    "com.docker.compose.project": "media-vpn",
                    "com.docker.compose.service": "gluetun",
                    "com.docker.compose.project.config_files": (
                        "/home/ook4mi/docker/media-vpn/compose.yaml"
                    ),
                },
            },
            "State": {"Status": "running", "StartedAt": "2026-11-18T06:00:00Z"},
            "HostConfig": {"NetworkMode": "media-vpn_default"},
            "NetworkSettings": {
                "Ports": {
                    "8989/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8989"}],
                }
            },
        },
        {
            "Id": "aaaa1111222233334444555566667777888899990000aaaabbbbccccddddeeee",
            "Name": "/sonarr",
            "Config": {
                "Image": "lscr.io/linuxserver/sonarr:latest",
                "Labels": {
                    "com.docker.compose.project": "media-vpn",
                    "com.docker.compose.service": "sonarr",
                },
            },
            "State": {"Status": "running", "StartedAt": "2026-11-18T06:00:10Z"},
            "HostConfig": {"NetworkMode": f"container:{gluetun_id}"},
            "NetworkSettings": {"Ports": {}},
        },
    ]

    containers, detected_gluetun_id = parse_raw_containers(raw)

    assert detected_gluetun_id == gluetun_id
    by_name = {c.name: c for c in containers}
    assert by_name["gluetun"].ports[0].via_gluetun is True
    assert by_name["sonarr"].gluetun_attached is True


def test_extract_ports_filters_by_protocol_and_query() -> None:
    containers = [
        ContainerInfo(
            id="1",
            name="technitium-dns",
            image="technitium/dns-server",
            stack_name="networking",
            state="running",
            ports=[
                PortBinding(
                    host_port=53,
                    container_port=53,
                    protocol="tcp",
                    container_name="technitium-dns",
                    stack_name="networking",
                ),
                PortBinding(
                    host_port=53,
                    container_port=53,
                    protocol="udp",
                    container_name="technitium-dns",
                    stack_name="networking",
                ),
            ],
        ),
        ContainerInfo(
            id="2",
            name="gluetun",
            image="qmcgaw/gluetun",
            stack_name="media-vpn",
            state="running",
            ports=[
                PortBinding(
                    host_port=8989,
                    container_port=8989,
                    protocol="tcp",
                    container_name="gluetun",
                    stack_name="media-vpn",
                    via_gluetun=True,
                ),
            ],
        ),
    ]

    udp_only = extract_ports(containers, protocol="udp")
    assert len(udp_only) == 1
    assert udp_only[0].host_port == 53

    gluetun_query = extract_ports(containers, query="gluetun")
    assert len(gluetun_query) == 1
    assert gluetun_query[0].host_port == 8989


def test_check_port_availability_detects_conflict_and_suggests_next_free() -> None:
    bindings = [
        PortBinding(
            host_port=4010,
            container_port=8000,
            protocol="tcp",
            container_name="towermap",
            stack_name="towermap",
        ),
        PortBinding(
            host_port=4011,
            container_port=80,
            protocol="tcp",
            container_name="vaultwarden",
            stack_name="homelab-apps",
        ),
    ]

    conflict_check = check_port_availability(
        4010, bindings, suggest_start=4010, suggest_end=4015
    )
    assert conflict_check.available is False
    assert len(conflict_check.conflicts) == 1
    assert conflict_check.conflicts[0].container_name == "towermap"
    assert conflict_check.next_free_port == 4012

    free_check = check_port_availability(
        4014, bindings, suggest_start=4010, suggest_end=4015
    )
    assert free_check.available is True
    assert free_check.conflicts == []
    assert free_check.next_free_port == 4012


def test_find_next_free_port_returns_none_when_range_exhausted() -> None:
    used = {4010, 4011, 4012}
    assert find_next_free_port(used, start=4010, end=4012) is None
