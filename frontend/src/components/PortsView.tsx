import {
  ArrowUpDown,
  CheckCircle2,
  Network,
  Search,
  Shield,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { PortBinding } from "../api/types";
import { usePortCheck } from "../hooks/useTowerMap";

interface PortsViewProps {
  ports: PortBinding[];
  isLoading: boolean;
}

type SortKey = "host_port" | "container_name" | "stack_name" | "protocol";

export function PortsView({ ports, isLoading }: PortsViewProps) {
  const [portInput, setPortInput] = useState("4010");
  const parsedPort = useMemo(() => {
    const n = Number.parseInt(portInput, 10);
    return Number.isInteger(n) && n >= 1 && n <= 65535 ? n : null;
  }, [portInput]);

  const { data: portCheck, isFetching: checkingPort } = usePortCheck(parsedPort);

  const [search, setSearch] = useState("");
  const [protocolFilter, setProtocolFilter] = useState<"all" | "tcp" | "udp">("all");
  const [routingFilter, setRoutingFilter] = useState<"all" | "gluetun" | "host">("all");
  const [sortKey, setSortKey] = useState<SortKey>("host_port");
  const [sortAsc, setSortAsc] = useState(true);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((prev) => !prev);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const filteredPorts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = ports.filter((p) => {
      if (protocolFilter !== "all" && p.protocol.toLowerCase() !== protocolFilter) {
        return false;
      }
      if (routingFilter === "gluetun" && !p.via_gluetun) return false;
      if (routingFilter === "host" && !p.host_network) return false;
      if (!q) return true;
      return (
        String(p.host_port).includes(q) ||
        String(p.container_port).includes(q) ||
        p.container_name.toLowerCase().includes(q) ||
        (p.stack_name ?? "").toLowerCase().includes(q) ||
        p.host_ip.toLowerCase().includes(q) ||
        (p.comment ?? "").toLowerCase().includes(q)
      );
    });

    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "host_port") {
        cmp = a.host_port - b.host_port;
      } else if (sortKey === "container_name") {
        cmp = a.container_name.localeCompare(b.container_name);
      } else if (sortKey === "stack_name") {
        cmp = (a.stack_name ?? "").localeCompare(b.stack_name ?? "");
      } else {
        cmp = a.protocol.localeCompare(b.protocol);
      }
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [ports, search, protocolFilter, routingFilter, sortKey, sortAsc]);

  return (
    <div className="space-y-5">
      {/* Interactive Port Availability Checker */}
      <section className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Is Port X Free?
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Check host port availability before deploying a new Compose stack (including
              ports bound indirectly via <span className="font-mono text-cyan-300">gluetun</span>).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="port-check-input" className="text-xs font-medium text-slate-400">
                Port
              </label>
              <input
                id="port-check-input"
                type="number"
                min={1}
                max={65535}
                value={portInput}
                onChange={(e) => setPortInput(e.target.value)}
                className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100 focus:border-sky-500 focus:outline-none"
                placeholder="4010"
              />
            </div>

            {portCheck?.next_free_port && (
              <button
                type="button"
                onClick={() => setPortInput(String(portCheck.next_free_port))}
                className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/15 px-3 py-2 text-xs font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/25"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>
                  Next free ({portCheck.suggest_range_start}–{portCheck.suggest_range_end}):{" "}
                  <strong className="font-mono">{portCheck.next_free_port}</strong>
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Verdict Banner */}
        <div className="mt-4">
          {parsedPort === null ? (
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 px-4 py-3 text-xs text-slate-400">
              Enter a valid TCP/UDP port number between <span className="font-mono">1</span> and{" "}
              <span className="font-mono">65535</span>.
            </div>
          ) : checkingPort && !portCheck ? (
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 px-4 py-3 text-xs text-slate-400">
              Checking port {parsedPort}...
            </div>
          ) : portCheck ? (
            portCheck.available ? (
              <div className="flex items-center gap-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                <span>
                  Port <strong className="font-mono">:{portCheck.port}</strong> is{" "}
                  <strong>available</strong> on <span className="font-mono">tower</span>.
                </span>
              </div>
            ) : (
              <div className="flex flex-col gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                <div className="flex items-center gap-2.5">
                  <XCircle className="h-4 w-4 shrink-0 text-rose-400" />
                  <span>
                    Port <strong className="font-mono">:{portCheck.port}</strong> is already bound
                    by {portCheck.conflicts.length}{" "}
                    {portCheck.conflicts.length === 1 ? "binding" : "bindings"}:
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 pl-6">
                  {portCheck.conflicts.map((conflict) => (
                    <span
                      key={`${conflict.host_ip}-${conflict.protocol}-${conflict.container_name}`}
                      className="rounded-md bg-rose-950/80 px-2.5 py-1 font-mono text-xs text-rose-200 ring-1 ring-rose-500/30"
                    >
                      {conflict.container_name} ({conflict.stack_name ?? "standalone"}) ·{" "}
                      {conflict.host_ip}:{conflict.host_port}→{conflict.container_port}/
                      {conflict.protocol}
                      {conflict.via_gluetun ? " [via gluetun]" : ""}
                    </span>
                  ))}
                </div>
              </div>
            )
          ) : null}
        </div>
      </section>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-3.5">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter ports by number, container, stack, IP, or comment..."
            className="w-full rounded-lg border border-slate-700/80 bg-slate-950 py-2 pr-3 pl-9 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(["all", "tcp", "udp"] as const).map((proto) => (
            <button
              key={proto}
              type="button"
              onClick={() => setProtocolFilter(proto)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium uppercase transition ${
                protocolFilter === proto
                  ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40"
                  : "bg-slate-950 text-slate-400 ring-1 ring-slate-800 hover:text-slate-200"
              }`}
            >
              {proto}
            </button>
          ))}
          <button
            type="button"
            onClick={() =>
              setRoutingFilter((prev) => (prev === "gluetun" ? "all" : "gluetun"))
            }
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              routingFilter === "gluetun"
                ? "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/40"
                : "bg-slate-950 text-slate-400 ring-1 ring-slate-800 hover:text-slate-200"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            <span>via gluetun</span>
          </button>
          <button
            type="button"
            onClick={() =>
              setRoutingFilter((prev) => (prev === "host" ? "all" : "host"))
            }
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              routingFilter === "host"
                ? "bg-indigo-500/20 text-indigo-300 ring-1 ring-indigo-500/40"
                : "bg-slate-950 text-slate-400 ring-1 ring-slate-800 hover:text-slate-200"
            }`}
          >
            <Network className="h-3.5 w-3.5" />
            <span>host network</span>
          </button>
        </div>
      </div>

      {/* Port Registry Table */}
      <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/50">
        {isLoading ? (
          <div className="p-10 text-center text-sm text-slate-400">
            Loading port registry...
          </div>
        ) : filteredPorts.length === 0 ? (
          <div className="p-10 text-center text-sm text-slate-400">
            No bound ports match the current filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800/80 text-left text-sm">
              <thead className="bg-slate-900/90 text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <SortableTh
                    label="Host Port"
                    active={sortKey === "host_port"}
                    onClick={() => toggleSort("host_port")}
                  />
                  <th className="px-4 py-3 font-medium">Container Port</th>
                  <SortableTh
                    label="Proto"
                    active={sortKey === "protocol"}
                    onClick={() => toggleSort("protocol")}
                  />
                  <SortableTh
                    label="Container"
                    active={sortKey === "container_name"}
                    onClick={() => toggleSort("container_name")}
                  />
                  <SortableTh
                    label="Stack"
                    active={sortKey === "stack_name"}
                    onClick={() => toggleSort("stack_name")}
                  />
                  <th className="px-4 py-3 font-medium">Host IP</th>
                  <th className="px-4 py-3 font-medium">Routing</th>
                  <th className="px-4 py-3 font-medium">Comment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredPorts.map((binding) => (
                  <tr
                    key={`${binding.host_ip}-${binding.host_port}-${binding.protocol}-${binding.container_name}`}
                    className="transition hover:bg-slate-800/30"
                  >
                    <td className="px-4 py-3 font-mono font-semibold text-sky-300">
                      :{binding.host_port}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-300">
                      {binding.container_port}
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs uppercase text-slate-300">
                        {binding.protocol}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-100">
                      {binding.container_name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      {binding.stack_name ?? "standalone"}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      {binding.host_ip}
                    </td>
                    <td className="px-4 py-3">
                      {binding.via_gluetun ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-cyan-500/15 px-2 py-0.5 text-xs font-medium text-cyan-300 ring-1 ring-cyan-500/30">
                          <Shield className="h-3 w-3" />
                          via gluetun
                        </span>
                      ) : binding.host_network ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-indigo-500/15 px-2 py-0.5 text-xs font-medium text-indigo-300 ring-1 ring-indigo-500/30">
                          <Network className="h-3 w-3" />
                          host network
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500">direct</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-300">
                      {binding.comment ? (
                        <span>
                          <span className="mr-1 text-slate-500">#</span>
                          {binding.comment}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function SortableTh({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <th className="px-4 py-3 font-medium">
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 uppercase transition hover:text-slate-200 ${
          active ? "text-sky-300" : "text-slate-400"
        }`}
      >
        <span>{label}</span>
        <ArrowUpDown className="h-3 w-3" />
      </button>
    </th>
  );
}
