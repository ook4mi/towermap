import { AlertCircle, Box, Globe, Network, Shield } from "lucide-react";
import { useState } from "react";
import { ContainersView } from "./components/ContainersView";
import { GluetunView } from "./components/GluetunView";
import { HeaderBar, type TabKey } from "./components/HeaderBar";
import { PortsView } from "./components/PortsView";
import { RoutesView } from "./components/RoutesView";
import { useTheme } from "./hooks/useTheme";
import {
  useContainers,
  useGluetun,
  useOverview,
  usePorts,
  useRefreshCache,
  useRoutes,
} from "./hooks/useTowerMap";

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "containers", label: "Stacks & Containers", icon: <Box className="h-4 w-4" /> },
  { key: "ports", label: "Port Registry", icon: <Network className="h-4 w-4" /> },
  { key: "gluetun", label: "Gluetun Topology", icon: <Shield className="h-4 w-4" /> },
  { key: "routes", label: "Routes", icon: <Globe className="h-4 w-4" /> },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("containers");
  const { theme, setTheme } = useTheme();

  const overviewQuery = useOverview();
  const containersQuery = useContainers();
  const portsQuery = usePorts();
  const gluetunQuery = useGluetun();
  const routesQuery = useRoutes();
  const refreshMutation = useRefreshCache();

  const apiError =
    overviewQuery.error ||
    containersQuery.error ||
    portsQuery.error ||
    gluetunQuery.error ||
    routesQuery.error;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <HeaderBar
        overview={overviewQuery.data}
        isRefreshing={refreshMutation.isPending || overviewQuery.isFetching}
        onRefresh={() => refreshMutation.mutate()}
        onSelectTab={setActiveTab}
        theme={theme}
        onChangeTheme={setTheme}
      />

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {apiError && (
          <div className="mb-5 flex items-center gap-2.5 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-800 dark:text-rose-200">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
            <span>
              Failed to reach TowerMap backend API:{" "}
              <span className="font-mono">{(apiError as Error).message}</span>
            </span>
          </div>
        )}

        {/* Navigation Tabs */}
        <nav
          aria-label="Primary views"
          className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3 dark:border-slate-800/80"
        >
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            const badgeCount =
              tab.key === "gluetun"
                ? overviewQuery.data?.gluetun_warnings_count
                : tab.key === "routes"
                  ? overviewQuery.data?.route_alerts_count
                  : undefined;

            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-sky-500/15 text-sky-700 ring-1 ring-sky-500/40 dark:text-sky-300"
                    : "text-slate-600 hover:bg-slate-200/70 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {badgeCount !== undefined && badgeCount > 0 && (
                  <span className="rounded-full bg-amber-500/20 px-1.5 py-0.5 font-mono text-[11px] text-amber-800 dark:text-amber-300">
                    {badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Active Tab Content */}
        {activeTab === "containers" && (
          <ContainersView
            containers={containersQuery.data ?? []}
            isLoading={containersQuery.isLoading}
          />
        )}
        {activeTab === "ports" && (
          <PortsView
            ports={portsQuery.data ?? []}
            isLoading={portsQuery.isLoading}
          />
        )}
        {activeTab === "gluetun" && (
          <GluetunView
            gluetun={gluetunQuery.data}
            isLoading={gluetunQuery.isLoading}
          />
        )}
        {activeTab === "routes" && (
          <RoutesView
            routes={routesQuery.data ?? []}
            integrations={overviewQuery.data?.integrations}
            isLoading={routesQuery.isLoading}
          />
        )}
      </main>
    </div>
  );
}
