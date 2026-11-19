import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "./client";

describe("apiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds query parameters for getContainers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await apiClient.getContainers({
      stack: "media-vpn",
      state: "running",
      gluetun_only: true,
      q: "sonarr",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/containers?stack=media-vpn&state=running&gluetun_only=true&q=sonarr",
      expect.objectContaining({
        headers: expect.objectContaining({ Accept: "application/json" }),
      }),
    );
  });

  it("calls POST /api/cache/refresh on refreshCache", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok", refreshed_at: "2026-11-19T22:00:00Z" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await apiClient.refreshCache();
    expect(res.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cache/refresh",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
