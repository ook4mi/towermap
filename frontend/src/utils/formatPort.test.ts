import { describe, expect, it } from "vitest";
import type { PortBinding } from "../api/types";
import { deduplicatePorts, formatComposePort } from "./formatPort";

const basePort: PortBinding = {
  host_ip: "0.0.0.0",
  host_port: 9696,
  container_port: 9696,
  protocol: "tcp",
  container_name: "gluetun",
  stack_name: "media-vpn",
  via_gluetun: true,
  host_network: false,
  comment: "Prowlarr",
};

describe("formatComposePort", () => {
  it("formats standard TCP ports cleanly", () => {
    expect(formatComposePort(basePort)).toBe("9696:9696");
  });

  it("includes /udp for UDP ports and IP prefix for explicit host IPs", () => {
    expect(
      formatComposePort({
        ...basePort,
        host_ip: "127.0.0.1",
        host_port: 53,
        container_port: 53,
        protocol: "udp",
      }),
    ).toBe("127.0.0.1:53:53/udp");
  });
});

describe("deduplicatePorts", () => {
  it("collapses dual-stack 0.0.0.0 and :: bindings into a single entry", () => {
    const result = deduplicatePorts([
      { ...basePort, host_ip: "::", comment: null },
      { ...basePort, host_ip: "0.0.0.0", comment: "Prowlarr" },
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].host_ip).toBe("0.0.0.0");
    expect(result[0].comment).toBe("Prowlarr");
  });
});
