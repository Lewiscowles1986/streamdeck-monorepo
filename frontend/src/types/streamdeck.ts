// Device types
//
// Two dialects are in play (both accepted everywhere):
//  - kebab ids: what the UI stores in configs and sends to the API
//  - human names: what the vendored core reports (DECK_TYPE) and what
//    GET /devices returns — e.g. "Stream Deck XL", "Stream Deck +"
export type DeviceType =
  | "stream-deck"
  | "stream-deck-mini"
  | "stream-deck-xl"
  | "stream-deck-mk2"
  | "stream-deck-plus"
  | "stream-deck-neo"
  | "stream-deck-pedal"
  | "stream-deck-studio"
  | "Stream Deck"
  | "Stream Deck Mini"
  | "Stream Deck XL"
  | "Stream Deck MK.2"
  | "Stream Deck +"
  | "Stream Deck Neo"
  | "Stream Deck Pedal"
  | "Stream Deck Studio";

export interface Device {
  id: string;
  type: DeviceType;
  name: string;
  currentConfigId?: string;
  current_config_id?: string;
  activeAgentId?: string | null;
  active_agent_id?: string | null;
  connected: boolean;
}

// Button action types
export interface CommandAction {
  type: "command";
  executable: string;
  arguments?: string;
  cwd?: string;
  env?: Record<string, string>;
  timeout?: number;
}

export interface ExitAction {
  type: "exit";
}

export type ButtonAction = CommandAction | ExitAction;

// A nominated computer running `streamdeck agent` (backend Agent model).
// NOTE: the Agent model intentionally has NO camelCase aliases — the wire
// dialect for agents is snake_case (agent CLI registers with `last_seen`).
export interface Agent {
  id: string;
  hostname: string;
  user?: string | null;
  platform?: string | null;
  active?: boolean;
  last_seen?: string | null;
}

// Font configuration
export interface FontConfig {
  family?: string;
  size?: number;
  color?: string;
  weight?: "normal" | "bold";
  position?: "top" | "center" | "bottom";
}

// Button appearance state
export interface ButtonAppearance {
  image?: string;
  text?: string;
  font?: FontConfig;
}

// Toggle state
export interface ToggleState extends ButtonAppearance {
  name: string;
  action?: ButtonAction;
}

// Button configuration
export interface ButtonConfig {
  index: number;
  idle?: ButtonAppearance;
  pressed?: ButtonAppearance;
  action?: ButtonAction | null;
  isToggle?: boolean;
  toggleStates?: ToggleState[];
}

// Stream Deck configuration
export interface StreamDeckConfig {
  id?: string;
  name: string;
  deviceType?: DeviceType;
  device_type?: DeviceType;
  buttons?: ButtonConfig[];
}

// Device grid dimensions — keyed by BOTH kebab ids and the human names
// the backend returns, so lookups never miss.
export const DEVICE_DIMENSIONS: Record<string, { rows: number; cols: number }> = {
  "stream-deck": { rows: 3, cols: 5 },
  "Stream Deck": { rows: 3, cols: 5 },
  "stream-deck-mk2": { rows: 3, cols: 5 },
  "Stream Deck MK.2": { rows: 3, cols: 5 },
  "stream-deck-mini": { rows: 2, cols: 3 },
  "Stream Deck Mini": { rows: 2, cols: 3 },
  "stream-deck-xl": { rows: 4, cols: 8 },
  "Stream Deck XL": { rows: 4, cols: 8 },
  "stream-deck-plus": { rows: 2, cols: 4 },
  "Stream Deck +": { rows: 2, cols: 4 },
  "stream-deck-neo": { rows: 2, cols: 4 },
  "Stream Deck Neo": { rows: 2, cols: 4 },
  "stream-deck-pedal": { rows: 1, cols: 3 },
  "Stream Deck Pedal": { rows: 1, cols: 3 },
  "stream-deck-studio": { rows: 2, cols: 16 },
  "Stream Deck Studio": { rows: 2, cols: 16 },
};

// Fallback for unknown device types (must render, not crash).
export const FALLBACK_DEVICE_DIMENSIONS = { rows: 3, cols: 5 };

export function deviceDimensions(deviceType?: DeviceType): { rows: number; cols: number } {
  if (!deviceType) return FALLBACK_DEVICE_DIMENSIONS;
  return DEVICE_DIMENSIONS[deviceType] ?? FALLBACK_DEVICE_DIMENSIONS;
}

// Template variable for actions
export interface TemplateVariable {
  name: string;
  description: string;
  example: string;
}

export const TEMPLATE_VARIABLES: TemplateVariable[] = [
  { name: "{{button_index}}", description: "Current button index", example: "0" },
  { name: "{{device_id}}", description: "Device identifier", example: "ABC123" },
  { name: "{{toggle_state}}", description: "Current toggle state index", example: "0" },
  { name: "{{config_name}}", description: "Active configuration name", example: "Gaming" },
  { name: "{{timestamp}}", description: "Current Unix timestamp", example: "1699876543" },
  { name: "{{date}}", description: "Current date (YYYY-MM-DD)", example: "2026-09-19" },
  { name: "{{time}}", description: "Current time (HH:MM:SS)", example: "14:30:00" },
];

// Display label for a device type in either dialect (human names pass through).
export function deviceTypeLabel(deviceType?: DeviceType): string {
  if (!deviceType) return "Stream Deck";
  if (deviceType.includes(" ")) return deviceType; // human name from the API
  const labels: Record<string, string> = {
    "stream-deck": "Stream Deck",
    "stream-deck-mini": "Stream Deck Mini",
    "stream-deck-xl": "Stream Deck XL",
    "stream-deck-mk2": "Stream Deck MK.2",
    "stream-deck-plus": "Stream Deck +",
    "stream-deck-neo": "Stream Deck Neo",
    "stream-deck-pedal": "Stream Deck Pedal",
    "stream-deck-studio": "Stream Deck Studio",
  };
  return labels[deviceType] ?? deviceType;
}
