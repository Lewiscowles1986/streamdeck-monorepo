import { useState } from "react";
import { Plus, Trash2, Variable } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type {
  ButtonAction,
  CommandAction,
  SwitchConfigAction,
  StreamDeckConfig,
} from "@/types/streamdeck";
import { TEMPLATE_VARIABLES } from "@/types/streamdeck";
import { useQuery } from "@tanstack/react-query";
import { configsApi } from "@/lib/api";

interface ActionEditorProps {
  action?: ButtonAction | null;
  onChange: (action: ButtonAction | null) => void;
}

export function ActionEditor({ action, onChange }: ActionEditorProps) {
  const [envEntries, setEnvEntries] = useState<[string, string][]>(
    action?.type === "command" && action.env
      ? Object.entries(action.env)
      : []
  );

  const commandAction = action?.type === "command" ? action : null;
  const switchAction = action?.type === "switch-config" ? action : null;

  // The switch-config picker lists every config in the store (demo mock or
  // real API — configsApi.getAll serves both).
  const { data: configs = [] } = useQuery({
    queryKey: ["configs"],
    queryFn: configsApi.getAll,
    enabled: action?.type === "switch-config",
  });

  const updateCommand = (updates: Partial<CommandAction>) => {
    const newAction: CommandAction = {
      type: "command",
      executable: commandAction?.executable || "",
      ...commandAction,
      ...updates,
    };
    onChange(newAction);
  };

  const addEnvVar = () => {
    const newEntries = [...envEntries, ["", ""] as [string, string]];
    setEnvEntries(newEntries);
    updateCommand({ env: Object.fromEntries(newEntries.filter(([k]) => k)) });
  };

  const updateEnvVar = (index: number, key: string, value: string) => {
    const newEntries = [...envEntries];
    newEntries[index] = [key, value];
    setEnvEntries(newEntries);
    updateCommand({ env: Object.fromEntries(newEntries.filter(([k]) => k)) });
  };

  const removeEnvVar = (index: number) => {
    const newEntries = envEntries.filter((_, i) => i !== index);
    setEnvEntries(newEntries);
    updateCommand({ env: Object.fromEntries(newEntries.filter(([k]) => k)) });
  };

  const insertTemplate = (variable: string, field: "executable" | "arguments" | "cwd") => {
    const currentValue = commandAction?.[field] || "";
    updateCommand({ [field]: currentValue + variable });
  };

  const TemplateButton = ({ field }: { field: "executable" | "arguments" | "cwd" }) => (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="h-8 w-8">
          <Variable className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="end">
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Template Variables</h4>
          <div className="space-y-1">
            {TEMPLATE_VARIABLES.map((v) => (
              <button
                key={v.name}
                onClick={() => insertTemplate(v.name, field)}
                className="flex w-full items-start gap-2 rounded-md p-2 text-left hover:bg-secondary"
              >
                <code className="text-xs text-primary">{v.name}</code>
                <span className="text-xs text-muted-foreground">{v.description}</span>
              </button>
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Action Type</Label>
        <Select
          value={
            action?.type === "exit"
              ? "exit"
              : action?.type === "switch-config"
                ? "switch-config"
                : action
                  ? "command"
                  : "none"
          }
          onValueChange={(value) => {
            if (value === "none") {
              onChange(null);
            } else if (value === "exit") {
              // The runner treats a bare-string/exit action as the shutdown
              // button; represented as {"type": "exit"} in the config JSON.
              onChange({ type: "exit" });
            } else if (value === "switch-config") {
              // P15: the runner swaps its active config for this one.
              onChange({ type: "switch-config", configId: "" });
            } else {
              updateCommand({});
            }
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select action type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">No Action</SelectItem>
            <SelectItem value="command">Command</SelectItem>
            <SelectItem value="switch-config">Switch Config</SelectItem>
            <SelectItem value="exit">Exit (shut down the runner)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {action?.type === "exit" && (
        <p className="rounded-md border border-warning/40 bg-warning/10 p-3 text-xs text-muted-foreground">
          Pressing this button stops the Stream Deck runner and closes the
          connection. Use it as an emergency off-switch.
        </p>
      )}

      {switchAction && (
        <SwitchConfigFields
          action={switchAction}
          configs={configs}
          onChange={onChange}
        />
      )}

      {commandAction && (
        <>
          <div className="space-y-2">
            <Label>Launch Mode</Label>
            <Select
              value={commandAction.mode || "attached"}
              onValueChange={(value) =>
                updateCommand({ mode: value as "attached" | "detached" })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="attached">
                  Attached (wait for completion)
                </SelectItem>
                <SelectItem value="detached">
                  Detached (fire and forget)
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Attached waits for the command and reports its output. Detached
              starts it and moves on — the process keeps running after the
              agent stops (no timeout, no output capture).
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Executable</Label>
              <TemplateButton field="executable" />
            </div>
            <Input
              value={commandAction.executable}
              onChange={(e) => updateCommand({ executable: e.target.value })}
              placeholder="/path/to/executable"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Arguments</Label>
              <TemplateButton field="arguments" />
            </div>
            <Input
              value={commandAction.arguments || ""}
              onChange={(e) => updateCommand({ arguments: e.target.value })}
              placeholder="--flag value"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Working Directory</Label>
              <TemplateButton field="cwd" />
            </div>
            <Input
              value={commandAction.cwd || ""}
              onChange={(e) => updateCommand({ cwd: e.target.value })}
              placeholder="/path/to/directory"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Timeout (seconds)</Label>
            </div>
            <Input
              type="number"
              value={commandAction.timeout ?? 30}
              onChange={(e) =>
                updateCommand({ timeout: parseInt(e.target.value) || 30 })
              }
              min={1}
              max={600}
            />
            <p className="text-xs text-muted-foreground">
              The agent kills the command after this many seconds (default 30).
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Environment Variables</Label>
              <Button variant="ghost" size="sm" onClick={addEnvVar}>
                <Plus className="mr-1 h-4 w-4" />
                Add
              </Button>
            </div>
            {envEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground">No environment variables</p>
            ) : (
              <div className="space-y-2">
                {envEntries.map(([key, value], index) => (
                  <div key={index} className="flex gap-2">
                    <Input
                      value={key}
                      onChange={(e) => updateEnvVar(index, e.target.value, value)}
                      placeholder="KEY"
                      className="flex-1"
                    />
                    <Input
                      value={value}
                      onChange={(e) => updateEnvVar(index, key, e.target.value)}
                      placeholder="value"
                      className="flex-1"
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeEnvVar(index)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * P15 switch-config fields: a config picker (Select listing every config
 * from the API/demo store) plus a manual id input. Choosing from the list
 * fills the input; the JSON wire form is
 * {"type": "switch-config", "configId": "..."}.
 */
function SwitchConfigFields({
  action,
  configs,
  onChange,
}: {
  action: SwitchConfigAction;
  configs: StreamDeckConfig[];
  onChange: (action: ButtonAction | null) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>Target Config</Label>
      <Select
        value={action.configId || undefined}
        onValueChange={(value) => onChange({ type: "switch-config", configId: value })}
      >
        <SelectTrigger>
          <SelectValue placeholder={configs.length ? "Pick a config…" : "No configs yet"} />
        </SelectTrigger>
        <SelectContent>
          {configs.map((config) => (
            <SelectItem key={config.id} value={config.id!}>
              {config.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        value={action.configId}
        onChange={(e) => onChange({ type: "switch-config", configId: e.target.value })}
        placeholder="Config ID (from the picker or pasted)"
      />
      <p className="text-xs text-muted-foreground">
        Pressing this button makes the device runner switch to the selected
        configuration and re-render every key. Unknown ids are ignored at
        press time (the current config stays active).
      </p>
    </div>
  );
}
