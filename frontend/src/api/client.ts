import type {
  ContainerInfo,
  GluetunOverview,
  OverviewResponse,
  PortBinding,
  PortCheckResponse,
  RefreshResponse,
  RouteEntry,
} from "./types";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`API error ${response.status}: ${detail || response.statusText}`);
  }

  return (await response.json()) as T;
}

export const apiClient = {
  getOverview: () => fetchJson<OverviewResponse>("/api/overview"),

  getContainers: (params?: {
    stack?: string;
    state?: string;
    gluetun_only?: boolean;
    q?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.stack) search.set("stack", params.stack);
    if (params?.state) search.set("state", params.state);
    if (params?.gluetun_only) search.set("gluetun_only", "true");
    if (params?.q) search.set("q", params.q);
    const qs = search.toString();
    return fetchJson<ContainerInfo[]>(`/api/containers${qs ? `?${qs}` : ""}`);
  },

  getPorts: (params?: { protocol?: "tcp" | "udp"; q?: string }) => {
    const search = new URLSearchParams();
    if (params?.protocol) search.set("protocol", params.protocol);
    if (params?.q) search.set("q", params.q);
    const qs = search.toString();
    return fetchJson<PortBinding[]>(`/api/ports${qs ? `?${qs}` : ""}`);
  },

  checkPort: (port: number) =>
    fetchJson<PortCheckResponse>(`/api/ports/check?port=${encodeURIComponent(port)}`),

  getGluetun: () => fetchJson<GluetunOverview>("/api/gluetun"),

  getRoutes: (params?: { status?: string; q?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.q) search.set("q", params.q);
    const qs = search.toString();
    return fetchJson<RouteEntry[]>(`/api/routes${qs ? `?${qs}` : ""}`);
  },

  refreshCache: () =>
    fetchJson<RefreshResponse>("/api/cache/refresh", { method: "POST" }),
};
