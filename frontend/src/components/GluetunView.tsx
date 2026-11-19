import {
  AlertTriangle,
  ArrowRight,
  Clock,
  Globe,
  Network,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { GluetunOverview } from "../api/types";

interface GluetunViewProps {
  gluetun: GluetunOverview | undefined;
  isLoading: boolean;
}

function formatStarted(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

export function GluetunView({ gluetun, isLoading }: GluetunViewProps) {
  if (isLoading || !gluetun) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-sm text-slate-400">
        Loading Gluetun VPN topology...
      </div>
    );
  }

  const vpnRunning = gluetun.vpn_status?.toLowerCase() === "running";
  const isHealthy =
    gluetun.container_state === "running" &&
    (!gluetun.configured || (gluetun.reachable && vpnRunning)) &&
    gluetun.warnings.length === 0;

  return (
    <div className="space-y-5">
      {/* VPN Status Banner */}
      <section
        className={`rounded-xl border p-5 ${
          isHealthy
            ? "border-emerald-500/30 bg-emerald-500/5"
            : gluetun.warnings.length > 0
              ? "border-amber-500/35 bg-amber-500/5"
              : "border-slate-800 bg-slate-900/60"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={`mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl ring-1 ${
                isHealthy
                  ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30"
                  : gluetun.warnings.length > 0
                    ? "bg-amber-500/15 text-amber-400 ring-amber-500/30"
                    : "bg-slate-800 text-slate-400 ring-slate-700"
              }`}
            >
              {isHealthy ? (
                <ShieldCheck className="h-5 w-5" />
              ) : gluetun.warnings.length > 0 ? (
                <ShieldAlert className="h-5 w-5" />
              ) : (
                <Shield className="h-5 w-5" />
              )}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold text-slate-100">
                  Gluetun VPN Gateway
                </h2>
                <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-xs text-slate-300 ring-1 ring-slate-700">
                  container: {gluetun.container_state}
                </span>
                {gluetun.vpn_status && (
                  <span
                    className={`rounded-md px-2 py-0.5 font-mono text-xs ring-1 ${
                      vpnRunning
                        ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                        : "bg-rose-500/15 text-rose-300 ring-rose-500/30"
                    }`}
                  >
                    tunnel: {gluetun.vpn_status}
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {gluetun.attached_containers.length} container(s) share{" "}
                <span className="font-mono text-cyan-300">network_mode: service:gluetun</span>.
                Restarting <span className="font-mono">gluetun</span> requires recreating attached
                containers.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <InfoPill
              icon={<Globe className="h-3.5 w-3.5 text-cyan-400" />}
              label="VPN Public IP"
              value={gluetun.public_ip ?? (gluetun.configured ? "Unavailable" : "Not configured")}
            />
            <InfoPill
              icon={<Shield className="h-3.5 w-3.5 text-sky-400" />}
              label="Exit Location"
              value={
                gluetun.country
                  ? [gluetun.country, gluetun.region].filter(Boolean).join(", ")
                  : "—"
              }
            />
            <InfoPill
              icon={<Clock className="h-3.5 w-3.5 text-slate-400" />}
              label="Started At"
              value={formatStarted(gluetun.started_at)}
            />
          </div>
        </div>

        {gluetun.organization && (
          <div className="mt-3 text-xs text-slate-400">
            VPN Provider / Org:{" "}
            <span className="font-mono text-slate-300">{gluetun.organization}</span>
          </div>
        )}
      </section>

      {/* Blast-Radius Warnings */}
      {gluetun.warnings.length > 0 && (
        <section className="rounded-xl border border-amber-500/35 bg-amber-500/10 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-amber-200">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <span>Blast-Radius &amp; Health Warnings ({gluetun.warnings.length})</span>
          </div>
          <ul className="mt-2.5 space-y-1.5 pl-6 text-xs text-amber-100/90 list-disc">
            {gluetun.warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Topology Grid: Attached Containers & Published Ports */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* Attached Containers */}
        <section className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/50 lg:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-900/80 px-4 py-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-slate-100">
                Attached Containers ({gluetun.attached_containers.length})
              </h3>
            </div>
            <span className="font-mono text-xs text-slate-400">
              gluetun ({gluetun.container_id ?? "missing"})
            </span>
          </div>

          {gluetun.attached_containers.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-400">
              No containers are currently attached to gluetun&apos;s network namespace.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/70">
              {gluetun.attached_containers.map((container) => (
                <div
                  key={container.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 transition hover:bg-slate-800/25"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-sm font-medium text-slate-100">
                        {container.name}
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-cyan-500/70" />
                      <span className="font-mono text-xs text-cyan-300">gluetun</span>
                      <span
                        className={`rounded px-2 py-0.5 text-[11px] font-medium ring-1 ${
                          container.state === "running"
                            ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                            : "bg-rose-500/15 text-rose-300 ring-rose-500/30"
                        }`}
                      >
                        {container.state}
                      </span>
                      {container.health && container.health !== "none" && (
                        <span
                          className={`rounded px-2 py-0.5 text-[11px] font-medium ring-1 ${
                            container.health === "healthy"
                              ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25"
                              : "bg-rose-500/15 text-rose-300 ring-rose-500/35"
                          }`}
                        >
                          {container.health}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-xs text-slate-400">
                      <span>{container.image}</span>
                      <span className="text-slate-500">
                        started: {formatStarted(container.started_at)}
                      </span>
                    </div>
                  </div>

                  <span className="font-mono text-[11px] text-slate-500">
                    {container.network_mode.length > 26
                      ? `${container.network_mode.slice(0, 22)}...`
                      : container.network_mode}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Published Ports on Gluetun */}
        <section className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/50">
          <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-900/80 px-4 py-3">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-violet-400" />
              <h3 className="text-sm font-semibold text-slate-100">
                Exposed Ports ({gluetun.published_ports.length})
              </h3>
            </div>
          </div>

          {gluetun.published_ports.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-400">
              No host ports published on gluetun.
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60">
              {gluetun.published_ports.map((port) => (
                <div
                  key={`${port.host_ip}-${port.host_port}-${port.protocol}`}
                  className="flex items-center justify-between px-4 py-2.5 text-xs"
                >
                  <span className="font-mono font-semibold text-cyan-300">
                    :{port.host_port}
                  </span>
                  <span className="font-mono text-slate-400">
                    → {port.container_port}/{port.protocol}
                  </span>
                  <span className="font-mono text-slate-500">{port.host_ip}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function InfoPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800/80 bg-slate-950/70 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1 font-mono text-xs font-medium text-slate-100">{value}</div>
    </div>
  );
}
