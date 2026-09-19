import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, AlertCircle, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DeviceCard } from "@/components/streamdeck/DeviceCard";
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
import { useToast } from "@/hooks/use-toast";
import { devicesApi, configsApi, agentsApi } from "@/lib/api";
import { useApi } from "@/contexts/ApiContext";
import { TryDemoButton } from "@/components/streamdeck/DemoBanner";
import type { Device, StreamDeckConfig, Agent } from "@/types/streamdeck";

export default function Dashboard() {
  const { isConnected } = useApi();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [selectedConfigId, setSelectedConfigId] = useState<string>("");
  const [nominateDialogOpen, setNominateDialogOpen] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");

  const {
    data: devices = [],
    isLoading: devicesLoading,
    error: devicesError,
    refetch: refetchDevices,
  } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.getAll,
    enabled: isConnected,
  });

  const { data: configs = [] } = useQuery({
    queryKey: ["configs"],
    queryFn: configsApi.getAll,
    enabled: isConnected,
  });

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: agentsApi.getAll,
    enabled: isConnected,
  });

  const assignMutation = useMutation({
    mutationFn: ({ deviceId, configId }: { deviceId: string; configId: string }) =>
      devicesApi.assignConfig(deviceId, configId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      toast({ title: "Config assigned", description: "Configuration has been applied to the device." });
      setAssignDialogOpen(false);
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const nominateMutation = useMutation({
    mutationFn: ({ deviceId, agentId }: { deviceId: string; agentId: string }) =>
      devicesApi.nominateAgent(deviceId, agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      toast({ title: "Agent nominated", description: "Command actions on this device will run on the nominated computer." });
      setNominateDialogOpen(false);
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const clearAgentMutation = useMutation({
    mutationFn: (deviceId: string) => devicesApi.clearAgent(deviceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      toast({ title: "Agent cleared", description: "Command actions will run locally again." });
    },
    onError: (error) => {
      toast({ title: "Error", description: String(error), variant: "destructive" });
    },
  });

  const handleAssignConfig = (deviceId: string) => {
    setSelectedDeviceId(deviceId);
    setSelectedConfigId("");
    setAssignDialogOpen(true);
  };

  const handleNominateAgent = (deviceId: string) => {
    setSelectedDeviceId(deviceId);
    setSelectedAgentId("");
    setNominateDialogOpen(true);
  };

  const handleConfirmAssign = () => {
    if (selectedDeviceId && selectedConfigId) {
      assignMutation.mutate({ deviceId: selectedDeviceId, configId: selectedConfigId });
    }
  };

  const handleConfirmNominate = () => {
    if (selectedDeviceId && selectedAgentId) {
      nominateMutation.mutate({ deviceId: selectedDeviceId, agentId: selectedAgentId });
    }
  };

  if (!isConnected) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8">
        <AlertCircle className="mb-4 h-16 w-16 text-muted-foreground" />
        <h2 className="mb-2 text-xl font-semibold">Not Connected</h2>
        <p className="mb-4 text-center text-muted-foreground">
          Unable to connect to the Stream Deck API.
          <br />
          Please check your settings.
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
          <h1 className="text-2xl font-bold">Devices</h1>
          <p className="text-muted-foreground">Manage your connected Stream Deck devices</p>
        </div>
        <Button
          variant="outline"
          onClick={() => refetchDevices()}
          disabled={devicesLoading}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${devicesLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {devicesError ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
          <AlertCircle className="mx-auto mb-2 h-8 w-8 text-destructive" />
          <p className="text-destructive">Failed to load devices</p>
          <p className="text-sm text-muted-foreground">{String(devicesError)}</p>
        </div>
      ) : devicesLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-lg bg-secondary" />
          ))}
        </div>
      ) : devices.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16">
          <Monitor className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-medium">No devices found</h3>
          <p className="text-sm text-muted-foreground">Connect a Stream Deck device to get started</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {devices.map((device: Device) => (
            <DeviceCard
              key={device.id}
              device={device}
              onAssignConfig={handleAssignConfig}
              onNominateAgent={handleNominateAgent}
              onClearAgent={(deviceId) => clearAgentMutation.mutate(deviceId)}
            />
          ))}
        </div>
      )}

      <Dialog open={nominateDialogOpen} onOpenChange={setNominateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nominate a Computer</DialogTitle>
            <DialogDescription>
              Command actions from this device will execute on the nominated
              computer (running `streamdeck agent`).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {agents.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No agents registered yet. Run <code>streamdeck agent</code> on
                the computer you want to control.
              </p>
            ) : (
              <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a computer" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent: Agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.hostname}
                      {agent.user ? ` (${agent.user})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setNominateDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleConfirmNominate}
                disabled={!selectedAgentId || nominateMutation.isPending}
              >
                {nominateMutation.isPending ? "Nominating..." : "Nominate"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign Configuration</DialogTitle>
            <DialogDescription>
              Select a configuration to apply to this device.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Select value={selectedConfigId} onValueChange={setSelectedConfigId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a configuration" />
              </SelectTrigger>
              <SelectContent>
                {configs.map((config: StreamDeckConfig) => (
                  <SelectItem key={config.id} value={config.id!}>
                    {config.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleConfirmAssign}
                disabled={!selectedConfigId || assignMutation.isPending}
              >
                {assignMutation.isPending ? "Assigning..." : "Assign"}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
