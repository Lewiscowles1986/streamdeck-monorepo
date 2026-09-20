import { useState } from "react";
import { Plus, Trash2, Variable } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { CommandInput } from "./CommandInput";
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
  SequenceAction,
  SequenceStep,
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
  const sequenceAction = action?.type === "sequence" ? action : null;

  // JSON fallback for sequence steps the structured editor does not host
  // (non-command step types). Editing here replaces the whole steps array.
  const [stepsJson, setStepsJson] = useState<string | null>(null);

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
            } else if (value === "sequence") {
              // P18: an empty sequence — add steps to build it up.
              onChange({ type: "sequence", steps: [] });
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
            <SelectItem value="sequence">Sequence (run multiple actions)</SelectItem>
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

      {sequenceAction && (
        <SequenceEditor
          action={sequenceAction}
          stepsJson={stepsJson}
          onStepsJsonChange={setStepsJson}
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
            {/* P17 completion: static binaries + typed history; template
                variables complete inline after "{{". Drop-in for the raw
                Input (same value/onChange contract). */}
            <CommandInput
              value={commandAction.executable}
              onChange={(executable) => updateCommand({ executable })}
              placeholder="/path/to/executable"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Arguments</Label>
              <TemplateButton field="arguments" />
            </div>
            {/* P17: flags helper for known binaries + inline template vars;
                executableContext drives the static flag map. */}
            <CommandInput
              value={commandAction.arguments || ""}
              onChange={(arguments_) => updateCommand({ arguments: arguments_ })}
              placeholder="--flag value"
              executableContext={commandAction.executable}
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

/**
 * P18 sequence editor: steps as compact cards, each hosting the command
 * fields (executable + arguments via CommandInput, launch mode) plus a
 * per-step "Delay before step (ms)" input and remove button; a stopOnError
 * switch for the sequence. JSON View round-trips the nested structure; a
 * JSON fallback textarea hosts step types the card form does not.
 */
function SequenceEditor({
  action,
  stepsJson,
  onStepsJsonChange,
  onChange,
}: {
  action: SequenceAction;
  stepsJson: string | null;
  onStepsJsonChange: (json: string | null) => void;
  onChange: (action: ButtonAction | null) => void;
}) {
  const steps = Array.isArray(action.steps) ? action.steps : [];

  const updateSequence = (updates: Partial<SequenceAction>) => {
    onChange({ ...action, ...updates });
  };

  const addStep = () => {
    const next: SequenceStep = { type: "command", executable: "" };
    onChange({ ...action, steps: [...steps, next] });
  };

  const updateStep = (index: number, updates: Partial<SequenceStep>) => {
    const newSteps = steps.map((step, i) =>
      i === index ? { ...step, ...updates } : step
    );
    onChange({ ...action, steps: newSteps });
  };

  const removeStep = (index: number) => {
    onChange({
      ...action,
      steps: steps.filter((_, i) => i !== index),
    });
  };

  const applyStepsJson = () => {
    try {
      const parsed = JSON.parse(stepsJson ?? "[]");
      if (!Array.isArray(parsed)) return;
      onChange({ ...action, steps: parsed });
      onStepsJsonChange(null);
    } catch {
      // invalid JSON: keep the textarea open for correction
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Label>Sequence Steps ({steps.length})</Label>
        <Button variant="outline" size="sm" onClick={addStep}>
          <Plus className="mr-1 h-4 w-4" />
          Add step
        </Button>
      </div>

      {steps.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No steps yet — each step is a full action run in order.
        </p>
      )}

      <div className="space-y-3">
        {steps.map((step, index) => (
          <div key={index} className="rounded-md border border-border p-3" data-testid={`sequence-step-${index}`}>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                Step {index + 1}
                {"type" in step && step.type === "command" ? (
                  <span className="ml-2 rounded bg-secondary px-1.5 py-0.5 text-[10px] uppercase">
                    Command
                  </span>
                ) : null}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-destructive hover:text-destructive"
                onClick={() => removeStep(index)}
                aria-label={`Remove step ${index + 1}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs">Executable</Label>
              </div>
              <CommandInput
                value={step.executable || ""}
                onChange={(executable) => updateStep(index, { executable })}
                placeholder="/path/to/executable"
              />
              <div className="flex items-center justify-between">
                <Label className="text-xs">Arguments</Label>
              </div>
              <CommandInput
                value={step.arguments || ""}
                onChange={(arguments_) => updateStep(index, { arguments: arguments_ })}
                placeholder="--flag value"
                executableContext={step.executable}
              />
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="text-xs">Launch Mode</Label>
                  <Select
                    value={step.mode || "attached"}
                    onValueChange={(value) =>
                      updateStep(index, { mode: value as "attached" | "detached" })
                    }
                  >
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="attached">Attached</SelectItem>
                      <SelectItem value="detached">Detached</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Delay before step (ms)</Label>
                  <Input
                    type="number"
                    value={step.delayMs ?? 0}
                    onChange={(e) =>
                      updateStep(index, {
                        delayMs: parseInt(e.target.value) || 0,
                      })
                    }
                    min={0}
                    max={60000}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between rounded-md border border-border p-3">
        <div className="space-y-1">
          <Label>Stop on Error</Label>
          <p className="text-xs text-muted-foreground">
            Abort remaining steps after the first failure (default: fire all
            steps and report partial results).
          </p>
        </div>
        <Switch
          checked={action.stopOnError || false}
          onCheckedChange={(checked) => updateSequence({ stopOnError: checked })}
          aria-label="Stop on Error"
        />
      </div>

      <details className="rounded-md border border-border p-3" data-testid="sequence-json-fallback">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          Advanced: edit steps as JSON
        </summary>
        <div className="mt-2 space-y-2">
          <Textarea
            value={stepsJson ?? JSON.stringify(steps, null, 2)}
            onChange={(e) => onStepsJsonChange(e.target.value)}
            rows={8}
            className="font-mono text-xs"
            aria-label="Sequence steps JSON"
          />
          <Button variant="outline" size="sm" onClick={applyStepsJson}>
            Apply JSON
          </Button>
        </div>
      </details>

      <p className="text-xs text-muted-foreground">
        Steps run in order on the nominated agent. A failed step does not stop
        the runner — results are reported per step.
      </p>
    </div>
  );
}
