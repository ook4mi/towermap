export interface PortBinding {
  host_ip: string;
  host_port: number;
  container_port: number;
  protocol: string;
  container_name: string;
  stack_name: string | null;
  via_gluetun: boolean;
  host_network: boolean;
  comment: string | null;
}

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  stack_name: string | null;
  service_name: string | null;
  compose_file: string | null;
  state: string;
  health: string | null;
  started_at: string | null;
  network_mode: string;
  gluetun_attached: boolean;
  ports: PortBinding[];
}

export interface GluetunOverview {
  container_state: string;
  container_id: string | null;
  started_at: string | null;
  vpn_status: string | null;
  public_ip: string | null;
  country: string | null;
  region: string | null;
  organization: string | null;
  configured: boolean;
  reachable: boolean;
  attached_containers: ContainerInfo[];
  published_ports: PortBinding[];
  warnings: string[];
}

export type RouteStatus =
  | "ok"
  | "orphan_dns"
  | "orphan_proxy"
  | "target_down"
  | "external";

export interface RouteEntry {
  domain: string;
  dns_record_type: string | null;
  dns_target: string | null;
  proxy_enabled: boolean | null;
  proxy_target: string | null;
  ssl_enabled: boolean;
  matched_container: string | null;
  status: RouteStatus;
}

export interface IntegrationStatus {
  docker: string;
  gluetun: string;
  npm: string;
  dns: string;
}

export interface OverviewResponse {
  mode: "mock" | "live";
  total_stacks: number;
  total_containers: number;
  running_containers: number;
  stopped_containers: number;
  unhealthy_containers: number;
  used_ports_count: number;
  gluetun_attached_count: number;
  gluetun_vpn_status: string | null;
  gluetun_public_ip: string | null;
  gluetun_country: string | null;
  gluetun_warnings_count: number;
  routes_total: number;
  route_alerts_count: number;
  active_alerts: number;
  last_updated: string;
  integrations: IntegrationStatus;
}

export interface PortCheckResponse {
  port: number;
  available: boolean;
  conflicts: PortBinding[];
  next_free_port: number | null;
  suggest_range_start: number;
  suggest_range_end: number;
}

export interface RefreshResponse {
  status: string;
  refreshed_at: string;
}
