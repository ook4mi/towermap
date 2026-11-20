"""Port registry extraction, conflict checking, and next-free-port suggestion."""

from app.models import ContainerInfo, PortBinding, PortCheckResponse


def extract_ports(
    containers: list[ContainerInfo],
    *,
    protocol: str | None = None,
    query: str | None = None,
) -> list[PortBinding]:
    """Return a sorted list of all host port bindings across containers."""
    normalized_proto = protocol.strip().lower() if protocol else None
    normalized_query = query.strip().lower() if query else None

    bindings: list[PortBinding] = []
    for container in containers:
        for binding in container.ports:
            if normalized_proto and binding.protocol.lower() != normalized_proto:
                continue
            if normalized_query:
                haystack = " ".join(
                    [
                        str(binding.host_port),
                        str(binding.container_port),
                        binding.protocol,
                        binding.container_name,
                        binding.stack_name or "",
                        binding.host_ip,
                        binding.comment or "",
                        "gluetun" if binding.via_gluetun else "",
                        "host" if binding.host_network else "",
                    ]
                ).lower()
                if normalized_query not in haystack:
                    continue
            bindings.append(binding)

    bindings.sort(
        key=lambda item: (item.host_port, item.protocol, item.container_name, item.host_ip)
    )
    return bindings


def find_next_free_port(
    used_ports: set[int],
    *,
    start: int = 4010,
    end: int = 4099,
) -> int | None:
    """Find the lowest unused host port within [start, end], inclusive."""
    if start > end:
        return None
    for candidate in range(start, end + 1):
        if candidate not in used_ports:
            return candidate
    return None


def check_port_availability(
    port: int,
    bindings: list[PortBinding],
    *,
    suggest_start: int = 4010,
    suggest_end: int = 4099,
) -> PortCheckResponse:
    """Check whether `port` is bound by any container and suggest the next free port."""
    conflicts = [b for b in bindings if b.host_port == port]
    used_ports = {b.host_port for b in bindings}
    next_free = find_next_free_port(used_ports, start=suggest_start, end=suggest_end)
    return PortCheckResponse(
        port=port,
        available=len(conflicts) == 0,
        conflicts=conflicts,
        next_free_port=next_free,
        suggest_range_start=suggest_start,
        suggest_range_end=suggest_end,
    )
