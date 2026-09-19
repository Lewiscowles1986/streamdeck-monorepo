import { LayoutGrid, Edit, Trash2, Copy, MoreVertical } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { StreamDeckConfig } from "@/types/streamdeck";
import { deviceDimensions, deviceTypeLabel } from "@/types/streamdeck";

interface ConfigCardProps {
  config: StreamDeckConfig;
  onDelete?: (configId: string) => void;
  onDuplicate?: (config: StreamDeckConfig) => void;
}
export function ConfigCard({ config, onDelete, onDuplicate }: ConfigCardProps) {
  const navigate = useNavigate();
  const dimensions = deviceDimensions(config?.deviceType ?? config?.device_type);
  const configuredButtons = (config?.buttons ?? []).filter(
    (b) => b.idle?.image || b.idle?.text || b.action
  ).length;
  const totalButtons = dimensions.rows * dimensions.cols;

  return (
    <Card className="group relative overflow-hidden border-border bg-card transition-all hover:border-primary/50">
      <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <CardHeader className="relative pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20">
              <LayoutGrid className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{config.name}</CardTitle>
              <Badge variant="secondary" className="mt-1">
                {deviceTypeLabel(config?.deviceType ?? config?.device_type)}
              </Badge>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Config actions">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate(`/config/${config.id}`)}>
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDuplicate?.(config)}>
                <Copy className="mr-2 h-4 w-4" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => config.id && onDelete?.(config.id)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      <CardContent className="relative">
        {/* Mini preview grid */}
        <div
          className="mb-4 grid gap-1"
          style={{
            gridTemplateColumns: `repeat(${dimensions.cols}, 1fr)`,
          }}
        >
          {Array.from({ length: totalButtons }).map((_, i) => {
            const button = (config?.buttons ?? []).find((b) => b.index === i);
            const hasContent = button?.idle?.image || button?.idle?.text || button?.action;
            return (
              <div
                key={i}
                className={`aspect-square rounded-sm ${
                  hasContent ? "bg-primary/30" : "bg-secondary"
                }`}
              />
            );
          })}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {configuredButtons} / {totalButtons} buttons configured
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="text-primary hover:text-primary"
            onClick={() => navigate(`/config/${config.id}`)}
          >
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
