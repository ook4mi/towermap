"""Lightweight comment-preserving parser for Docker Compose YAML files.

Extracts inline and preceding YAML comments for `ports:`, `expose:`, and `environment:`
entries per service so TowerMap can annotate Gluetun and host-network ports.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_PORT_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")


@dataclass
class ServiceComposeHints:
    """Port comments and exposed ports extracted from a Compose service block."""

    # Keyed by (port, protocol) and (port, None) as protocol-agnostic fallback
    port_comments: dict[tuple[int, str | None], str] = field(default_factory=dict)
    # Extra ports listed under `expose:` as (port, protocol, comment)
    exposed_ports: list[tuple[int, str, str | None]] = field(default_factory=list)
    # Inline comments on environment variables, keyed by env var name
    env_comments: dict[str, str] = field(default_factory=dict)

    def get_comment(self, port: int, protocol: str) -> str | None:
        proto = protocol.lower()
        return self.port_comments.get((port, proto)) or self.port_comments.get((port, None))


def _split_code_and_comment(line: str) -> tuple[str, str | None]:
    """Split a YAML line into (content_before_comment, comment_text) respecting quotes."""
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif (
            ch == "#"
            and not in_single
            and not in_double
            and (idx == 0 or line[idx - 1].isspace())
        ):
            # In YAML, '#' starts a comment when at line start or preceded by whitespace
            comment = line[idx + 1 :].strip()
            return line[:idx].rstrip(), (comment or None)
    return line.rstrip(), None


def _strip_quotes(value: str) -> str:
    val = value.strip()
    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
        return val[1:-1].strip()
    return val


def _is_commented_out_yaml_item(comment_text: str) -> bool:
    """Return True if a full-line comment looks like a commented-out YAML item (`# - 8080:8080`)."""
    stripped = comment_text.lstrip()
    return stripped.startswith("- ") or stripped.startswith("-\t") or stripped == "-"


def _expand_port_range(expr: str) -> list[int]:
    match = _PORT_RANGE_RE.match(expr.strip())
    if not match:
        return []
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else start
    if start < 1 or end > 65535 or end < start or (end - start) > 500:
        return []
    return list(range(start, end + 1))


def _parse_short_port_spec(spec: str) -> list[tuple[int, str | None]]:
    """Parse short Compose port syntax and return list of (host_port, protocol_or_None).

    Examples:
      - "8080:8080" -> [(8080, None)]
      - "8080:80/tcp" -> [(8080, "tcp")]
      - "127.0.0.1:8080:80/udp" -> [(8080, "udp")]
      - "[::1]:8080:80" -> [(8080, None)]
      - "6881-6883:6881-6883/udp" -> [(6881, "udp"), (6882, "udp"), (6883, "udp")]
      - "3000" -> [(3000, None)]
    """
    cleaned = _strip_quotes(spec)
    if not cleaned:
        return []

    protocol: str | None = None
    if "/" in cleaned:
        cleaned, proto_part = cleaned.rsplit("/", 1)
        proto_lower = proto_part.strip().lower()
        if proto_lower in {"tcp", "udp"}:
            protocol = proto_lower

    # Handle bracketed IPv6 host IP like [::1]:8080:80
    if cleaned.startswith("["):
        closing = cleaned.find("]")
        if closing != -1:
            cleaned = cleaned[closing + 1 :].lstrip(":")

    parts = cleaned.split(":")
    if len(parts) in {1, 2}:
        host_expr = parts[0]
    elif len(parts) >= 3:
        # host_ip:host_port:container_port
        host_expr = parts[-2]
    else:
        return []

    ports = _expand_port_range(host_expr)
    return [(p, protocol) for p in ports]


def _parse_expose_spec(spec: str) -> list[tuple[int, str]]:
    """Parse Compose `expose:` item like `"3000"` or `"2222/tcp"`."""
    cleaned = _strip_quotes(spec)
    if not cleaned:
        return []
    protocol = "tcp"
    if "/" in cleaned:
        cleaned, proto_part = cleaned.rsplit("/", 1)
        proto_lower = proto_part.strip().lower()
        if proto_lower in {"tcp", "udp"}:
            protocol = proto_lower
    return [(p, protocol) for p in _expand_port_range(cleaned)]


def parse_compose_text(text: str) -> dict[str, ServiceComposeHints]:
    """Parse Compose YAML text and return mapping of service_name -> ServiceComposeHints."""
    result: dict[str, ServiceComposeHints] = {}

    in_services = False
    services_indent = -1
    current_service: str | None = None
    service_indent = -1
    current_section: str | None = None  # "ports" | "expose" | "environment" | None
    section_indent = -1

    group_comment: str | None = None
    # Long-syntax port item accumulator
    long_port_published: list[int] = []
    long_port_protocol: str | None = None
    long_port_comment: str | None = None

    def _flush_long_port() -> None:
        nonlocal long_port_published, long_port_protocol, long_port_comment
        if current_service and long_port_published and long_port_comment:
            hints = result.setdefault(current_service, ServiceComposeHints())
            for port_num in long_port_published:
                hints.port_comments[(port_num, long_port_protocol)] = long_port_comment
                if long_port_protocol is not None:
                    hints.port_comments.setdefault((port_num, None), long_port_comment)
        long_port_published = []
        long_port_protocol = None
        long_port_comment = None

    for raw_line in text.splitlines():
        raw_line = raw_line.replace("\t", "  ")
        if not raw_line.strip():
            # Blank line breaks group comment association
            group_comment = None
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        code, comment = _split_code_and_comment(raw_line)
        stripped = code.strip()

        # Full-line comment
        if not stripped:
            if (
                current_section in {"ports", "expose"}
                and comment
                and indent >= section_indent
                and not _is_commented_out_yaml_item(comment)
            ):
                group_comment = comment
            continue

        # Detect top-level sections
        if indent == 0 and stripped.endswith(":"):
            _flush_long_port()
            key = stripped[:-1].strip()
            in_services = key == "services"
            services_indent = 0 if in_services else -1
            current_service = None
            current_section = None
            group_comment = None
            continue

        if not in_services:
            continue

        # Detect service header directly under `services:`
        if (
            (current_service is None and indent > services_indent)
            or (current_service is not None and indent == service_indent)
        ) and stripped.endswith(":") and not stripped.startswith("-"):
            _flush_long_port()
            current_service = _strip_quotes(stripped[:-1])
            service_indent = indent
            current_section = None
            section_indent = -1
            group_comment = None
            result.setdefault(current_service, ServiceComposeHints())
            continue

        if current_service is None:
            continue

        # Leaving current service if dedented back to or above service_indent
        if indent <= service_indent:
            _flush_long_port()
            current_section = None
            group_comment = None
            continue

        # Detect service property headers (`ports:`, `expose:`, `environment:`, etc.)
        if (
            (current_section is None or indent <= section_indent)
            and not stripped.startswith("-")
            and ":" in stripped
        ):
            _flush_long_port()
            prop_key = stripped.split(":", 1)[0].strip()
            if prop_key in {"ports", "expose", "environment"}:
                current_section = prop_key
                section_indent = indent
                group_comment = None
            else:
                current_section = None
                section_indent = indent
                group_comment = None
            continue

        hints = result.setdefault(current_service, ServiceComposeHints())

        if current_section == "ports":
            if stripped.startswith("-"):
                _flush_long_port()
                item_body = stripped[1:].strip()
                # Check if long syntax starts on this line: `- target: 80` or `- published: 8080`
                long_keys = ("target:", "published:", "protocol:", "host_ip:", "mode:")
                if (
                    ":" in item_body
                    and not item_body.startswith(('"', "'"))
                    and item_body.startswith(long_keys)
                ):
                    long_port_comment = comment or group_comment
                    _accumulate_long_port_field(
                        item_body,
                        long_port_published,
                        comment,
                    )
                    if item_body.startswith("protocol:"):
                        long_port_protocol = _strip_quotes(item_body.split(":", 1)[1]).lower()
                else:
                    effective_comment = comment or group_comment
                    if effective_comment:
                        for port_num, proto in _parse_short_port_spec(item_body):
                            hints.port_comments[(port_num, proto)] = effective_comment
                            if proto is not None:
                                hints.port_comments.setdefault((port_num, None), effective_comment)
            elif ":" in stripped:
                # Continuation of long syntax port mapping
                if comment and not long_port_comment:
                    long_port_comment = comment
                key, val = (p.strip() for p in stripped.split(":", 1))
                if key == "published":
                    long_port_published.extend(_expand_port_range(_strip_quotes(val)))
                    if comment:
                        long_port_comment = comment
                elif key == "protocol":
                    long_port_protocol = _strip_quotes(val).lower()

        elif current_section == "expose":
            if stripped.startswith("-"):
                item_body = stripped[1:].strip()
                effective_comment = comment or group_comment
                for port_num, proto in _parse_expose_spec(item_body):
                    hints.exposed_ports.append((port_num, proto, effective_comment))
                    if effective_comment:
                        hints.port_comments[(port_num, proto)] = effective_comment
                        hints.port_comments.setdefault((port_num, None), effective_comment)

        elif current_section == "environment" and comment:
            if stripped.startswith("-"):
                env_item = _strip_quotes(stripped[1:].strip())
                if "=" in env_item:
                    env_key = env_item.split("=", 1)[0].strip()
                    if env_key:
                        hints.env_comments[env_key] = comment
            elif ":" in stripped:
                env_key = _strip_quotes(stripped.split(":", 1)[0].strip())
                if env_key:
                    hints.env_comments[env_key] = comment

    _flush_long_port()
    return result


def _accumulate_long_port_field(
    item_body: str,
    published_acc: list[int],
    _comment: str | None,
) -> None:
    key, val = (p.strip() for p in item_body.split(":", 1))
    if key == "published":
        published_acc.extend(_expand_port_range(_strip_quotes(val)))


def load_compose_hints(config_files_label: str | None) -> dict[str, ServiceComposeHints]:
    """Read one or more comma-separated Compose files and merge service hints.

    Fails safely (returns empty dict) if files are missing or unreadable.
    """
    if not config_files_label:
        return {}

    merged: dict[str, ServiceComposeHints] = {}
    for raw_path in config_files_label.split(","):
        path_str = raw_path.strip()
        if not path_str:
            continue
        path = Path(path_str)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parsed = parse_compose_text(text)
        for svc, hints in parsed.items():
            existing = merged.setdefault(svc, ServiceComposeHints())
            existing.port_comments.update(hints.port_comments)
            existing.exposed_ports.extend(hints.exposed_ports)
            existing.env_comments.update(hints.env_comments)

    return merged
