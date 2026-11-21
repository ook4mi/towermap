import {
  ArrowRight,
  ExternalLink,
  Info,
  Lock,
  LockOpen,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { IntegrationStatus, RouteEntry, RouteStatus } from "../api/types";

interface RoutesViewProps {
  routes: RouteEntry[];
  integrations: IntegrationStatus | undefined;
  isLoading: boolean;
}

const STATUS_META: Record<
  RouteStatus,
  { label: string; badgeClass: string; description: string }
> = {
  ok: {
    label: "OK",
    badgeClass:
      "bg-emerald-500/10 text-emerald-700 ring-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-300",
    description: "DNS, NPM proxy host, and target container are all healthy.",
  },
  target_down: {
    label: "Target Down",
    badgeClass:
      "bg-rose-500/10 text-rose-700 ring-rose-500/35 dark:bg-rose-500/15 dark:text-rose-300",
    description: "Proxy host exists, but target container is stopped, disabled, or unbound.",
  },
  orphan_proxy: {
    label: "Orphan Proxy",
    badgeClass:
      "bg-amber-500/10 text-amber-800 ring-amber-500/35 dark:bg-amber-500/15 dark:text-amber-300",
    description: "Configured in NPM without a matching DNS record in Technitium.",
  },
  orphan_dns: {
    label: "DNS Only",
    badgeClass:
      "bg-amber-500/10 text-amber-800 ring-amber-500/30 dark:text-amber-200",
    description: "DNS points to tower, but no NPM reverse proxy host matches this domain.",
  },
  external: {
    label: "External",
    badgeClass:
      "bg-sky-500/10 text-sky-700 ring-sky-500/30 dark:bg-sky-500/15 dark:text-sky-300",
    description: "Routes to another LAN or external host outside tower's Docker containers.",
  },
};

export function RoutesView({ routes, integrations, isLoading }: RoutesViewProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<RouteStatus | "all">("all");

  const statusCounts = useMemo(() => {
    const counts: Record<RouteStatus, number> = {
      ok: 0,
      target_down: 0,
      orphan_proxy: 0,
      orphan_dns: 0,
      external: 0,
    };
    for (const r of routes) {
      counts[r.status] += 1;
    }
    return counts;
  }, [routes]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return routes.filter((route) => {
      if (statusFilter !== "all" && route.status !== statusFilter) return false;
      if (!q) return true;
      return (
        route.domain.toLowerCase().includes(q) ||
        (route.dns_target ?? "").toLowerCase().includes(q) ||
        (route.proxy_target ?? "").toLowerCase().includes(q) ||
        (route.matched_container ?? "").toLowerCase().includes(q)
      );
    });
  }, [routes, search, statusFilter]);

  const missingIntegrations =
    integrations &&
    (integrations.npm === "unconfigured" ||
      integrations.dns === "unconfigured" ||
      integrations.npm === "error" ||
      integrations.dns === "error");

  return (
    <div className="space-y-4">
      {missingIntegrations && (
        <div className="flex items-start gap-2.5 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-xs text-sky-900 dark:text-sky-200">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400" />
          <div>
            <strong>Partial integration status:</strong> Technitium DNS is{" "}
            <span className="font-mono">{integrations.dns}</span> and Nginx Proxy Manager is{" "}
            <span className="font-mono">{integrations.npm}</span>. Configure{" "}
            <span className="font-mono">TECHNITIUM_*</span> and{" "}
            <span className="font-mono">NPM_*</span> environment variables for full end-to-end
            route correlation.
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs dark:border-slate-800/80 dark:bg-slate-900/60 dark:shadow-none">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search domain, DNS target, proxy target, or container..."
            className="w-full rounded-lg border border-slate-300 bg-slate-50 py-2 pr-3 pl-9 text-sm text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:bg-white focus:outline-none dark:border-slate-700/80 dark:bg-slate-950 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:bg-slate-950"
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <FilterChip
            active={statusFilter === "all"}
            label={`All (${routes.length})`}
            onClick={() => setStatusFilter("all")}
          />
          {(
            ["ok", "target_down", "orphan_proxy", "orphan_dns", "external"] as const
          ).map((status) => (
            <FilterChip
              key={status}
              active={statusFilter === status}
              label={`${STATUS_META[status].label} (${statusCounts[status]})`}
              onClick={() => setStatusFilter(status)}
            />
          ))}
        </div>
      </div>

      {/* Routes Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-xs dark:border-slate-800/80 dark:bg-slate-900/50 dark:shadow-none">
        {isLoading ? (
          <div className="p-10 text-center text-sm text-slate-500 dark:text-slate-400">
            Correlating DNS, Nginx Proxy Manager, and Docker containers...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-500 dark:text-slate-400">
            No routes match the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm dark:divide-slate-800/80">
              <thead className="bg-slate-100/80 text-xs uppercase tracking-wider text-slate-600 dark:bg-slate-900/90 dark:text-slate-400">
                <tr>
                  <th className="px-4 py-3 font-medium">Domain</th>
                  <th className="px-4 py-3 font-medium">Technitium DNS</th>
                  <th className="px-4 py-3 font-medium">NPM Proxy Target</th>
                  <th className="px-4 py-3 font-medium">Docker Container</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/70 dark:divide-slate-800/60">
                {filtered.map((route) => {
                  const meta = STATUS_META[route.status];
                  const href = `${route.ssl_enabled ? "https" : "http"}://${route.domain}`;
                  return (
                    <tr
                      key={route.domain}
                      className="transition hover:bg-slate-50 dark:hover:bg-slate-800/30"
                    >
                      <td className="px-4 py-3">
                        <a
                          href={href}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 font-mono text-sm font-medium text-sky-700 hover:text-sky-600 hover:underline dark:text-sky-300 dark:hover:text-sky-200"
                        >
                          <span>{route.domain}</span>
                          <ExternalLink className="h-3 w-3 opacity-60" />
                        </a>
                      </td>

                      <td className="px-4 py-3">
                        {route.dns_target ? (
                          <div className="flex items-center gap-2 font-mono text-xs">
                            <span className="rounded bg-slate-200/80 px-1.5 py-0.5 text-[11px] text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                              {route.dns_record_type}
                            </span>
                            <span className="text-slate-700 dark:text-slate-300">
                              {route.dns_target}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 dark:text-slate-500">
                            Missing in DNS
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        {route.proxy_target ? (
                          <div className="flex items-center gap-2 font-mono text-xs">
                            {route.ssl_enabled ? (
                              <span title="SSL Enabled">
                                <Lock className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                              </span>
                            ) : (
                              <span title="No SSL Certificate">
                                <LockOpen className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
                              </span>
                            )}
                            <span
                              className={
                                route.proxy_enabled === false
                                  ? "text-slate-400 line-through dark:text-slate-500"
                                  : "text-slate-800 dark:text-slate-200"
                              }
                            >
                              {route.proxy_target}
                            </span>
                            {route.proxy_enabled === false && (
                              <span className="rounded bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">
                                disabled
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 dark:text-slate-500">
                            No NPM host
                          </span>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        {route.matched_container ? (
                          <div className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-800 dark:text-slate-200">
                            <ArrowRight className="h-3 w-3 text-slate-400 dark:text-slate-500" />
                            <span>{route.matched_container}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 dark:text-slate-500">—</span>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        <span
                          title={meta.description}
                          className={`inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-medium ring-1 ${meta.badgeClass}`}
                        >
                          {meta.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
        active
          ? "bg-sky-500/15 text-sky-700 ring-1 ring-sky-500/40 dark:bg-sky-500/20 dark:text-sky-300"
          : "bg-slate-100 text-slate-600 ring-1 ring-slate-200 hover:text-slate-900 dark:bg-slate-950 dark:text-slate-400 dark:ring-slate-800 dark:hover:text-slate-200"
      }`}
    >
      {label}
    </button>
  );
}
