import { Monitor, CheckCircle, XCircle, Link, Laptop } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Device } from "@/types/streamdeck";
import { deviceTypeLabel } from "@/types/streamdeck";

interface DeviceCardProps {
  device: Device;
  onAssignConfig?: (deviceId: string) => void;
  onNominateAgent?: (deviceId: string) => void;
  onClearAgent?: (deviceId: string) => void;
}

function linkIfExists(assignedEntityId: string | undefined | null) {
  if (assignedEntityId) {
    return (
      <a
        href={`/config/${assignedEntityId}`}
        className="text-primary underline hover:text-primary/80"
      >
        {assignedEntityId}
      </a>
    );
  }
  return null;
}

export function DeviceCard({
  device,
  onAssignConfig,
  onNominateAgent,
  onClearAgent,
}: DeviceCardProps) {
  const assignedEntityId = device?.currentConfigId ?? device?.current_config_id;
  const assigned = Boolean(assignedEntityId);
  const nominatedAgentId = device?.activeAgentId ?? device?.active_agent_id;
  return (
    <Card className="group relative overflow-hidden border-border bg-card transition-all hover:border-primary/50">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
      
      <CardHeader className="relative pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-secondary">
              <Monitor className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">{device.name || deviceTypeLabel(device.type)}</CardTitle>
              <p className="text-sm text-muted-foreground">{deviceTypeLabel(device.type)}</p>
            </div>
          </div>
          <Badge
            variant={device.connected ? "default" : "secondary"}
            className={device.connected ? "bg-success/20 text-success" : ""}
          >
            {device.connected ? (
              <CheckCircle className="mr-1 h-3 w-3" />
            ) : (
              <XCircle className="mr-1 h-3 w-3" />
            )}
            {device.connected ? "Online" : "Offline"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="relative space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Device ID</span>
            <p className="font-mono text-xs">{device.id}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Nominated Agent</span>
            <p className="font-mono text-xs truncate">
              {nominatedAgentId ? (
                <span className="inline-flex items-center gap-1">
                  <Laptop className="h-3 w-3 text-primary" />
                  {nominatedAgentId}
                </span>
              ) : (
                <span className="text-muted-foreground">None</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border pt-4">
          <div>
            <span className="text-sm text-muted-foreground">Active Config</span>
            <p className="text-sm font-medium">
              {linkIfExists(assignedEntityId) ?? "None assigned"}
            </p>
          </div>
          <div className="flex gap-2">
            {nominatedAgentId && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onClearAgent?.(device.id)}
                title="Fall back to local execution"
              >
                Clear agent
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNominateAgent?.(device.id)}
            >
              <Laptop className="mr-2 h-4 w-4" />
              {nominatedAgentId ? "Change agent" : "Nominate"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAssignConfig?.(device.id)}
            >
              <Link className="mr-2 h-4 w-4" />
              {(assigned) ? "Re-assign" : "Assign"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
