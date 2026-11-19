import {
  AlertTriangle,
  Box,
  Globe,
  Layers,
  Network,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { OverviewResponse } from "../api/types";

export type TabKey = "containers" | "ports" | "gluetun" | "routes";

interface HeaderBarProps {
  overview: OverviewResponse | undefined;
  isRefreshing: boolean;
  onRefresh: () => void;
  onSelectTab: (tab: TabKey) => void;
}

function formatTime(iso: string | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function HeaderBar({
  overview,
  isRefreshing,
  onRefresh,
  onSelectTab,
}: HeaderBarProps) {
  const vpnHealthy =
    overview?.gluetun_vpn_status?.toLowerCase() === "running" &&
    (overview?.gluetun_warnings_count ?? 0) === 0;
  const vpnWarning =
    (overview?.gluetun_warnings_count ?? 0) > 0 ||
    (overview?.gluetun_vpn_status !== null &&
      overview?.gluetun_vpn_status !== undefined &&
      overview.gluetun_vpn_status.toLowerCase() !== "running");

  return (
    <header className="border-b border-slate-800/80 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
        {/* Top Row: Brand, Mode, Live Status Pills, Refresh */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400 ring-1 ring-sky-500/30">
              <Server className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-semibold tracking-tight text-slate-100">
                  TowerMap
                </h1>
                {overview && (
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${
                      overview.mode === "mock"
                        ? "bg-amber-500/10 text-amber-300 ring-amber-500/30"
                        : "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        overview.mode === "mock" ? "bg-amber-400" : "bg-emerald-400"
                      }`}
                    />
                    {overview.mode === "mock" ? "MOCK MODE" : "LIVE"}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">
                Read-only infrastructure map for{" "}
                <span className="font-mono text-slate-300">tower</span> · Updated{" "}
                <span className="font-mono">{formatTime(overview?.last_updated)}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Gluetun VPN Pill */}
            <button
              type="button"
              onClick={() => onSelectTab("gluetun")}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition hover:brightness-110 ${
                vpnHealthy
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                  : vpnWarning
                    ? "bg-amber-500/10 text-amber-300 ring-amber-500/30"
                    : "bg-slate-900 text-slate-300 ring-slate-700"
              }`}
            >
              {vpnHealthy ? (
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
              ) : vpnWarning ? (
                <ShieldAlert className="h-4 w-4 text-amber-400" />
              ) : (
                <Shield className="h-4 w-4 text-slate-400" />
              )}
              <span>
                VPN:{" "}
                <span className="font-mono">
                  {overview?.gluetun_public_ip ?? overview?.gluetun_vpn_status ?? "—"}
                </span>
                {overview?.gluetun_country ? ` (${overview.gluetun_country})` : ""}
              </span>
              {(overview?.gluetun_warnings_count ?? 0) > 0 && (
                <span className="rounded bg-amber-500/20 px-1.5 py-0.5 font-mono text-[11px] text-amber-200">
                  {overview?.gluetun_warnings_count} warn
                </span>
              )}
            </button>

            {/* Route Alerts Badge */}
            <button
              type="button"
              onClick={() => onSelectTab("routes")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition hover:brightness-110 ${
                (overview?.route_alerts_count ?? 0) > 0
                  ? "bg-rose-500/10 text-rose-300 ring-rose-500/30"
                  : "bg-slate-900 text-slate-300 ring-slate-700"
              }`}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>
                {overview?.route_alerts_count ?? 0} Route{" "}
                {overview?.route_alerts_count === 1 ? "Alert" : "Alerts"}
              </span>
            </button>

            {/* Manual Refresh Button */}
            <button
              type="button"
              onClick={onRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/25 disabled:opacity-60"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
              />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Summary KPI Strip */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <SummaryCard
            icon={<Layers className="h-4 w-4 text-sky-400" />}
            label="Compose Stacks"
            value={overview?.total_stacks ?? "—"}
            subtext="Active projects"
            onClick={() => onSelectTab("containers")}
          />
          <SummaryCard
            icon={<Box className="h-4 w-4 text-emerald-400" />}
            label="Containers"
            value={
              overview
                ? `${overview.running_containers}/${overview.total_containers}`
                : "—"
            }
            subtext={
              overview
                ? `${overview.stopped_containers} stopped · ${overview.unhealthy_containers} unhealthy`
                : "Loading..."
            }
            onClick={() => onSelectTab("containers")}
          />
          <SummaryCard
            icon={<Network className="h-4 w-4 text-violet-400" />}
            label="Bound Host Ports"
            value={overview?.used_ports_count ?? "—"}
            subtext="TCP & UDP bindings"
            onClick={() => onSelectTab("ports")}
          />
          <SummaryCard
            icon={<Shield className="h-4 w-4 text-cyan-400" />}
            label="Gluetun Attached"
            value={overview?.gluetun_attached_count ?? "—"}
            subtext={
              overview && overview.gluetun_warnings_count > 0
                ? `${overview.gluetun_warnings_count} topology warning(s)`
                : "Sharing VPN namespace"
            }
            highlight={Boolean(overview && overview.gluetun_warnings_count > 0)}
            onClick={() => onSelectTab("gluetun")}
          />
          <SummaryCard
            icon={<Globe className="h-4 w-4 text-amber-400" />}
            label="Domain Routes"
            value={overview?.routes_total ?? "—"}
            subtext={
              overview
                ? overview.route_alerts_count > 0
                  ? `${overview.route_alerts_count} drift issue(s)`
                  : "All routes synced"
                : "Loading..."
            }
            highlight={Boolean(overview && overview.route_alerts_count > 0)}
            onClick={() => onSelectTab("routes")}
          />
        </div>
      </div>
    </header>
  );
}

interface SummaryCardProps {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  subtext: string;
  highlight?: boolean;
  onClick?: () => void;
}

function SummaryCard({
  icon,
  label,
  value,
  subtext,
  highlight = false,
  onClick,
}: SummaryCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group flex flex-col items-start rounded-xl border p-3.5 text-left transition ${
        highlight
          ? "border-amber-500/35 bg-amber-500/5 hover:border-amber-500/50"
          : "border-slate-800/80 bg-slate-900/60 hover:border-slate-700"
      }`}
    >
      <div className="flex w-full items-center justify-between">
        <span className="text-xs font-medium text-slate-400">{label}</span>
        {icon}
      </div>
      <div className="mt-1.5 font-mono text-2xl font-semibold tracking-tight text-slate-100">
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-slate-400">{subtext}</div>
    </button>
  );
}
