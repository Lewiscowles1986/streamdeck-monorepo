import { cn } from "@/lib/utils";
import type { ButtonConfig } from "@/types/streamdeck";
import { Command, ToggleLeft } from "lucide-react";

interface ButtonCellProps {
  button?: ButtonConfig;
  index: number;
  isSelected: boolean;
  onClick: () => void;
}

export function ButtonCell({ button, index, isSelected, onClick }: ButtonCellProps) {
  const hasImage = button?.idle?.image;
  const hasText = button?.idle?.text;
  const hasAction = button?.action;
  const isToggle = button?.isToggle;

  return (
    <button
      onClick={onClick}
      className={cn(
        "streamdeck-button relative flex aspect-square flex-col items-center justify-center p-1",
        isSelected && "selected"
      )}
    >
      {/* Background image */}
      {hasImage && (
        <img
          src={button.idle!.image}
          alt=""
          className="absolute inset-1 h-[calc(100%-8px)] w-[calc(100%-8px)] rounded object-cover"
        />
      )}

      {/* Text overlay */}
      {hasText && (
        <span
          className={cn(
            "relative z-10 truncate text-center text-xs font-medium",
            hasImage ? "text-white drop-shadow-lg" : "text-foreground"
          )}
          style={{
            color: button.idle?.font?.color,
            fontSize: button.idle?.font?.size ? `${button.idle.font.size}px` : undefined,
          }}
        >
          {button.idle!.text}
        </span>
      )}

      {/* Empty state - show index */}
      {!hasImage && !hasText && (
        <span className="text-xs text-muted-foreground">{index + 1}</span>
      )}

      {/* Indicators */}
      <div className="absolute bottom-1 right-1 flex gap-0.5">
        {hasAction && (
          <div className="flex h-4 w-4 items-center justify-center rounded-sm bg-accent/20">
            <Command className="h-2.5 w-2.5 text-accent" />
          </div>
        )}
        {isToggle && (
          <div className="flex h-4 w-4 items-center justify-center rounded-sm bg-primary/20">
            <ToggleLeft className="h-2.5 w-2.5 text-primary" />
          </div>
        )}
      </div>
    </button>
  );
}
