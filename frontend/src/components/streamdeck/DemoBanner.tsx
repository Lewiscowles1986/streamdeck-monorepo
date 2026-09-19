import { FlaskConical, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApi } from "@/contexts/ApiContext";

/**
 * DemoBanner — shown while the UI runs against the in-browser mock
 * (no server, no device). Communicates the "mindshare without hardware" mode.
 */
export function DemoBanner() {
  const { isDemo, exitDemoMode } = useApi();
  if (!isDemo) return null;

  return (
    <div className="flex items-center justify-between gap-4 border-b border-primary/30 bg-primary/10 px-4 py-2 text-sm">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-primary" />
        <span>
          <strong>Demo mode</strong> — no server required; data is stored in this
          browser only.
        </span>
      </div>
      <Button variant="ghost" size="sm" onClick={exitDemoMode}>
        <X className="mr-1 h-3 w-3" />
        Exit demo
      </Button>
    </div>
  );
}

/** CTA shown when the real API is unreachable: enter demo instead of dead-ending. */
export function TryDemoButton() {
  const { enterDemoMode } = useApi();
  return (
    <Button variant="secondary" onClick={enterDemoMode}>
      <FlaskConical className="mr-2 h-4 w-4" />
      Try demo mode (no server)
    </Button>
  );
}