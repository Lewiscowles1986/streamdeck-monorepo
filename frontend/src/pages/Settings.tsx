import { useState } from "react";
import { Check, Loader2, Server, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { useApi } from "@/contexts/ApiContext";

export default function Settings() {
  const { apiBaseUrl, setApiBaseUrl, isConnected, isChecking, checkConnection } = useApi();
  const { toast } = useToast();
  const [urlInput, setUrlInput] = useState(apiBaseUrl);

  const handleSave = async () => {
    setApiBaseUrl(urlInput);
    const connected = await checkConnection();
    if (connected) {
      toast({ title: "Connected", description: "Successfully connected to the API." });
    } else {
      toast({
        title: "Connection failed",
        description: "Could not connect to the API. Please check the URL.",
        variant: "destructive",
      });
    }
  };

  const handleTest = async () => {
    const originalUrl = apiBaseUrl;
    setApiBaseUrl(urlInput);
    const connected = await checkConnection();
    if (!connected) {
      setApiBaseUrl(originalUrl);
    }
    toast({
      title: connected ? "Connection successful" : "Connection failed",
      description: connected
        ? "API is reachable at this URL."
        : "Could not reach the API. Check the URL and ensure CORS is enabled.",
      variant: connected ? "default" : "destructive",
    });
  };

  return (
    <div className="flex-1 space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure your Stream Deck Manager</p>
      </div>

      <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              API Connection
            </CardTitle>
            <CardDescription>
              Configure the connection to your Stream Deck backend API
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="api-url">API Base URL</Label>
              <div className="flex gap-2">
                <Input
                  id="api-url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="flex-1"
                />
                <Button variant="outline" onClick={handleTest} disabled={isChecking}>
                  {isChecking ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Enter the base URL of your Python backend. Make sure CORS is enabled.
              </p>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/50 p-4">
              <div className="flex items-center gap-3">
                <div
                  className={`h-3 w-3 rounded-full ${
                    isConnected ? "bg-success animate-pulse" : "bg-destructive"
                  }`}
                />
                <div>
                  <p className="text-sm font-medium">
                    {isConnected ? "Connected" : "Disconnected"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {isConnected
                      ? "API is reachable and responding"
                      : "Unable to reach the API server"}
                  </p>
                </div>
              </div>
              {isConnected && <Check className="h-5 w-5 text-success" />}
            </div>

            <Button onClick={handleSave} disabled={isChecking} className="w-full">
              {isChecking ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing connection...
                </>
              ) : (
                "Save & Connect"
              )}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>API Documentation</CardTitle>
            <CardDescription>
              Your backend should implement these endpoints
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/20 px-2 py-0.5 text-xs text-primary">
                  GET
                </span>
                <span className="text-muted-foreground">/devices</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-warning/20 px-2 py-0.5 text-xs text-warning">
                  PUT
                </span>
                <span className="text-muted-foreground">
                  /device/{"{device-id}"}/config/{"{config-id}"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-success/20 px-2 py-0.5 text-xs text-success">
                  POST
                </span>
                <span className="text-muted-foreground">/config</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/20 px-2 py-0.5 text-xs text-primary">
                  GET
                </span>
                <span className="text-muted-foreground">/config/{"{config-id}"}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-warning/20 px-2 py-0.5 text-xs text-warning">
                  PUT
                </span>
                <span className="text-muted-foreground">/config/{"{config-id}"}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/20 px-2 py-0.5 text-xs text-primary">
                  GET
                </span>
                <span className="text-muted-foreground">/configs</span>
                <span className="text-xs text-muted-foreground">(list all)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-destructive/20 px-2 py-0.5 text-xs text-destructive">
                  DELETE
                </span>
                <span className="text-muted-foreground">/config/{"{config-id}"}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
