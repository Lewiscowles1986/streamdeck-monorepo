import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { getApiBaseUrl, setApiBaseUrl as setStoredApiUrl, testConnection } from "@/lib/api";
import { isDemoMode, enableDemoMode, disableDemoMode } from "@/lib/demo-api";

interface ApiContextType {
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  isConnected: boolean;
  isChecking: boolean;
  isDemo: boolean;
  enterDemoMode: () => void;
  exitDemoMode: () => void;
  checkConnection: () => Promise<boolean>;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const [apiBaseUrl, setApiBaseUrlState] = useState(getApiBaseUrl());
  const [isConnected, setIsConnected] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [isDemo, setIsDemo] = useState(isDemoMode());

  const checkConnection = useCallback(async () => {
    setIsChecking(true);
    try {
      const connected = await testConnection();
      setIsConnected(connected);
      return connected;
    } finally {
      setIsChecking(false);
    }
  }, []);

  const setApiBaseUrl = useCallback((url: string) => {
    setStoredApiUrl(url);
    setApiBaseUrlState(url);
    setIsConnected(false);
  }, []);

  const enterDemoMode = useCallback(() => {
    enableDemoMode();
    setIsDemo(true);
    setIsConnected(true);
  }, []);

  const exitDemoMode = useCallback(() => {
    disableDemoMode();
    setIsDemo(false);
    setIsConnected(false);
  }, []);

  // Check connection on mount
  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  return (
    <ApiContext.Provider
      value={{
        apiBaseUrl,
        setApiBaseUrl,
        isConnected: isConnected || isDemo,
        isChecking,
        isDemo,
        enterDemoMode,
        exitDemoMode,
        checkConnection,
      }}
    >
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error("useApi must be used within an ApiProvider");
  }
  return context;
}
