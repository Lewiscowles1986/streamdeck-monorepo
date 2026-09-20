import { ChevronDown, ChevronRight, Zap } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { ConfigTriggers } from "@/types/streamdeck";

/**
 * TriggersEditor — the config-level "Automatic Switching" surface (R5, P16).
 * A collapsed section in the ConfigEditor with the two trigger inputs the
 * runner understands:
 *   - Frontmost apps: comma-separated application names (case-insensitive)
 *   - WiFi SSID (+ optional interface) to match the current network
 * Writes config.triggers = { app: [...], network: { ssid, interface } }.
 * The hint text states the runner-side semantics.
 */
export function TriggersEditor({
  triggers,
  onChange,
}: {
  triggers?: ConfigTriggers;
  onChange: (triggers: ConfigTriggers | undefined) => void;
}) {
  const [open, setOpen] = useState(false);

  const appsValue = (triggers?.app ?? []).join(", ");
  const network = triggers?.network ?? {};

  const setApps = (raw: string) => {
    const app = raw
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);
    onChange(merge({ app }, network));
  };

  const setNetwork = (updates: Partial<NonNullable<ConfigTriggers["network"]>>) => {
    const next = { ...network, ...updates };
    // Drop empty string fields so the wire form stays clean.
    for (const key of Object.keys(next) as (keyof typeof next)[]) {
      if (next[key] === "") delete next[key];
    }
    onChange(merge({ app: triggers?.app }, Object.keys(next).length ? next : undefined));
  };

  const merge = (
    app: { app?: string[] },
    network?: ConfigTriggers["network"]
  ): ConfigTriggers | undefined => {
    const next: ConfigTriggers = {};
    if (app.app && app.app.length) next.app = app.app;
    if (network && Object.keys(network).length) next.network = network;
    return Object.keys(next).length ? next : undefined;
  };

  return (
    <Collapsible open={open} onOpenChange={setOpen} data-testid="triggers-editor">
      <CollapsibleTrigger
        className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm font-medium hover:bg-secondary/60"
        data-testid="triggers-toggle"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Zap className="h-4 w-4 text-primary" />
        Automatic Switching
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-4 rounded-md border border-border bg-secondary/30 p-4">
          <p className="text-xs text-muted-foreground">
            Switch to this layout when an app is frontmost or you are connected to a wifi
            network.
          </p>
          <div className="space-y-2">
            <Label>Frontmost apps</Label>
            <Input
              value={appsValue}
              onChange={(e) => setApps(e.target.value)}
              placeholder="Slack, Spotify"
              data-testid="triggers-apps"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>WiFi SSID</Label>
              <Input
                value={network.ssid ?? ""}
                onChange={(e) => setNetwork({ ssid: e.target.value })}
                placeholder="HomeWifi"
                data-testid="triggers-ssid"
              />
            </div>
            <div className="space-y-2">
              <Label>Interface (optional)</Label>
              <Input
                value={network.interface ?? ""}
                onChange={(e) => setNetwork({ interface: e.target.value })}
                placeholder="en0"
                data-testid="triggers-interface"
              />
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}