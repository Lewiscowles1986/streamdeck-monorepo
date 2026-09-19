import type { Device, StreamDeckConfig, Agent } from "@/types/streamdeck";
import {
  isDemoMode,
  demoDevicesApi,
  demoConfigsApi,
  demoAgentsApi,
  testDemoConnection,
} from "@/lib/demo-api";

let apiBaseUrl = localStorage.getItem("streamdeck_api_url") || "http://localhost:8000";

export const getApiBaseUrl = () => apiBaseUrl;

export const setApiBaseUrl = (url: string) => {
  apiBaseUrl = url.replace(/\/$/, ""); // Remove trailing slash
  localStorage.setItem("streamdeck_api_url", apiBaseUrl);
};

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  // Demo mode: serve everything from the in-browser mock (no server needed).
  if (isDemoMode()) {
    return demoFetch<T>(endpoint, options);
  }

  const url = `${apiBaseUrl}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, `API Error ${response.status}: ${errorText}`);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) return {} as T;
  
  return JSON.parse(text);
}

// Device endpoints
export const devicesApi = {
  getAll: () => fetchApi<Device[]>("/devices"),
  
  assignConfig: (deviceId: string, configId: string) =>
    fetchApi<void>(`/device/${deviceId}/config/${configId}`, { method: "PUT" }),

  // The config currently assigned to a device (what the device runner loads).
  getAssignedConfig: (deviceId: string) =>
    fetchApi<{ config: StreamDeckConfig | null; device: Device }>(
      `/device/${deviceId}/config`
    ),

  // Nominate a computer to execute this device's command actions.
  nominateAgent: (deviceId: string, agentId: string) =>
    fetchApi<Device>(`/device/${deviceId}/agent/${agentId}`, { method: "PUT" }),

  // Fall back to local execution (clears the nomination).
  clearAgent: (deviceId: string) =>
    fetchApi<Device>(`/device/${deviceId}/agent`, { method: "DELETE" }),
};

// Agent endpoints (nominate-a-computer). NOTE the dialect: the Agent model
// has no camelCase aliases — snake_case on the wire.
export const agentsApi = {
  getAll: () => fetchApi<Agent[]>("/agents"),

  delete: (agentId: string) =>
    fetchApi<Agent>(`/agents/${agentId}`, { method: "DELETE" }),
};

// Config endpoints
export const configsApi = {
  getAll: () => fetchApi<StreamDeckConfig[]>("/configs"),

  getById: (configId: string) => fetchApi<StreamDeckConfig>(`/config/${configId}`),

  create: (config: Omit<StreamDeckConfig, "id">) =>
    fetchApi<StreamDeckConfig>("/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  
  update: (configId: string, config: StreamDeckConfig) =>
    fetchApi<StreamDeckConfig>(`/config/${configId}`, {
      method: "PUT",
      body: JSON.stringify(config),
    }),
  
  delete: (configId: string) =>
    fetchApi<void>(`/config/${configId}`, { method: "DELETE" }),
};

// Test connection
export const testConnection = async (): Promise<boolean> => {
  if (isDemoMode()) return testDemoConnection();
  try {
    await fetchApi("/devices");
    return true;
  } catch {
    return false;
  }
};

// Route a request to the in-browser demo mock. Mirrors the REST surface.
async function demoFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? "GET").toUpperCase();
  const body = options?.body ? JSON.parse(String(options.body)) : undefined;
  const [path, queryString] = endpoint.split("?");
  const parts = path.split("/").filter(Boolean); // e.g. ["config", ":id"]

  const notFound = () => {
    throw new ApiError(404, "Not found (demo)");
  };

  // /devices
  if (parts[0] === "devices" && method === "GET") {
    return demoDevicesApi.getAll() as unknown as T;
  }
  // /device/:id/config (runner-facing: what will this deck run)
  if (parts[0] === "device" && parts[2] === "config" && method === "GET") {
    const devices = await demoDevicesApi.getAll();
    const device = devices.find((d) => d.id === parts[1]);
    if (!device) notFound();
    const configs = await demoConfigsApi.getAll();
    const assignedId = device.currentConfigId ?? device.current_config_id;
    const config = assignedId
      ? (configs.find((c) => c.id === assignedId) ?? null)
      : null;
    return { config, device } as unknown as T;
  }
  // /device/:id/config/:configId
  if (parts[0] === "device" && parts[2] === "config" && method === "PUT") {
    await demoDevicesApi.assignConfig(parts[1], parts[3]);
    return {} as T;
  }
  // /device/:id/agent/:agentId
  if (parts[0] === "device" && parts[2] === "agent" && method === "PUT") {
    await demoDevicesApi.nominateAgent(parts[1], parts[3]);
    return {} as T;
  }
  // /device/:id/agent (clear nomination)
  if (parts[0] === "device" && parts[2] === "agent" && method === "DELETE") {
    await demoDevicesApi.nominateAgent(parts[1], null);
    return {} as T;
  }
  // /agents (list) and /agents/:id (delete)
  if (parts[0] === "agents" && method === "GET") {
    return demoAgentsApi.getAll() as unknown as T;
  }
  if (parts[0] === "agents" && method === "DELETE" && parts[1]) {
    await demoAgentsApi.delete(parts[1]);
    return {} as T;
  }
  // /configs, /config, /config/:id
  if (parts[0] === "configs" && method === "GET") {
    return demoConfigsApi.getAll() as unknown as T;
  }
  if (parts[0] === "config") {
    if (method === "GET" && parts[1]) return demoConfigsApi.getById(parts[1]) as unknown as T;
    if (method === "POST") return demoConfigsApi.create(body) as unknown as T;
    if (method === "PUT" && parts[1]) return demoConfigsApi.update(parts[1], body) as unknown as T;
    if (method === "DELETE" && parts[1]) {
      await demoConfigsApi.delete(parts[1]);
      return {} as T;
    }
    notFound();
  }
  if (queryString !== undefined) notFound();
  notFound();
}
