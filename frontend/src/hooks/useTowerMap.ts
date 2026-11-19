import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export const queryKeys = {
  overview: ["overview"] as const,
  containers: ["containers"] as const,
  ports: ["ports"] as const,
  portCheck: (port: number) => ["port-check", port] as const,
  gluetun: ["gluetun"] as const,
  routes: ["routes"] as const,
};

export function useOverview() {
  return useQuery({
    queryKey: queryKeys.overview,
    queryFn: apiClient.getOverview,
    refetchInterval: 30_000,
  });
}

export function useContainers() {
  return useQuery({
    queryKey: queryKeys.containers,
    queryFn: () => apiClient.getContainers(),
    refetchInterval: 30_000,
  });
}

export function usePorts() {
  return useQuery({
    queryKey: queryKeys.ports,
    queryFn: () => apiClient.getPorts(),
    refetchInterval: 30_000,
  });
}

export function usePortCheck(port: number | null) {
  return useQuery({
    queryKey: queryKeys.portCheck(port ?? 0),
    queryFn: () => apiClient.checkPort(port!),
    enabled: port !== null && Number.isInteger(port) && port >= 1 && port <= 65535,
  });
}

export function useGluetun() {
  return useQuery({
    queryKey: queryKeys.gluetun,
    queryFn: apiClient.getGluetun,
    refetchInterval: 30_000,
  });
}

export function useRoutes() {
  return useQuery({
    queryKey: queryKeys.routes,
    queryFn: () => apiClient.getRoutes(),
    refetchInterval: 30_000,
  });
}

export function useRefreshCache() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: apiClient.refreshCache,
    onSuccess: async () => {
      await queryClient.invalidateQueries();
    },
  });
}
