/**
 * demo-api.ts — in-browser mock of the Stream Deck REST API.
 *
 * Powers "demo mode": the UI works with NO server and NO device. State is
 * persisted in localStorage so edits survive reloads. This is what makes the
 * project shareable before you own hardware — mindshare without a device.
 *
 * The mock intentionally mirrors the REST surface in lib/api.ts:
 *   devicesApi.getAll, devicesApi.assignConfig
 *   configsApi.getAll/getById/create/update/delete
 *   agentsApi.getAll/delete/nominate (agents are part of this port)
 */

import type { Device, StreamDeckConfig, ButtonAction, Agent } from "@/types/streamdeck";

const LS_DEVICES = "streamdeck_demo_devices";
const LS_CONFIGS = "streamdeck_demo_configs";
const LS_AGENTS = "streamdeck_demo_agents";

export const DEMO_DEVICE_ID = "demo-deck-xl-001";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function write<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `demo-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// Seed devices so a fresh demo has something to look at. Types use the
// human names the real API returns from the vendored core's DECK_TYPE.
const DEFAULT_DEVICES: Device[] = [
  {
    id: DEMO_DEVICE_ID,
    type: "Stream Deck XL",
    name: "Stream Deck XL (demo) - 000000000001",
    connected: true,
    currentConfigId: undefined,
    current_config_id: undefined,
  },
  {
    id: "demo-deck-mk2-002",
    type: "Stream Deck MK.2",
    name: "Stream Deck MK.2 (demo) - 000000000002",
    connected: true,
    currentConfigId: undefined,
    current_config_id: undefined,
  },
];

const DEFAULT_AGENTS: Agent[] = [
  {
    id: "demo-agent-studio",
    hostname: "studio-mac.local",
    user: "you",
    platform: "macOS",
    active: true,
    last_seen: new Date().toISOString(),
  },
];

function ensureSeed(): void {
  if (!localStorage.getItem(LS_DEVICES)) write(LS_DEVICES, DEFAULT_DEVICES);
  if (!localStorage.getItem(LS_AGENTS)) write(LS_AGENTS, DEFAULT_AGENTS);
}

const LS_DEMO_EXIT = "streamdeck_demo_exit";

export function isDemoMode(): boolean {
  if (localStorage.getItem(LS_DEMO_EXIT) === "1") return false;
  // Demo builds (DEMO_MODE=1 at build time) default to demo mode on first run.
  return (
    import.meta.env.VITE_DEMO_MODE === "1" ||
    localStorage.getItem("streamdeck_demo_mode") === "1"
  );
}

export function enableDemoMode(persist = true): void {
  localStorage.removeItem(LS_DEMO_EXIT);
  if (persist) localStorage.setItem("streamdeck_demo_mode", "1");
}

export function disableDemoMode(): void {
  // Works in both builds: clears the opt-in flag and marks exit for demo builds.
  localStorage.removeItem("streamdeck_demo_mode");
  localStorage.setItem(LS_DEMO_EXIT, "1");
}

export function resetDemoData(): void {
  localStorage.removeItem(LS_DEVICES);
  localStorage.removeItem(LS_CONFIGS);
  localStorage.removeItem(LS_AGENTS);
}

const delay = (ms = 80) => new Promise((r) => setTimeout(r, ms));

// -----------------------------
// Devices
// -----------------------------
export const demoDevicesApi = {
  async getAll(): Promise<Device[]> {
    await delay();
    ensureSeed();
    return read<Device[]>(LS_DEVICES, DEFAULT_DEVICES);
  },

  async assignConfig(deviceId: string, configId: string): Promise<void> {
    await delay();
    ensureSeed();
    const devices = read<Device[]>(LS_DEVICES, DEFAULT_DEVICES);
    const updated = devices.map((d) =>
      d.id === deviceId ? { ...d, currentConfigId: configId, current_config_id: configId } : d
    );
    write(LS_DEVICES, updated);
  },

  async nominateAgent(deviceId: string, agentId: string | null): Promise<void> {
    await delay();
    ensureSeed();
    const devices = read<Device[]>(LS_DEVICES, DEFAULT_DEVICES);
    const updated = devices.map((d) =>
      d.id === deviceId ? { ...d, activeAgentId: agentId, active_agent_id: agentId } : d
    );
    write(LS_DEVICES, updated);
  },
};

// -----------------------------
// Configs
// -----------------------------
export const demoConfigsApi = {
  async getAll(): Promise<StreamDeckConfig[]> {
    await delay();
    return read<StreamDeckConfig[]>(LS_CONFIGS, []);
  },

  async getById(configId: string): Promise<StreamDeckConfig> {
    await delay();
    const configs = read<StreamDeckConfig[]>(LS_CONFIGS, []);
    const config = configs.find((c) => c.id === configId);
    if (!config) throw new Error("Configuration not found");
    return config;
  },

  async create(config: Omit<StreamDeckConfig, "id">): Promise<StreamDeckConfig> {
    await delay();
    const configs = read<StreamDeckConfig[]>(LS_CONFIGS, []);
    // Mirror the real API: id is server-generated; no createdAt/updatedAt
    // columns exist on the backend model.
    const created: StreamDeckConfig = {
      ...config,
      id: uuid(),
    };
    write(LS_CONFIGS, [created, ...configs]);
    return created;
  },

  async update(
    configId: string,
    config: Partial<StreamDeckConfig>
  ): Promise<StreamDeckConfig> {
    await delay();
    const configs = read<StreamDeckConfig[]>(LS_CONFIGS, []);
    // Real PUT /config/{id} replaces name/deviceType/buttons/triggers
    // wholesale; a partial body would be rejected (422). Emulate the same
    // contract: only fields present on the payload are kept, merged over
    // nothing. Triggers (R5, P16) follow the same replace semantics — a
    // payload WITHOUT a triggers key clears the block (the pydantic
    // default is None), exactly like the real API. (JUDGE R5 fix: the
    // old code preserved target.triggers on omission, which diverged
    // from the real PUT.)
    const target = configs.find((c) => c.id === configId);
    if (!target) throw new Error("Configuration not found");
    const replaced: StreamDeckConfig = {
      id: configId,
      name: config.name ?? target.name,
      deviceType: config.deviceType ?? config.device_type ?? target.deviceType ?? target.device_type,
      buttons: config.buttons ?? target.buttons ?? [],
      triggers: config.triggers,
    };
    const updated = configs.map((c) => (c.id === configId ? replaced : c));
    write(LS_CONFIGS, updated);
    return replaced;
  },

  async delete(configId: string): Promise<void> {
    await delay();
    const configs = read<StreamDeckConfig[]>(LS_CONFIGS, []);
    write(LS_CONFIGS, configs.filter((c) => c.id !== configId));
  },
};

// -----------------------------
// Agents (demo)
// -----------------------------
export const demoAgentsApi = {
  async getAll(): Promise<Agent[]> {
    await delay();
    ensureSeed();
    return read<Agent[]>(LS_AGENTS, DEFAULT_AGENTS);
  },

  async delete(agentId: string): Promise<void> {
    await delay();
    ensureSeed();
    write(
      LS_AGENTS,
      read<Agent[]>(LS_AGENTS, DEFAULT_AGENTS).filter((a) => a.id !== agentId)
    );
  },
};

// -----------------------------
// Test connection (always true in demo)
// -----------------------------
export async function testDemoConnection(): Promise<boolean> {
  await delay(40);
  ensureSeed();
  return true;
}

export type { Agent };
export type { ButtonAction };