import { Monitor, CheckCircle, XCircle, Link } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Device } from "@/types/streamdeck";

interface DeviceCardProps {
  device: Device;
  onAssignConfig?: (deviceId: string) => void;
}

const deviceTypeLabels: Record<string, string> = {
  "stream-deck": "Stream Deck",
  "stream-deck-mini": "Stream Deck Mini",
  "stream-deck-xl": "Stream Deck XL",
  "stream-deck-mk2": "Stream Deck MK.2",
  "stream-deck-plus": "Stream Deck +",
};

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

export function DeviceCard({ device, onAssignConfig }: DeviceCardProps) {
  const assignedEntityId = device?.currentConfigId ?? device?.current_config_id;
  const assigned = Boolean(assignedEntityId);
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
              <CardTitle className="text-lg">{device.name || deviceTypeLabels[device.type]}</CardTitle>
              <p className="text-sm text-muted-foreground">{deviceTypeLabels[device.type]}</p>
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
          {device.serial && (
            <div>
              <span className="text-muted-foreground">Serial</span>
              <p className="font-mono text-xs">{device.serial}</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border pt-4">
          <div>
            <span className="text-sm text-muted-foreground">Active Config</span>
            <p className="text-sm font-medium">
              {linkIfExists(assignedEntityId) ?? "None assigned"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onAssignConfig?.(device.id)}
          >
            <Link className="mr-2 h-4 w-4" />
            {(assigned) ? "Re-assign" : "Assign"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
