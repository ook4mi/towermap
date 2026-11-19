"""Docker Engine read-only collector using the official Docker Python SDK."""

import asyncio
import logging
from typing import Any

import docker
from docker.errors import DockerException

from app.models import ContainerInfo, PortBinding

logger = logging.getLogger(__name__)


def parse_port_bindings(
    raw_ports: dict[str, Any] | None,
    *,
    container_name: str,
    stack_name: str | None,
    via_gluetun: bool,
) -> list[PortBinding]:
    """Parse Docker NetworkSettings.Ports or HostConfig.PortBindings into PortBinding items."""
    if not raw_ports:
        return []

    bindings: list[PortBinding] = []
    seen: set[tuple[str, int, int, str]] = set()

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
            dedupe_key = (host_ip, host_port, container_port, protocol)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            bindings.append(
                PortBinding(
                    host_ip=host_ip,
                    host_port=host_port,
                    container_port=container_port,
                    protocol=protocol,
                    container_name=container_name,
                    stack_name=stack_name,
                    via_gluetun=via_gluetun,
                )
            )

    return sorted(bindings, key=lambda item: (item.host_port, item.protocol, item.host_ip))


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
) -> tuple[list[ContainerInfo], str | None]:
    """Convert raw Docker container inspect payloads into typed ContainerInfo models.

    Returns (containers, gluetun_full_id).
    """
    gluetun_full_id: str | None = None
    gluetun_names: set[str] = {"gluetun"}
    all_full_ids: set[str] = set()

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
            containers = client.containers.list(all=True)
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
