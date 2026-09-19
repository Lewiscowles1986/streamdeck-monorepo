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

import type { Device, StreamDeckConfig, ButtonAction } from "@/types/streamdeck";

const LS_DEVICES = "streamdeck_demo_devices";
const LS_CONFIGS = "streamdeck_demo_configs";
const LS_AGENTS = "streamdeck_demo_agents";

export const DEMO_DEVICE_ID = "demo-deck-xl-001";

interface Agent {
  id: string;
  hostname: string;
  user?: string | null;
  platform?: string | null;
  connected: boolean;
}

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

// Seed devices so a fresh demo has something to look at.
const DEFAULT_DEVICES: Device[] = [
  {
    id: DEMO_DEVICE_ID,
    type: "stream-deck-xl",
    name: "Stream Deck XL (demo) - 000000000001",
    connected: true,
    currentConfigId: undefined,
    current_config_id: undefined,
  },
  {
    id: "demo-deck-mk2-002",
    type: "stream-deck-mk2",
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
    connected: true,
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
    const created: StreamDeckConfig = {
      ...config,
      id: uuid(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
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
    const updated = configs.map((c) =>
      c.id === configId
        ? { ...c, ...config, updatedAt: new Date().toISOString() }
        : c
    );
    write(LS_CONFIGS, updated);
    const found = updated.find((c) => c.id === configId);
    if (!found) throw new Error("Configuration not found");
    return found;
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