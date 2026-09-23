import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save, Loader2, ImagePlus, Trash2, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ImageUpload } from "@/components/streamdeck/ImageUpload";
import { useToast } from "@/hooks/use-toast";
import { configsApi } from "@/lib/api";
import type {
  StreamDeckConfig,
  BackgroundSpan,
  DeviceType,
} from "@/types/streamdeck";
import { deviceDimensions } from "@/types/streamdeck";

/**
 * Backgrounds — the P19 coordination surface.
 *
 * One page composes multi-button image backgrounds for a config: upload the
 * image, place the span (x/y = top-left cell, width/height = cells), and see
 * the exact per-cell crop the device runner will paint — the same composite-
 * then-slice math lives in `backgroundTileStyle` (ButtonGrid) and the runner
 * (`streamdeck/runner.py`). Save writes `config.backgrounds` through the
 * normal whole-row PUT.
 */
export default function Backgrounds() {
  const { configId: routeConfigId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [selectedConfigId, setSelectedConfigId] = useState<string | undefined>(
    routeConfigId
  );
  const [config, setConfig] = useState<StreamDeckConfig | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  const { data: configs = [], isLoading: configsLoading } = useQuery({
    queryKey: ["configs"],
    queryFn: configsApi.getAll,
  });

  const { isLoading: configLoading } = useQuery({
    queryKey: ["config", selectedConfigId],
    queryFn: () => configsApi.getById(selectedConfigId!),
    enabled: !!selectedConfigId,
  });

  const saveMutation = useMutation({
    mutationFn: (updated: StreamDeckConfig) =>
      configsApi.update(updated.id!, updated),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configs"] });
      queryClient.invalidateQueries({ queryKey: ["config", selectedConfigId] });
      toast({ title: "Saved", description: "Backgrounds saved successfully." });
      setHasChanges(false);
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const handleSelectConfig = (id: string) => {
    setSelectedConfigId(id);
    setHasChanges(false);
    setConfig(null);
  };

  // Adopt the query cache into editor state when the selection changes.
  // Editor state is the source of truth while editing; the cache wins only
  // on selection change (or after a save invalidated the query).
  const cache = queryClient.getQueryData<StreamDeckConfig>([
    "config",
    selectedConfigId,
  ]);
  useEffect(() => {
    setConfig(cache ?? null);
    setHasChanges(false);
  }, [selectedConfigId, cache]);

  const effectiveConfig = config;

  const deviceType = (effectiveConfig?.deviceType ??
    effectiveConfig?.device_type) as DeviceType | undefined;
  const dimensions = deviceDimensions(deviceType);
  const totalButtons = dimensions.rows * dimensions.cols;

  const backgrounds = useMemo(
    () => effectiveConfig?.backgrounds ?? [],
    [effectiveConfig]
  );

  const setBackgrounds = (next: BackgroundSpan[]) => {
    if (!effectiveConfig) return;
    setConfig({ ...effectiveConfig, backgrounds: next });
    setHasChanges(true);
  };

  const addSpan = () => {
    if (!effectiveConfig) return;
    const span: BackgroundSpan = {
      id: `bg-${Date.now().toString(36)}`,
      image: "",
      x: 0,
      y: 0,
      width: Math.min(2, dimensions.cols),
      height: Math.min(2, dimensions.rows),
    };
    setConfig({ ...effectiveConfig, backgrounds: [...backgrounds, span] });
    setHasChanges(true);
  };

  const updateSpan = (id: string, updates: Partial<BackgroundSpan>) => {
    setConfig({
      ...effectiveConfig!,
      backgrounds: backgrounds.map((bg) =>
        bg.id === id ? { ...bg, ...updates } : bg
      ),
    });
    setHasChanges(true);
  };

  const removeSpan = (id: string) => {
    setConfig({
      ...effectiveConfig!,
      backgrounds: backgrounds.filter((bg) => bg.id !== id),
    });
    setHasChanges(true);
  };

  const handleSave = () => {
    if (effectiveConfig?.id) saveMutation.mutate(effectiveConfig);
  };

  /** Per-cell CSS tile — same math as ButtonGrid.backgroundTileStyle. */
  const tileStyle = (bg: BackgroundSpan, index: number) => {
    const row = Math.floor(index / dimensions.cols);
    const col = index % dimensions.cols;
    const inside =
      col >= bg.x &&
      col < bg.x + bg.width &&
      row >= bg.y &&
      row < bg.y + bg.height;
    if (!inside || !bg.image) return undefined;
    return {
      backgroundImage: `url(${bg.image})`,
      backgroundSize: `${bg.width * 100}% ${bg.height * 100}%`,
      backgroundPosition: `${((bg.x - col) / bg.width) * 100}% ${
        ((bg.y - row) / bg.height) * 100
      }%`,
    };
  };

  const coveringSpan = (index: number) => {
    for (const bg of [...backgrounds].reverse()) {
      if (tileStyle(bg, index)) return bg;
    }
    return undefined;
  };

  if (configsLoading || (selectedConfigId && !effectiveConfig && configLoading)) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-card/50 px-6 py-4">
        <div className="flex items-center gap-4">
          {routeConfigId && (
            <Button variant="ghost" size="icon" onClick={() => navigate("/configs")}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div className="flex items-center gap-3">
            <Layers className="h-5 w-5 text-primary" />
            <div>
              <h1 className="text-lg font-semibold">Backgrounds</h1>
              <p className="text-xs text-muted-foreground">
                Images painted across multiple buttons
              </p>
            </div>
          </div>
        </div>
        <Button
          onClick={handleSave}
          disabled={!hasChanges || saveMutation.isPending || !effectiveConfig}
          className="glow-primary"
        >
          {saveMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save
        </Button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Controls */}
        <div className="w-96 shrink-0 overflow-y-auto border-r border-border p-6">
          <div className="space-y-6">
            <div className="space-y-2">
              <Label>Configuration</Label>
              <Select
                value={selectedConfigId ?? ""}
                onValueChange={handleSelectConfig}
              >
                <SelectTrigger data-testid="backgrounds-config-picker">
                  <SelectValue placeholder="Pick a config" />
                </SelectTrigger>
                <SelectContent>
                  {configs.map((c) => (
                    <SelectItem key={c.id} value={c.id!}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {configs.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  No configs yet — create one under Configurations first.
                </p>
              )}
            </div>

            {!effectiveConfig ? (
              <p className="text-sm text-muted-foreground">
                Select a configuration to compose its backgrounds.
              </p>
            ) : (
              <>
                {backgrounds.map((bg) => (
                  <div
                    key={bg.id}
                    data-testid={`background-editor-${bg.id}`}
                    className="space-y-3 rounded-lg border border-border bg-secondary/30 p-4"
                  >
                    <div className="flex items-center justify-between">
                      <Label className="text-sm">Background</Label>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs text-destructive"
                        onClick={() => removeSpan(bg.id)}
                        aria-label={`Remove background ${bg.id}`}
                      >
                        <Trash2 className="mr-1 h-3 w-3" />
                        Remove
                      </Button>
                    </div>

                    <ImageUpload
                      value={bg.image || undefined}
                      onChange={(image) =>
                        updateSpan(bg.id, { image: image ?? "" })
                      }
                      label="Span image"
                    />

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Column (x)</Label>
                        <Input
                          type="number"
                          min={0}
                          max={dimensions.cols - 1}
                          value={bg.x}
                          onChange={(e) =>
                            updateSpan(bg.id, { x: Number(e.target.value) || 0 })
                          }
                          data-testid={`background-x-${bg.id}`}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Row (y)</Label>
                        <Input
                          type="number"
                          min={0}
                          max={dimensions.rows - 1}
                          value={bg.y}
                          onChange={(e) =>
                            updateSpan(bg.id, { y: Number(e.target.value) || 0 })
                          }
                          data-testid={`background-y-${bg.id}`}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Width (cells)</Label>
                        <Input
                          type="number"
                          min={1}
                          max={dimensions.cols}
                          value={bg.width}
                          onChange={(e) =>
                            updateSpan(bg.id, {
                              width: Number(e.target.value) || 1,
                            })
                          }
                          data-testid={`background-width-${bg.id}`}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Height (cells)</Label>
                        <Input
                          type="number"
                          min={1}
                          max={dimensions.rows}
                          value={bg.height}
                          onChange={(e) =>
                            updateSpan(bg.id, { height: Number(e.target.value) || 1 })
                          }
                          data-testid={`background-height-${bg.id}`}
                        />
                      </div>
                    </div>
                  </div>
                ))}

                <Button
                  variant="outline"
                  onClick={addSpan}
                  className="w-full"
                  data-testid="add-background"
                >
                  <ImagePlus className="mr-2 h-4 w-4" />
                  Add background
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Live preview grid */}
        <ScrollArea className="flex-1">
          <div className="mx-auto max-w-4xl p-6">
            {!effectiveConfig ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                The deck preview appears here once a config is selected.
              </div>
            ) : (
              <div
                className="grid gap-2"
                style={{
                  gridTemplateColumns: `repeat(${dimensions.cols}, 1fr)`,
                }}
                data-testid="backgrounds-preview-grid"
              >
                {Array.from({ length: totalButtons }).map((_, index) => {
                  const covering = coveringSpan(index);
                  const button = (effectiveConfig.buttons ?? []).find(
                    (b) => b.index === index
                  );
                  const hasOwnImage = !!button?.idle?.image;
                  return (
                    <div
                      key={index}
                      data-testid={
                        covering && !hasOwnImage
                          ? `covered-cell-${index}`
                          : undefined
                      }
                      className="streamdeck-button relative flex aspect-square items-center justify-center"
                    >
                      {covering && !hasOwnImage && (
                        <div
                          aria-hidden
                          className="absolute inset-0 rounded-lg"
                          style={tileStyle(covering, index)}
                        />
                      )}
                      <span className="relative z-10 text-xs text-muted-foreground/70">
                        {index + 1}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
            {effectiveConfig && (
              <p className="mt-4 text-xs text-muted-foreground">
                The preview mirrors the runner: each cell shows its exact crop of
                the span. Buttons with their own image stay on top.
              </p>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}