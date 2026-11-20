import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  Network,
  Search,
  Shield,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { ContainerInfo, PortBinding } from "../api/types";

interface ContainersViewProps {
  containers: ContainerInfo[];
  isLoading: boolean;
}

type StateFilter = "all" | "running" | "stopped" | "unhealthy";

export function ContainersView({ containers, isLoading }: ContainersViewProps) {
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<StateFilter>("all");
  const [gluetunOnly, setGluetunOnly] = useState(false);
  const [collapsedStacks, setCollapsedStacks] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return containers.filter((c) => {
      if (stateFilter === "running" && c.state !== "running") return false;
      if (stateFilter === "stopped" && c.state === "running") return false;
      if (stateFilter === "unhealthy" && c.health !== "unhealthy") return false;
      if (gluetunOnly && !c.gluetun_attached) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        c.image.toLowerCase().includes(q) ||
        (c.stack_name ?? "standalone").toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q) ||
        c.ports.some(
          (p) =>
            String(p.host_port).includes(q) ||
            (p.comment ?? "").toLowerCase().includes(q),
        )
      );
    });
  }, [containers, search, stateFilter, gluetunOnly]);

  const groupedByStack = useMemo(() => {
    const map = new Map<string, ContainerInfo[]>();
    for (const container of filtered) {
      const key = container.stack_name ?? "standalone";
      const list = map.get(key) ?? [];
      list.push(container);
      map.set(key, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const toggleStack = (stack: string) => {
    setCollapsedStacks((prev) => ({ ...prev, [stack]: !prev[stack] }));
  };

  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-sm text-slate-400">
        Loading Docker stacks &amp; containers...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-3.5">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search container, stack, image, port, or comment..."
            className="w-full rounded-lg border border-slate-700/80 bg-slate-950 py-2 pr-3 pl-9 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {(["all", "running", "stopped", "unhealthy"] as const).map((filter) => (
            <button
              key={filter}
              type="button"
              onClick={() => setStateFilter(filter)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition ${
                stateFilter === filter
                  ? "bg-sky-500/20 text-sky-300 ring-1 ring-sky-500/40"
                  : "bg-slate-950 text-slate-400 ring-1 ring-slate-800 hover:text-slate-200"
              }`}
            >
              {filter}
            </button>
          ))}

          <button
            type="button"
            onClick={() => setGluetunOnly((prev) => !prev)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              gluetunOnly
                ? "bg-cyan-500/20 text-cyan-300 ring-1 ring-cyan-500/40"
                : "bg-slate-950 text-slate-400 ring-1 ring-slate-800 hover:text-slate-200"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            <span>Gluetun only</span>
          </button>
        </div>
      </div>

      {/* Grouped Stack Cards */}
      {groupedByStack.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
          No containers match the current filters.
        </div>
      ) : (
        <div className="space-y-4">
          {groupedByStack.map(([stackName, items]) => {
            const runningCount = items.filter((c) => c.state === "running").length;
            const composeFile = items.find((c) => c.compose_file)?.compose_file;
            const isCollapsed = Boolean(collapsedStacks[stackName]);

            return (
              <section
                key={stackName}
                className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/50"
              >
                <button
                  type="button"
                  onClick={() => toggleStack(stackName)}
                  className="flex w-full flex-wrap items-center justify-between gap-2 bg-slate-900/90 px-4 py-3 text-left transition hover:bg-slate-900"
                >
                  <div className="flex items-center gap-2.5">
                    {isCollapsed ? (
                      <ChevronRight className="h-4 w-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-slate-400" />
                    )}
                    <span className="font-mono text-sm font-semibold text-slate-100">
                      {stackName}
                    </span>
                    <span className="rounded-full bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                      {runningCount}/{items.length} running
                    </span>
                  </div>

                  {composeFile && (
                    <span
                      title={composeFile}
                      className="inline-flex max-w-md items-center gap-1.5 truncate font-mono text-xs text-slate-400"
                    >
                      <FileCode2 className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                      <span className="truncate">{composeFile}</span>
                    </span>
                  )}
                </button>

                {!isCollapsed && (
                  <div className="divide-y divide-slate-800/70">
                    {items.map((container) => (
                      <ContainerRow key={container.id} container={container} />
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ContainerRow({ container }: { container: ContainerInfo }) {
  const isHostNetwork = container.network_mode.toLowerCase() === "host";
  const hasRichPorts =
    container.ports.length > 3 ||
    container.ports.some((p) => Boolean(p.comment) || p.via_gluetun || p.host_network);

  return (
    <div className="px-4 py-3.5 transition hover:bg-slate-800/20">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-medium text-slate-100">
              {container.name}
            </span>
            <StateBadge state={container.state} />
            {container.health && container.health !== "none" && (
              <HealthBadge health={container.health} />
            )}
            {container.gluetun_attached && (
              <span className="inline-flex items-center gap-1 rounded-md bg-cyan-500/15 px-2 py-0.5 text-[11px] font-medium text-cyan-300 ring-1 ring-cyan-500/30">
                <Shield className="h-3 w-3" />
                via gluetun
              </span>
            )}
            {isHostNetwork && (
              <span className="inline-flex items-center gap-1 rounded-md bg-indigo-500/15 px-2 py-0.5 text-[11px] font-medium text-indigo-300 ring-1 ring-indigo-500/30">
                <Network className="h-3 w-3" />
                host network
              </span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
            <span className="truncate font-mono text-slate-400">
              {container.image}
            </span>
            <span className="font-mono text-slate-500">id:{container.id}</span>
          </div>
        </div>

        {/* Compact inline badges for simple 1–3 port containers without comments */}
        {!hasRichPorts && (
          <div className="flex flex-wrap items-center gap-1.5 lg:justify-end">
            {container.ports.length === 0 ? (
              <span className="text-xs text-slate-500">
                {container.gluetun_attached
                  ? "Ports published via gluetun"
                  : "No host ports"}
              </span>
            ) : (
              container.ports.map((port) => (
                <span
                  key={`${port.host_ip}-${port.host_port}-${port.protocol}`}
                  className="inline-flex items-center gap-1 rounded-md bg-slate-950 px-2 py-0.5 font-mono text-xs text-slate-200 ring-1 ring-slate-700"
                >
                  :{port.host_port}
                  <span className="text-slate-500">
                    →{port.container_port}/{port.protocol}
                  </span>
                </span>
              ))
            )}
          </div>
        )}
      </div>

      {/* Vertical structured port list for Gluetun, host-network, or commented/many ports */}
      {hasRichPorts && container.ports.length > 0 && (
        <PortListBlock ports={container.ports} />
      )}
    </div>
  );
}

function PortListBlock({ ports }: { ports: PortBinding[] }) {
  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-slate-800/80 bg-slate-950/60">
      <div className="divide-y divide-slate-800/60">
        {ports.map((port) => (
          <div
            key={`${port.host_ip}-${port.host_port}-${port.container_port}-${port.protocol}`}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-3 py-1.5 text-xs"
          >
            <div className="flex items-center gap-2.5 font-mono">
              <span
                className={`min-w-[4.5rem] font-semibold ${
                  port.via_gluetun
                    ? "text-cyan-300"
                    : port.host_network
                      ? "text-indigo-300"
                      : "text-sky-300"
                }`}
              >
                :{port.host_port}
              </span>
              <span className="text-slate-400">
                → {port.container_port}/{port.protocol}
              </span>
              {port.host_ip !== "0.0.0.0" && (
                <span className="text-slate-500">({port.host_ip})</span>
              )}
              {port.host_network && (
                <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 font-sans text-[10px] font-medium text-indigo-300 ring-1 ring-indigo-500/30">
                  host
                </span>
              )}
            </div>

            {port.comment ? (
              <span className="truncate font-mono text-xs text-slate-300">
                <span className="mr-1 text-slate-500">#</span>
                {port.comment}
              </span>
            ) : (
              <span className="text-[11px] text-slate-600">—</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const normalized = state.toLowerCase();
  const styles =
    normalized === "running"
      ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
      : normalized === "restarting"
        ? "bg-amber-500/15 text-amber-300 ring-amber-500/30"
        : "bg-rose-500/15 text-rose-300 ring-rose-500/30";
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${styles}`}
    >
      {normalized}
    </span>
  );
}

function HealthBadge({ health }: { health: string }) {
  const normalized = health.toLowerCase();
  const styles =
    normalized === "healthy"
      ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25"
      : normalized === "starting"
        ? "bg-amber-500/10 text-amber-300 ring-amber-500/25"
        : "bg-rose-500/15 text-rose-300 ring-rose-500/40";
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ${styles}`}
    >
      {normalized}
    </span>
  );
}
