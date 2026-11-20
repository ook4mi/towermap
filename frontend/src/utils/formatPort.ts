import type { PortBinding } from "../api/types";

/**
 * Format a PortBinding in familiar Docker Compose style, e.g.:
 *   - 9696:9696
 *   - 53:53/udp
 *   - 127.0.0.1:8080:80
 */
export function formatComposePort(port: PortBinding): string {
  const ipPrefix =
    port.host_ip && port.host_ip !== "0.0.0.0" && port.host_ip !== "::"
      ? `${port.host_ip}:`
      : "";
  const protoSuffix =
    port.protocol && port.protocol.toLowerCase() !== "tcp"
      ? `/${port.protocol.toLowerCase()}`
      : "";
  return `${ipPrefix}${port.host_port}:${port.container_port}${protoSuffix}`;
}

/**
 * Deduplicate port bindings by (host_port, container_port, protocol),
 * keeping IPv4 bindings over IPv6 wildcard (::) and preserving comments.
 */
export function deduplicatePorts(ports: PortBinding[]): PortBinding[] {
  const map = new Map<string, PortBinding>();
  for (const port of ports) {
    const key = `${port.host_port}:${port.container_port}/${port.protocol.toLowerCase()}`;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, port);
    } else if (existing.host_ip === "::" && port.host_ip !== "::") {
      map.set(key, { ...port, comment: port.comment ?? existing.comment });
    } else if (!existing.comment && port.comment) {
      map.set(key, { ...existing, comment: port.comment });
    }
  }
  return Array.from(map.values()).sort(
    (a, b) => a.host_port - b.host_port || a.protocol.localeCompare(b.protocol),
  );
}
