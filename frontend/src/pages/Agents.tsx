import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, AlertCircle, Laptop, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { agentsApi, devicesApi } from "@/lib/api";
import { useApi } from "@/contexts/ApiContext";
import { TryDemoButton } from "@/components/streamdeck/DemoBanner";
import type { Agent, Device } from "@/types/streamdeck";

/**
 * Agents page — "nominate a computer" management surface.
 *
 * Lists every machine registered via `streamdeck agent`, which devices
 * nominated them, and lets an operator remove a computer (which also
 * clears any device nominations, mirroring DELETE /agents/{id}).
 */
export default function Agents() {
  const { isConnected } = useApi();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const {
    data: agents = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: agentsApi.getAll,
    enabled: isConnected,
  });

  const { data: devices = [] } = useQuery({
    queryKey: ["devices"],
    queryFn: devicesApi.getAll,
    enabled: isConnected,
  });

  const deleteMutation = useMutation({
    mutationFn: (agentId: string) => agentsApi.delete(agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      toast({ title: "Agent removed", description: "Device nominations were cleared." });
    },
    onError: (err) => {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    },
  });

  const nominateMutation = useMutation({
    mutationFn: ({ deviceId, agentId }: { deviceId: string; agentId: string }) =>
      devicesApi.nominateAgent(deviceId, agentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      toast({ title: "Agent nominated" });
    },
    onError: (err) => {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    },
  });

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

  const nominatedByDevice = (agentId: string): Device | undefined =>
    devices.find(
      (d) => (d.activeAgentId ?? d.active_agent_id) === agentId
    );

  return (
    <div className="flex-1 space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agents</h1>
          <p className="text-muted-foreground">
            Computers running <code>streamdeck agent</code> that can execute
            button commands
          </p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {agents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16">
          <Laptop className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-medium">No agents registered</h3>
          <p className="text-sm text-muted-foreground">
            Run <code>streamdeck agent</code> on a computer to register it here.
          </p>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Registered computers</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Hostname</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Nominated by</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((agent: Agent) => {
                  const device = nominatedByDevice(agent.id);
                  return (
                    <TableRow key={agent.id}>
                      <TableCell className="font-medium">{agent.hostname}</TableCell>
                      <TableCell>{agent.user ?? "—"}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {agent.platform ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={agent.active === false ? "secondary" : "default"}
                          className={agent.active === false ? "" : "bg-success/20 text-success"}
                        >
                          {agent.active === false ? "Inactive" : "Active"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {device ? (
                          device.name || device.id
                        ) : (
                          <span className="text-muted-foreground">None</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive"
                          onClick={() => deleteMutation.mutate(agent.id)}
                          title="Remove agent (clears nominations)"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {agents.length > 0 && devices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Nominate for a device</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {devices.map((device: Device) => {
              const current = device.activeAgentId ?? device.active_agent_id;
              return (
                <div
                  key={device.id}
                  className="flex items-center justify-between rounded-lg border border-border p-3"
                >
                  <div>
                    <p className="text-sm font-medium">{device.name || device.id}</p>
                    <p className="text-xs text-muted-foreground">
                      {current ? `Agent: ${current}` : "No agent nominated"}
                    </p>
                  </div>
                  {current ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => nominateMutation.mutate({ deviceId: device.id, agentId: current })}
                      disabled={nominateMutation.isPending}
                    >
                      Refresh nomination
                    </Button>
                  ) : (
                    <SelectNominate
                      agents={agents}
                      onSubmit={(agentId) =>
                        nominateMutation.mutate({ deviceId: device.id, agentId })
                      }
                      pending={nominateMutation.isPending}
                    />
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SelectNominate({
  agents,
  onSubmit,
  pending,
}: {
  agents: Agent[];
  onSubmit: (agentId: string) => void;
  pending: boolean;
}) {
  const [agentId, setAgentId] = useState("");
  return (
    <div className="flex items-center gap-2">
      <select
        className="h-9 rounded-md border border-border bg-transparent px-2 text-sm"
        value={agentId}
        onChange={(e) => setAgentId(e.target.value)}
      >
        <option value="">Select computer…</option>
        {agents.map((a: Agent) => (
          <option key={a.id} value={a.id}>
            {a.hostname}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        disabled={!agentId || pending}
        onClick={() => onSubmit(agentId)}
      >
        Nominate
      </Button>
    </div>
  );
}