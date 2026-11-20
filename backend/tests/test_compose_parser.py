"""Unit tests for Compose YAML comment parsing and host-network port discovery."""

from pathlib import Path

from app.collectors.compose_parser import load_compose_hints, parse_compose_text
from app.collectors.docker_collector import parse_raw_containers


def test_parse_compose_text_extracts_inline_and_group_comments() -> None:
    yaml_text = """
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    ports:
      - "8000:8000/tcp" # Gluetun control API
      # qBittorrent
      - 8080:8080
      - 6881:6881/tcp
      - 6881:6881/udp
      # - 9999:9999 # disabled port should be ignored
      - "8989:8989" # Sonarr WebUI
      - target: 7878
        published: 7878 # Radarr
        protocol: tcp
      - "6890-6891:6890-6891/udp" # Torrent range

  gitea:
    image: gitea/gitea:latest
    network_mode: host
    expose:
      - "3000" # Gitea Web UI
    environment:
      - GITEA__server__HTTP_PORT=3005 # Custom Gitea HTTP
      - GITEA__server__SSH_LISTEN_PORT=2222 # Custom Gitea SSH
"""
    hints = parse_compose_text(yaml_text)

    gluetun = hints["gluetun"]
    assert gluetun.get_comment(8000, "tcp") == "Gluetun control API"
    assert gluetun.get_comment(8080, "tcp") == "qBittorrent"
    assert gluetun.get_comment(6881, "tcp") == "qBittorrent"
    assert gluetun.get_comment(6881, "udp") == "qBittorrent"
    assert gluetun.get_comment(9999, "tcp") is None
    assert gluetun.get_comment(8989, "tcp") == "Sonarr WebUI"
    assert gluetun.get_comment(7878, "tcp") == "Radarr"
    assert gluetun.get_comment(6890, "udp") == "Torrent range"
    assert gluetun.get_comment(6891, "udp") == "Torrent range"

    gitea = hints["gitea"]
    assert gitea.get_comment(3000, "tcp") == "Gitea Web UI"
    assert gitea.env_comments["GITEA__server__HTTP_PORT"] == "Custom Gitea HTTP"
    assert gitea.env_comments["GITEA__server__SSH_LISTEN_PORT"] == "Custom Gitea SSH"


def test_parse_raw_containers_attaches_compose_comments_from_disk(tmp_path: Path) -> None:
    compose_file = tmp_path / "compose.yaml"
    compose_file.write_text(
        """
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    ports:
      - "8989:8989" # Sonarr
      - "7878:7878" # Radarr
""",
        encoding="utf-8",
    )

    raw = [
        {
            "Id": "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            "Name": "/gluetun",
            "Config": {
                "Image": "qmcgaw/gluetun:latest",
                "Labels": {
                    "com.docker.compose.project": "media-vpn",
                    "com.docker.compose.service": "gluetun",
                    "com.docker.compose.project.config_files": str(compose_file),
                },
            },
            "State": {"Status": "running"},
            "HostConfig": {"NetworkMode": "media-vpn_default"},
            "NetworkSettings": {
                "Ports": {
                    "8989/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8989"}],
                    "7878/tcp": [{"HostIp": "0.0.0.0", "HostPort": "7878"}],
                }
            },
        }
    ]

    containers, _ = parse_raw_containers(raw)
    ports_by_num = {p.host_port: p for p in containers[0].ports}
    assert ports_by_num[8989].comment == "Sonarr"
    assert ports_by_num[7878].comment == "Radarr"


def test_host_network_gitea_discovers_exposed_and_env_override_ports(tmp_path: Path) -> None:
    compose_file = tmp_path / "gitea.yml"
    compose_file.write_text(
        """
services:
  gitea:
    image: gitea/gitea:latest
    network_mode: host
    environment:
      - GITEA__server__HTTP_PORT=3005 # Gitea Web
      - GITEA__server__SSH_LISTEN_PORT=2222 # Gitea SSH
""",
        encoding="utf-8",
    )

    raw = [
        {
            "Id": "aaaa222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            "Name": "/gitea",
            "Config": {
                "Image": "gitea/gitea:latest",
                "ExposedPorts": {"22/tcp": {}, "3000/tcp": {}},
                "Env": [
                    "GITEA__server__HTTP_PORT=3005",
                    "GITEA__server__SSH_LISTEN_PORT=2222",
                    "DB_PORT=5432",
                ],
                "Labels": {
                    "com.docker.compose.project": "gitea",
                    "com.docker.compose.service": "gitea",
                    "com.docker.compose.project.config_files": str(compose_file),
                },
            },
            "State": {"Status": "running"},
            "HostConfig": {"NetworkMode": "host"},
            "NetworkSettings": {"Ports": {}},
        }
    ]

    containers, _ = parse_raw_containers(raw)
    gitea = containers[0]
    ports_by_num = {p.host_port: p for p in gitea.ports}

    # Overridden defaults (3000, 22) and ignored DB_PORT (5432) should not appear
    assert set(ports_by_num.keys()) == {2222, 3005}
    assert ports_by_num[3005].host_network is True
    assert ports_by_num[3005].comment == "Gitea Web"
    assert ports_by_num[2222].host_network is True
    assert ports_by_num[2222].comment == "Gitea SSH"


def test_host_network_default_exposed_ports_without_env_vars() -> None:
    raw = [
        {
            "Id": "bbbb222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            "Name": "/gitea",
            "Config": {
                "Image": "gitea/gitea:latest",
                "ExposedPorts": {"22/tcp": {}, "3000/tcp": {}},
                "Env": [],
                "Labels": {
                    "com.docker.compose.project": "gitea",
                    "com.docker.compose.service": "gitea",
                },
            },
            "State": {"Status": "running"},
            "HostConfig": {"NetworkMode": "host"},
            "NetworkSettings": {"Ports": {}},
        }
    ]

    containers, _ = parse_raw_containers(raw)
    ports = {p.host_port: p for p in containers[0].ports}
    assert set(ports.keys()) == {22, 3000}
    assert all(p.host_network is True for p in ports.values())


def test_load_compose_hints_returns_empty_for_missing_file() -> None:
    assert load_compose_hints("/nonexistent/path/compose.yaml") == {}
