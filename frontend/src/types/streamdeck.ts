// Device types
export type DeviceType = "stream-deck" | "stream-deck-mini" | "stream-deck-xl" | "stream-deck-mk2" | "stream-deck-plus";

export interface Device {
  id: string;
  type: DeviceType;
  name: string;
  serial?: string;
  currentConfigId?: string;
  current_config_id?: string;
  connected: boolean;
}

// Button action types
export interface CommandAction {
  type: "command";
  executable: string;
  arguments?: string;
  cwd?: string;
  env?: Record<string, string>;
}

export type ButtonAction = CommandAction;

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
  createdAt?: string;
  updatedAt?: string;
}

// Device grid dimensions
export const DEVICE_DIMENSIONS: Record<DeviceType, { rows: number; cols: number }> = {
  "stream-deck": { rows: 3, cols: 5 },
  "stream-deck-mini": { rows: 2, cols: 3 },
  "stream-deck-xl": { rows: 4, cols: 8 },
  "stream-deck-mk2": { rows: 3, cols: 5 },
  "stream-deck-plus": { rows: 2, cols: 4 },
};

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
];
