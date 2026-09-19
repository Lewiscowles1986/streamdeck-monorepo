import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/streamdeck/AppSidebar";
import { DemoBanner } from "@/components/streamdeck/DemoBanner";
import { ApiProvider } from "@/contexts/ApiContext";
import Dashboard from "./pages/Dashboard";
import Configs from "./pages/Configs";
import ConfigEditor from "./pages/ConfigEditor";
import Agents from "./pages/Agents";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ApiProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <SidebarProvider>
            <div className="flex min-h-screen w-full dark">
              <AppSidebar />
              <main className="flex flex-1 flex-col">
                <header className="flex h-12 items-center border-b border-border px-4">
                  <SidebarTrigger />
                </header>
                <DemoBanner />
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/configs" element={<Configs />} />
                  <Route path="/config/:configId" element={<ConfigEditor />} />
                  <Route path="/agents" element={<Agents />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </main>
            </div>
          </SidebarProvider>
        </BrowserRouter>
      </ApiProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
