"""Docker Engine read-only collector using the official Docker Python SDK."""

import asyncio
import logging
from typing import Any

import docker
from docker.errors import DockerException

from app.collectors.compose_parser import ServiceComposeHints, load_compose_hints
from app.models import ContainerInfo, PortBinding

logger = logging.getLogger(__name__)

# Exact environment variable names commonly used to configure a container's own listening port
_LISTENING_PORT_ENV_KEYS = {
    "PORT",
    "HTTP_PORT",
    "HTTPS_PORT",
    "WEB_PORT",
    "WEBUI_PORT",
    "SERVER_PORT",
    "LISTEN_PORT",
    "APP_PORT",
    "UI_PORT",
    "API_PORT",
    "SSH_PORT",
    "SSH_LISTEN_PORT",
    "METRICS_PORT",
}

# Suffixes that unambiguously denote a container's listening port (excluding DB/client ports)
_LISTENING_PORT_ENV_SUFFIXES = (
    "_LISTEN_PORT",
    "__HTTP_PORT",
    "__HTTPS_PORT",
    "__SSH_PORT",
    "__SSH_LISTEN_PORT",
)

_IGNORED_PORT_ENV_PREFIXES = (
    "DB_",
    "DATABASE_",
    "POSTGRES_",
    "MYSQL_",
    "MARIADB_",
    "REDIS_",
    "SMTP_",
    "MAIL_",
    "LDAP_",
    "PROXY_",
)


def parse_port_bindings(
    raw_ports: dict[str, Any] | None,
    *,
    container_name: str,
    stack_name: str | None,
    via_gluetun: bool,
    compose_hints: ServiceComposeHints | None = None,
) -> list[PortBinding]:
    """Parse Docker NetworkSettings.Ports or HostConfig.PortBindings into PortBinding items."""
    if not raw_ports:
        return []

    by_key: dict[tuple[int, int, str], PortBinding] = {}

    for container_port_proto, host_entries in raw_ports.items():
        if not host_entries:
            continue
        parts = container_port_proto.split("/")
        try:
            container_port = int(parts[0])
        except (ValueError, IndexError):
            continue
        protocol = (parts[1] if len(parts) > 1 else "tcp").lower()

        for entry in host_entries:
            host_port_raw = entry.get("HostPort")
            if not host_port_raw:
                continue
            try:
                host_port = int(host_port_raw)
            except ValueError:
                continue
            host_ip = entry.get("HostIp") or "0.0.0.0"
            dedupe_key = (host_port, container_port, protocol)
            existing = by_key.get(dedupe_key)
            # Deduplicate IPv4/IPv6 dual-stack entries (0.0.0.0 & ::) so each port appears once,
            # preferring IPv4 (0.0.0.0 or explicit IP) over wildcard IPv6 (::).
            if existing is not None and not (existing.host_ip == "::" and host_ip != "::"):
                continue
            comment = (
                compose_hints.get_comment(host_port, protocol)
                if compose_hints is not None
                else None
            )
            by_key[dedupe_key] = PortBinding(
                host_ip=host_ip,
                host_port=host_port,
                container_port=container_port,
                protocol=protocol,
                container_name=container_name,
                stack_name=stack_name,
                via_gluetun=via_gluetun,
                comment=comment,
            )

    return sorted(
        by_key.values(),
        key=lambda item: (item.host_port, item.protocol, item.host_ip),
    )


def _parse_env_list(raw_env: list[str] | None) -> dict[str, str]:
    env_map: dict[str, str] = {}
    for entry in raw_env or []:
        if "=" in entry:
            key, value = entry.split("=", 1)
            env_map[key.strip()] = value.strip()
    return env_map


def _parse_port_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        port = int(value.strip())
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


def _parse_towermap_ports_label(raw_label: str | None) -> list[tuple[int, str, str | None]]:
    """Parse optional `towermap.ports` label like `3000/tcp:Gitea Web,2222/tcp:Gitea SSH`."""
    if not raw_label:
        return []
    entries: list[tuple[int, str, str | None]] = []
    for item in raw_label.split(","):
        token = item.strip()
        if not token:
            continue
        comment: str | None = None
        if ":" in token:
            port_part, comment_part = token.split(":", 1)
            comment = comment_part.strip() or None
        else:
            port_part = token
        protocol = "tcp"
        if "/" in port_part:
            port_str, proto_str = port_part.split("/", 1)
            proto_lower = proto_str.strip().lower()
            if proto_lower in {"tcp", "udp"}:
                protocol = proto_lower
        else:
            port_str = port_part
        port_num = _parse_port_int(port_str)
        if port_num is not None:
            entries.append((port_num, protocol, comment))
    return entries


def extract_host_network_ports(
    *,
    config: dict[str, Any],
    labels: dict[str, Any],
    container_name: str,
    stack_name: str | None,
    compose_hints: ServiceComposeHints | None = None,
) -> list[PortBinding]:
    """Infer listening ports for `network_mode: host` containers (e.g. Gitea, Plex).

    Combines:
      1. Optional `towermap.ports` container label (highest precedence)
      2. Listening-port environment variables (including Gitea `GITEA__server__*`)
      3. Compose `expose:` entries (with YAML comments)
      4. Docker `Config.ExposedPorts` (from Dockerfile EXPOSE / compose expose)
    """
    discovered: dict[tuple[int, str], str | None] = {}
    env_map = _parse_env_list(config.get("Env"))
    env_upper = {k.upper(): (k, v) for k, v in env_map.items()}

    # Track default image exposed ports that were explicitly overridden/disabled by env vars
    suppressed_exposed: set[tuple[int, str]] = set()

    # 1. Explicit `towermap.ports` label
    for port_num, proto, comment in _parse_towermap_ports_label(labels.get("towermap.ports")):
        discovered[(port_num, proto)] = comment or "towermap.ports label"

    # 2. Gitea-specific server env overrides (common with network_mode: host)
    gitea_http = env_upper.get("GITEA__SERVER__HTTP_PORT")
    if gitea_http:
        orig_key, raw_val = gitea_http
        port_num = _parse_port_int(raw_val)
        if port_num is not None:
            yaml_comment = compose_hints.env_comments.get(orig_key) if compose_hints else None
            discovered.setdefault((port_num, "tcp"), yaml_comment or "Gitea HTTP (host network)")
            if port_num != 3000:
                suppressed_exposed.add((3000, "tcp"))

    gitea_disable_ssh = env_upper.get("GITEA__SERVER__DISABLE_SSH")
    ssh_disabled = bool(
        gitea_disable_ssh and gitea_disable_ssh[1].strip().lower() in {"true", "1", "yes"}
    )
    if ssh_disabled:
        suppressed_exposed.add((22, "tcp"))
    else:
        gitea_ssh = (
            env_upper.get("GITEA__SERVER__SSH_LISTEN_PORT")
            or env_upper.get("GITEA__SERVER__SSH_PORT")
        )
        if gitea_ssh:
            orig_key, raw_val = gitea_ssh
            port_num = _parse_port_int(raw_val)
            if port_num is not None:
                yaml_comment = compose_hints.env_comments.get(orig_key) if compose_hints else None
                discovered.setdefault((port_num, "tcp"), yaml_comment or "Gitea SSH (host network)")
                if port_num != 22:
                    suppressed_exposed.add((22, "tcp"))

    # 3. Generic listening-port env vars
    for key_upper, (orig_key, raw_val) in env_upper.items():
        if key_upper.startswith("GITEA__SERVER__"):
            continue
        if key_upper.startswith(_IGNORED_PORT_ENV_PREFIXES):
            continue
        if key_upper in _LISTENING_PORT_ENV_KEYS or key_upper.endswith(
            _LISTENING_PORT_ENV_SUFFIXES
        ):
            port_num = _parse_port_int(raw_val)
            if port_num is not None:
                yaml_comment = compose_hints.env_comments.get(orig_key) if compose_hints else None
                discovered.setdefault(
                    (port_num, "tcp"),
                    yaml_comment or f"Host network ({orig_key})",
                )

    # 4. Compose `expose:` entries
    if compose_hints is not None:
        for port_num, proto, comment in compose_hints.exposed_ports:
            discovered.setdefault((port_num, proto), comment or "Host network (expose)")

    # 5. Docker image / container `Config.ExposedPorts`
    raw_exposed = config.get("ExposedPorts") or {}
    for port_proto in raw_exposed:
        parts = str(port_proto).split("/")
        port_num = _parse_port_int(parts[0])
        if port_num is None:
            continue
        proto = (parts[1] if len(parts) > 1 else "tcp").lower()
        if (port_num, proto) in suppressed_exposed:
            continue
        yaml_comment = (
            compose_hints.get_comment(port_num, proto) if compose_hints is not None else None
        )
        discovered.setdefault(
            (port_num, proto),
            yaml_comment or "Host network (EXPOSE)",
        )

    bindings = [
        PortBinding(
            host_ip="0.0.0.0",
            host_port=port_num,
            container_port=port_num,
            protocol=proto,
            container_name=container_name,
            stack_name=stack_name,
            via_gluetun=False,
            host_network=True,
            comment=comment,
        )
        for (port_num, proto), comment in discovered.items()
    ]
    return sorted(bindings, key=lambda item: (item.host_port, item.protocol))


def is_gluetun_container(name: str, image: str, service_name: str | None) -> bool:
    """Return True if a container represents the gluetun VPN gateway."""
    lowered_name = name.lower()
    lowered_image = image.lower()
    lowered_service = (service_name or "").lower()
    return (
        lowered_name == "gluetun"
        or lowered_service == "gluetun"
        or "gluetun" in lowered_image
    )


def parse_raw_containers(
    raw_attrs_list: list[dict[str, Any]],
    *,
    compose_hints_by_file: dict[str, dict[str, ServiceComposeHints]] | None = None,
) -> tuple[list[ContainerInfo], str | None]:
    """Convert raw Docker container inspect payloads into typed ContainerInfo models.

    Returns (containers, gluetun_full_id).
    """
    gluetun_full_id: str | None = None
    gluetun_names: set[str] = {"gluetun"}
    all_full_ids: set[str] = set()
    file_hints_cache: dict[str, dict[str, ServiceComposeHints]] = (
        dict(compose_hints_by_file) if compose_hints_by_file else {}
    )

    for attrs in raw_attrs_list:
        full_id = str(attrs.get("Id", ""))
        if full_id:
            all_full_ids.add(full_id)
        name = str(attrs.get("Name", "")).lstrip("/")
        config = attrs.get("Config") or {}
        labels = config.get("Labels") or {}
        image = str(config.get("Image") or "")
        service_name = labels.get("com.docker.compose.service")
        if is_gluetun_container(name, image, service_name):
            gluetun_full_id = full_id
            if name:
                gluetun_names.add(name.lower())

    containers: list[ContainerInfo] = []
    for attrs in raw_attrs_list:
        full_id = str(attrs.get("Id", ""))
        short_id = full_id[:12]
        name = str(attrs.get("Name", "")).lstrip("/") or short_id

        config = attrs.get("Config") or {}
        labels = config.get("Labels") or {}
        state_obj = attrs.get("State") or {}
        host_config = attrs.get("HostConfig") or {}
        network_settings = attrs.get("NetworkSettings") or {}

        image = str(config.get("Image") or "")
        stack_name = labels.get("com.docker.compose.project")
        service_name = labels.get("com.docker.compose.service")
        compose_file = labels.get("com.docker.compose.project.config_files")

        # Load compose YAML comments once per config_files string
        service_hints: ServiceComposeHints | None = None
        if compose_file:
            if compose_file not in file_hints_cache:
                file_hints_cache[compose_file] = load_compose_hints(compose_file)
            hints_for_file = file_hints_cache[compose_file]
            service_hints = hints_for_file.get(service_name or "") or hints_for_file.get(name)
            if service_hints is None:
                lowered_hints = {k.lower(): v for k, v in hints_for_file.items()}
                service_hints = (
                    lowered_hints.get((service_name or "").lower())
                    or lowered_hints.get(name.lower())
                )

        state = str(state_obj.get("Status") or "unknown").lower()
        health_obj = state_obj.get("Health")
        health = (
            str(health_obj.get("Status")).lower()
            if isinstance(health_obj, dict) and health_obj.get("Status")
            else "none"
        )
        started_at_raw = state_obj.get("StartedAt")
        started_at = (
            str(started_at_raw)
            if started_at_raw and not str(started_at_raw).startswith("0001-01-01")
            else None
        )

        network_mode = str(host_config.get("NetworkMode") or "default")
        is_self_gluetun = full_id == gluetun_full_id or is_gluetun_container(
            name, image, service_name
        )
        gluetun_attached = _detect_gluetun_attachment(
            network_mode=network_mode,
            labels=labels,
            gluetun_full_id=gluetun_full_id,
            gluetun_names=gluetun_names,
            all_full_ids=all_full_ids,
        )

        # Running containers expose live ports in NetworkSettings.Ports;
        # stopped containers still retain configured HostConfig.PortBindings.
        raw_ports = network_settings.get("Ports") or host_config.get("PortBindings") or {}
        ports = parse_port_bindings(
            raw_ports,
            container_name=name,
            stack_name=stack_name,
            via_gluetun=is_self_gluetun or gluetun_attached,
            compose_hints=service_hints,
        )

        # For `network_mode: host` containers (e.g. Gitea), Docker leaves Ports empty;
        # infer ports from labels, listening-port env vars, compose expose, and image EXPOSE.
        if network_mode.lower() == "host" and not ports:
            ports = extract_host_network_ports(
                config=config,
                labels=labels,
                container_name=name,
                stack_name=stack_name,
                compose_hints=service_hints,
            )

        containers.append(
            ContainerInfo(
                id=short_id,
                name=name,
                image=image,
                stack_name=stack_name,
                service_name=service_name,
                compose_file=compose_file,
                state=state,
                health=health,
                started_at=started_at,
                network_mode=network_mode,
                gluetun_attached=gluetun_attached,
                ports=ports,
            )
        )

    containers.sort(key=lambda item: (item.stack_name or "~standalone", item.name))
    return containers, gluetun_full_id


def _detect_gluetun_attachment(
    *,
    network_mode: str,
    labels: dict[str, Any],
    gluetun_full_id: str | None,
    gluetun_names: set[str],
    all_full_ids: set[str],
) -> bool:
    """Detect whether a container shares gluetun's network namespace (including stale IDs)."""
    lowered_mode = network_mode.lower()
    if lowered_mode == "service:gluetun":
        return True
    if not lowered_mode.startswith("container:"):
        return False

    target = network_mode.split(":", 1)[1].strip()
    if not target:
        return False

    if target.lower() in gluetun_names:
        return True
    if gluetun_full_id and (target == gluetun_full_id or gluetun_full_id.startswith(target)):
        return True

    # Stale container ID: target doesn't match any active container, and either gluetun exists
    # or compose depends_on mentions gluetun.
    depends_on = str(labels.get("com.docker.compose.depends_on") or "").lower()
    return target not in all_full_ids and (
        "gluetun" in depends_on or gluetun_full_id is not None
    )


class DockerCollector:
    """Collects container and port metadata from the Docker Engine."""

    def __init__(self, docker_host: str | None = None) -> None:
        self._docker_host = docker_host or None

    def _collect_sync(self) -> tuple[list[ContainerInfo], str | None]:
        client = (
            docker.DockerClient(base_url=self._docker_host)
            if self._docker_host
            else docker.from_env()
        )
        try:
            containers = client.containers.list(all=True, ignore_removed=True)
            raw_attrs = [container.attrs for container in containers]
            return parse_raw_containers(raw_attrs)
        finally:
            client.close()

    async def collect(self) -> tuple[list[ContainerInfo], str | None]:
        """Collect all containers asynchronously without blocking the event loop."""
        try:
            return await asyncio.to_thread(self._collect_sync)
        except DockerException as exc:
            logger.error("Failed to query Docker Engine: %s", exc)
            raise
