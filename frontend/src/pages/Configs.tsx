import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, AlertCircle, LayoutGrid, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ConfigCard } from "@/components/streamdeck/ConfigCard";
import { useToast } from "@/hooks/use-toast";
import { configsApi } from "@/lib/api";
import { useApi } from "@/contexts/ApiContext";
import { TryDemoButton } from "@/components/streamdeck/DemoBanner";
import type { StreamDeckConfig, DeviceType } from "@/types/streamdeck";
import { DEVICE_DIMENSIONS } from "@/types/streamdeck";

const DEVICE_TYPES: { value: DeviceType; label: string }[] = [
  { value: "stream-deck-xl", label: "Stream Deck XL (8×4)" },
  { value: "stream-deck", label: "Stream Deck (5×3)" },
  { value: "stream-deck-mk2", label: "Stream Deck MK.2 (5×3)" },
  { value: "stream-deck-mini", label: "Stream Deck Mini (3×2)" },
  { value: "stream-deck-plus", label: "Stream Deck + (4×2)" },
];

export default function Configs() {
  const navigate = useNavigate();
  const { isConnected } = useApi();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newConfigName, setNewConfigName] = useState("");
  const [newConfigDeviceType, setNewConfigDeviceType] = useState<DeviceType>("stream-deck-xl");
  const [searchQuery, setSearchQuery] = useState("");

  const {
    data: configs = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["configs"],
    queryFn: configsApi.getAll,
    enabled: isConnected,
  });

  const createMutation = useMutation({
    mutationFn: configsApi.create,
    onSuccess: (newConfig) => {
      queryClient.invalidateQueries({ queryKey: ["configs"] });
      toast({ title: "Config created", description: `"${newConfig.name}" has been created.` });
      setCreateDialogOpen(false);
      setNewConfigName("");
      navigate(`/config/${newConfig.id}`);
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: configsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configs"] });
      toast({ title: "Config deleted" });
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const handleCreate = () => {
    if (!newConfigName.trim()) return;
    const dimensions = DEVICE_DIMENSIONS[newConfigDeviceType];
    createMutation.mutate({
      name: newConfigName.trim(),
      deviceType: newConfigDeviceType,
      buttons: [],
    });
  };

  const handleDuplicate = (config: StreamDeckConfig) => {
    createMutation.mutate({
      name: `${config.name} (Copy)`,
      deviceType: config?.deviceType ?? config?.device_type,
      buttons: config.buttons,
    });
  };

  const filteredConfigs = configs.filter((config: StreamDeckConfig) =>
    config.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (!isConnected) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8">
        <AlertCircle className="mb-4 h-16 w-16 text-muted-foreground" />
        <h2 className="mb-2 text-xl font-semibold">Not Connected</h2>
        <p className="mb-4 text-center text-muted-foreground">
          Unable to connect to the Stream Deck API.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <a href="/settings">Go to Settings</a>
          </Button>
          <TryDemoButton />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Configurations</h1>
          <p className="text-muted-foreground">Create and manage button layouts</p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Config
        </Button>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search configurations..."
          className="pl-10"
        />
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
          <AlertCircle className="mx-auto mb-2 h-8 w-8 text-destructive" />
          <p className="text-destructive">Failed to load configurations</p>
        </div>
      ) : isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-64 animate-pulse rounded-lg bg-secondary" />
          ))}
        </div>
      ) : filteredConfigs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16">
          <LayoutGrid className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-medium">
            {searchQuery ? "No configs match your search" : "No configurations"}
          </h3>
          <p className="mb-4 text-sm text-muted-foreground">
            {searchQuery ? "Try a different search term" : "Create your first button layout"}
          </p>
          {!searchQuery && (
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Config
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredConfigs.map((config: StreamDeckConfig) => (
            <ConfigCard
              key={config.id}
              config={config}
              onDelete={(id) => deleteMutation.mutate(id)}
              onDuplicate={handleDuplicate}
            />
          ))}
        </div>
      )}

      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Configuration</DialogTitle>
            <DialogDescription>
              Set up a new button layout for your Stream Deck.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Configuration Name</Label>
              <Input
                value={newConfigName}
                onChange={(e) => setNewConfigName(e.target.value)}
                placeholder="My Gaming Layout"
              />
            </div>
            <div className="space-y-2">
              <Label>Target Device</Label>
              <Select
                value={newConfigDeviceType}
                onValueChange={(v) => setNewConfigDeviceType(v as DeviceType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DEVICE_TYPES.map((d) => (
                    <SelectItem key={d.value} value={d.value}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={!newConfigName.trim() || createMutation.isPending}
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
