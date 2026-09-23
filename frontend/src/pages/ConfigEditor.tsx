import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save, Code, Eye, Loader2, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ButtonGrid } from "@/components/streamdeck/ButtonGrid";
import { ButtonEditor } from "@/components/streamdeck/ButtonEditor";
import { TriggersEditor } from "@/components/streamdeck/TriggersEditor";
import { useToast } from "@/hooks/use-toast";
import { configsApi } from "@/lib/api";
import type { StreamDeckConfig, ButtonConfig } from "@/types/streamdeck";

export default function ConfigEditor() {
  const { configId } = useParams<{ configId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [config, setConfig] = useState<StreamDeckConfig | null>(null);
  const [selectedButtonIndex, setSelectedButtonIndex] = useState<number | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  const { data: loadedConfig, isLoading, error } = useQuery({
    queryKey: ["config", configId],
    queryFn: () => configsApi.getById(configId!),
    enabled: !!configId,
  });

  useEffect(() => {
    if (loadedConfig) {
      setConfig(loadedConfig);
      setHasChanges(false);
    }
  }, [loadedConfig]);

  const saveMutation = useMutation({
    mutationFn: (updatedConfig: StreamDeckConfig) =>
      configsApi.update(configId!, updatedConfig),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configs"] });
      queryClient.invalidateQueries({ queryKey: ["config", configId] });
      toast({ title: "Saved", description: "Configuration saved successfully." });
      setHasChanges(false);
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const handleNameChange = (name: string) => {
    if (!config) return;
    setConfig({ ...config, name });
    setHasChanges(true);
  };

  const handleTriggersChange = (triggers: StreamDeckConfig["triggers"]) => {
    if (!config) return;
    setConfig({ ...config, triggers });
    setHasChanges(true);
  };

  const handleButtonChange = (updatedButton: ButtonConfig) => {
    if (!config) return;
    const existingIndex = (config?.buttons ?? []).findIndex((b) => b.index === updatedButton.index);
    let newButtons: ButtonConfig[];

    if (existingIndex >= 0) {
      newButtons = (config?.buttons ?? []).map((b, i) =>
        i === existingIndex ? updatedButton : b
      );
    } else {
      const oldButtons =  (config?.buttons ?? [])
      newButtons = [...oldButtons, updatedButton];
    }

    setConfig({ ...config, buttons: newButtons });
    setHasChanges(true);
  };

  const handleSelectButton = (index: number) => {
    setSelectedButtonIndex(index);
  };

  const handleSave = () => {
    if (config) {
      saveMutation.mutate(config);
    }
  };

  const selectedButton = (config?.buttons ?? []).find((b) => b.index === selectedButtonIndex) || (
    selectedButtonIndex !== null ? { index: selectedButtonIndex } : null
  );

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8">
        <p className="mb-4 text-destructive">Failed to load configuration</p>
        <Button variant="outline" onClick={() => navigate("/configs")}>
          Back to Configs
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-card/50 px-6 py-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate("/configs")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-3">
            <Input
              value={config.name}
              onChange={(e) => handleNameChange(e.target.value)}
              className="w-64 border-none bg-transparent text-lg font-semibold focus-visible:ring-1"
            />
            {hasChanges && (
              <span className="text-xs text-warning">Unsaved changes</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => navigate(`/config/${configId}/backgrounds`)}
            data-testid="open-backgrounds"
          >
            <Layers className="mr-2 h-4 w-4" />
            Backgrounds
          </Button>
          <Button
            onClick={handleSave}
            disabled={!hasChanges || saveMutation.isPending}
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
      </div>

      {/* Editor Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Main grid area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <Tabs defaultValue="visual" className="flex flex-1 flex-col">
            <div className="border-b border-border px-6 py-2">
              <TabsList>
                <TabsTrigger value="visual" className="gap-2">
                  <Eye className="h-4 w-4" />
                  Visual Editor
                </TabsTrigger>
                <TabsTrigger value="json" className="gap-2">
                  <Code className="h-4 w-4" />
                  JSON View
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="visual" className="mt-0 flex-1 overflow-auto p-6">
              <div className="mx-auto max-w-4xl space-y-4">
                <TriggersEditor
                  triggers={config.triggers}
                  onChange={handleTriggersChange}
                />
                <ButtonGrid
                  deviceType={config?.deviceType ?? config?.device_type}
                  buttons={config.buttons}
                  selectedIndex={selectedButtonIndex}
                  onSelectButton={handleSelectButton}
                  backgrounds={config.backgrounds}
                />
              </div>
            </TabsContent>

            <TabsContent value="json" className="mt-0 flex-1 overflow-auto p-6">
              <ScrollArea className="h-full">
                <pre className="rounded-lg bg-secondary p-4 text-sm">
                  {JSON.stringify(config, null, 2)}
                </pre>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>

        {/* Button editor panel */}
        {selectedButton && (
          <div className="w-96 shrink-0">
            <ButtonEditor
              button={selectedButton as ButtonConfig}
              onChange={handleButtonChange}
              onClose={() => setSelectedButtonIndex(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
