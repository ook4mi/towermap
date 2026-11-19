"""Correlates Technitium DNS records, Nginx Proxy Manager hosts, and Docker containers."""

from app.models import ContainerInfo, DnsRecord, NpmProxyHost, RouteEntry


def _build_port_index(containers: list[ContainerInfo]) -> dict[int, ContainerInfo]:
    """Map host_port -> ContainerInfo, preferring running containers when duplicates exist."""
    index: dict[int, ContainerInfo] = {}
    for container in containers:
        for binding in container.ports:
            existing = index.get(binding.host_port)
            if existing is None or (existing.state != "running" and container.state == "running"):
                index[binding.host_port] = container
    return index


def _build_name_index(containers: list[ContainerInfo]) -> dict[str, ContainerInfo]:
    """Map container name and compose service name -> ContainerInfo."""
    index: dict[str, ContainerInfo] = {}
    for container in containers:
        index[container.name.lower()] = container
        if container.service_name and container.service_name.lower() not in index:
            index[container.service_name.lower()] = container
    return index


def correlate_routes(
    dns_records: list[DnsRecord],
    proxy_hosts: list[NpmProxyHost],
    containers: list[ContainerInfo],
    *,
    tower_hosts: set[str],
    default_domain: str = "ook4mi.ovh",
) -> list[RouteEntry]:
    """Build unified DNS -> NPM -> Docker Container route table with drift statuses."""
    normalized_tower_hosts = {h.strip().lower() for h in tower_hosts if h.strip()}
    normalized_zone = default_domain.strip().lower()

    dns_by_domain: dict[str, DnsRecord] = {}
    for rec in dns_records:
        key = rec.domain.strip().lower().rstrip(".")
        # Prefer A/AAAA over CNAME if both somehow exist for the same hostname
        if key not in dns_by_domain or dns_by_domain[key].record_type == "CNAME":
            dns_by_domain[key] = rec

    proxy_by_domain: dict[str, NpmProxyHost] = {}
    for host in proxy_hosts:
        for domain_name in host.domain_names:
            key = domain_name.strip().lower().rstrip(".")
            if key:
                proxy_by_domain[key] = host

    port_index = _build_port_index(containers)
    name_index = _build_name_index(containers)

    all_domains = sorted(set(dns_by_domain.keys()) | set(proxy_by_domain.keys()))
    routes: list[RouteEntry] = []

    for domain in all_domains:
        dns = dns_by_domain.get(domain)
        proxy = proxy_by_domain.get(domain)

        matched: ContainerInfo | None = None
        proxy_target: str | None = None
        target_is_local = False

        if proxy is not None:
            forward_host = proxy.forward_host.strip()
            forward_host_lower = forward_host.lower()
            proxy_target = (
                f"{forward_host}:{proxy.forward_port}"
                if proxy.forward_port
                else forward_host
            )
            if forward_host_lower in normalized_tower_hosts:
                target_is_local = True
                matched = port_index.get(proxy.forward_port)
            elif forward_host_lower in name_index:
                target_is_local = True
                matched = name_index[forward_host_lower]

        # Determine status
        if dns is not None and proxy is None:
            dns_target_lower = dns.target.strip().lower().rstrip(".")
            points_to_tower = (
                dns_target_lower in normalized_tower_hosts
                or dns_target_lower == normalized_zone
                or dns_target_lower.endswith(f".{normalized_zone}")
            )
            status = "orphan_dns" if points_to_tower else "external"
        elif dns is None and proxy is not None:
            status = "orphan_proxy"
        else:
            # Both DNS and NPM exist
            assert proxy is not None
            if not target_is_local:
                status = "external"
            elif not proxy.enabled:
                status = "target_down"
            elif matched is not None and matched.state == "running":
                status = "ok"
            else:
                status = "target_down"

        routes.append(
            RouteEntry(
                domain=domain,
                dns_record_type=dns.record_type if dns else None,
                dns_target=dns.target if dns else None,
                proxy_enabled=proxy.enabled if proxy else None,
                proxy_target=proxy_target,
                ssl_enabled=proxy.ssl_enabled if proxy else False,
                matched_container=matched.name if matched else None,
                status=status,
            )
        )

    return routes
