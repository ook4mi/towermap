"""Core Pydantic data models for TowerMap API responses and internal records."""

from typing import Literal

from pydantic import BaseModel, Field


class PortBinding(BaseModel):
    host_ip: str = "0.0.0.0"
    host_port: int
    container_port: int
    protocol: str  # "tcp" | "udp"
    container_name: str
    stack_name: str | None = None
    via_gluetun: bool = False
    host_network: bool = False
    comment: str | None = None


class ContainerInfo(BaseModel):
    id: str
    name: str
    image: str
    stack_name: str | None = None
    service_name: str | None = None
    compose_file: str | None = None
    state: str  # running, exited, restarting, created, ...
    health: str | None = None
    started_at: str | None = None
    network_mode: str = "default"
    gluetun_attached: bool = False
    ports: list[PortBinding] = Field(default_factory=list)


class GluetunOverview(BaseModel):
    container_state: str
    container_id: str | None = None
    started_at: str | None = None
    vpn_status: str | None = None
    public_ip: str | None = None
    country: str | None = None
    region: str | None = None
    organization: str | None = None
    configured: bool = False
    reachable: bool = False
    attached_containers: list[ContainerInfo] = Field(default_factory=list)
    published_ports: list[PortBinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DnsRecord(BaseModel):
    domain: str
    record_type: str  # A | AAAA | CNAME
    target: str


class NpmProxyHost(BaseModel):
    domain_names: list[str] = Field(default_factory=list)
    forward_scheme: str = "http"
    forward_host: str
    forward_port: int
    ssl_enabled: bool = False
    enabled: bool = True


class RouteEntry(BaseModel):
    domain: str
    dns_record_type: str | None = None
    dns_target: str | None = None
    proxy_enabled: bool | None = None
    proxy_target: str | None = None  # e.g., "192.168.68.62:8989"
    ssl_enabled: bool = False
    matched_container: str | None = None
    status: Literal["ok", "orphan_dns", "orphan_proxy", "target_down", "external"]


class IntegrationStatus(BaseModel):
    docker: str = "ok"  # ok | mock | error
    gluetun: str = "unconfigured"  # ok | mock | unconfigured | error
    npm: str = "unconfigured"  # ok | mock | unconfigured | error
    dns: str = "unconfigured"  # ok | mock | unconfigured | error


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: Literal["mock", "live"]


class OverviewResponse(BaseModel):
    mode: Literal["mock", "live"]
    total_stacks: int
    total_containers: int
    running_containers: int
    stopped_containers: int
    unhealthy_containers: int
    used_ports_count: int
    gluetun_attached_count: int
    gluetun_vpn_status: str | None = None
    gluetun_public_ip: str | None = None
    gluetun_country: str | None = None
    gluetun_warnings_count: int = 0
    routes_total: int = 0
    route_alerts_count: int = 0
    active_alerts: int = 0
    last_updated: str
    integrations: IntegrationStatus = Field(default_factory=IntegrationStatus)


class PortCheckResponse(BaseModel):
    port: int
    available: bool
    conflicts: list[PortBinding] = Field(default_factory=list)
    next_free_port: int | None = None
    suggest_range_start: int
    suggest_range_end: int


class RefreshResponse(BaseModel):
    status: str = "ok"
    refreshed_at: str
