import { ButtonCell } from "./ButtonCell";
import type { ButtonConfig, DeviceType, BackgroundSpan } from "@/types/streamdeck";
import { deviceDimensions } from "@/types/streamdeck";

interface ButtonGridProps {
  deviceType?: DeviceType;
  buttons: ButtonConfig[];
  selectedIndex: number | null;
  onSelectButton: (index: number) => void;
  /** P19: image spans shown behind cells with no image of their own. */
  backgrounds?: BackgroundSpan[] | null;
}

/**
 * The background tile for one key cell, as CSS: the span's image scaled to
 * cover the WHOLE region (background-size = width×100% / height×100% of the
 * cell) and offset so this cell shows its exact crop. Mirrors the runner's
 * composite-then-slice, so the editor preview matches the deck.
 */
function backgroundTileStyle(
  bg: BackgroundSpan,
  index: number,
  cols: number
): React.CSSProperties | undefined {
  const row = Math.floor(index / cols);
  const col = index % cols;
  const inside =
    col >= bg.x && col < bg.x + bg.width && row >= bg.y && row < bg.y + bg.height;
  if (!inside) return undefined;
  return {
    backgroundImage: `url(${bg.image})`,
    backgroundSize: `${bg.width * 100}% ${bg.height * 100}%`,
    backgroundPosition: `${((bg.x - col) / bg.width) * 100}% ${
      ((bg.y - row) / bg.height) * 100
    }%`,
  };
}

export function ButtonGrid({
  deviceType,
  buttons,
  selectedIndex,
  onSelectButton,
  backgrounds,
}: ButtonGridProps) {
  const dimensions = deviceDimensions(deviceType);
  const totalButtons = dimensions.rows * dimensions.cols;
  const spans = backgrounds ?? [];

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
          // A cell with no image of its own shows the tile of the LAST
          // span covering it (z-order: later entries composite over
          // earlier ones — same rule the runner applies).
          const covering = button?.idle?.image
            ? undefined
            : [...spans]
                .reverse()
                .find(
                  (bg) =>
                    backgroundTileStyle(bg, index, dimensions.cols) !== undefined
                );
          return (
            <div key={index} className="relative">
              {covering && (
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0 rounded-lg"
                  style={backgroundTileStyle(covering, index, dimensions.cols)}
                />
              )}
              <ButtonCell
                index={index}
                button={button}
                isSelected={selectedIndex === index}
                onClick={() => onSelectButton(index)}
              />
            </div>
          );
        })}
      </div>

      {/* Grid info */}
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {dimensions.cols}×{dimensions.rows} grid ({totalButtons} buttons)
          {spans.length > 0 && ` · ${spans.length} background${spans.length > 1 ? "s" : ""}`}
        </span>
        <span>Click a button to edit</span>
      </div>
    </div>
  );
}
