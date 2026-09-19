import { ButtonCell } from "./ButtonCell";
import type { ButtonConfig, DeviceType } from "@/types/streamdeck";
import { deviceDimensions } from "@/types/streamdeck";

interface ButtonGridProps {
  deviceType?: DeviceType;
  buttons: ButtonConfig[];
  selectedIndex: number | null;
  onSelectButton: (index: number) => void;
}

export function ButtonGrid({
  deviceType,
  buttons,
  selectedIndex,
  onSelectButton,
}: ButtonGridProps) {
  const dimensions = deviceDimensions(deviceType);
  const totalButtons = dimensions.rows * dimensions.cols;

  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <div
        className="grid gap-2"
        style={{
          gridTemplateColumns: `repeat(${dimensions.cols}, 1fr)`,
        }}
      >
        {Array.from({ length: totalButtons }).map((_, index) => {
          const button = (buttons ?? []).find((b) => b.index === index);
          return (
            <ButtonCell
              key={index}
              index={index}
              button={button}
              isSelected={selectedIndex === index}
              onClick={() => onSelectButton(index)}
            />
          );
        })}
      </div>

      {/* Grid info */}
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {dimensions.cols}×{dimensions.rows} grid ({totalButtons} buttons)
        </span>
        <span>Click a button to edit</span>
      </div>
    </div>
  );
}
