import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ImageUpload } from "./ImageUpload";
import { ActionEditor } from "./ActionEditor";
import { ToggleEditor } from "./ToggleEditor";
import type { ButtonConfig, ButtonAppearance, FontConfig } from "@/types/streamdeck";

interface ButtonEditorProps {
  button: ButtonConfig;
  onChange: (button: ButtonConfig) => void;
  onClose: () => void;
}

const FONT_FAMILIES = [
  { value: "sans-serif", label: "Sans Serif" },
  { value: "serif", label: "Serif" },
  { value: "monospace", label: "Monospace" },
  { value: "Arial", label: "Arial" },
  { value: "Helvetica", label: "Helvetica" },
  { value: "Roboto", label: "Roboto" },
];

const FONT_POSITIONS = [
  { value: "top", label: "Top" },
  { value: "center", label: "Center" },
  { value: "bottom", label: "Bottom" },
];

export function ButtonEditor({ button, onChange, onClose }: ButtonEditorProps) {
  const updateAppearance = (
    state: "idle" | "pressed",
    updates: Partial<ButtonAppearance>
  ) => {
    const current = button[state] || {};
    onChange({
      ...button,
      [state]: { ...current, ...updates },
    });
  };

  const updateFont = (state: "idle" | "pressed", updates: Partial<FontConfig>) => {
    const current = button[state] || {};
    const currentFont = current.font || {};
    onChange({
      ...button,
      [state]: {
        ...current,
        font: { ...currentFont, ...updates },
      },
    });
  };

  const AppearanceEditor = ({ state }: { state: "idle" | "pressed" }) => {
    const appearance = button[state] || {};
    const font = appearance.font || {};

    return (
      <div className="space-y-4">
        <ImageUpload
          value={appearance.image}
          onChange={(image) => updateAppearance(state, { image })}
          label={state === "idle" ? "Idle Image" : "Pressed Image"}
        />

        <div className="space-y-2">
          <Label>Text</Label>
          <Input
            value={appearance.text || ""}
            onChange={(e) => updateAppearance(state, { text: e.target.value })}
            placeholder="Button text"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label>Font Family</Label>
            <Select
              value={font.family || "sans-serif"}
              onValueChange={(value) => updateFont(state, { family: value })}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FONT_FAMILIES.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Font Size</Label>
            <Input
              type="number"
              value={font.size || 14}
              onChange={(e) => updateFont(state, { size: parseInt(e.target.value) || 14 })}
              min={8}
              max={48}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label>Text Color</Label>
            <div className="flex gap-2">
              <Input
                type="color"
                value={font.color || "#ffffff"}
                onChange={(e) => updateFont(state, { color: e.target.value })}
                className="h-9 w-12 p-1"
              />
              <Input
                value={font.color || "#ffffff"}
                onChange={(e) => updateFont(state, { color: e.target.value })}
                className="flex-1"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Text Position</Label>
            <Select
              value={font.position || "center"}
              onValueChange={(value: "top" | "center" | "bottom") =>
                updateFont(state, { position: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FONT_POSITIONS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col border-l border-border bg-card">
      <div className="flex items-center justify-between border-b border-border p-4">
        <div>
          <h3 className="font-semibold">Button {button.index + 1}</h3>
          <p className="text-xs text-muted-foreground">Edit button configuration</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4">
          <Tabs defaultValue="idle" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="idle">Idle</TabsTrigger>
              <TabsTrigger value="pressed">Pressed</TabsTrigger>
              <TabsTrigger value="action">Action</TabsTrigger>
            </TabsList>

            <TabsContent value="idle" className="mt-4">
              <AppearanceEditor state="idle" />
            </TabsContent>

            <TabsContent value="pressed" className="mt-4">
              <AppearanceEditor state="pressed" />
            </TabsContent>

            <TabsContent value="action" className="mt-4 space-y-6">
              <ActionEditor
                action={button.action}
                onChange={(action) => onChange({ ...button, action })}
              />

              <div className="border-t border-border pt-4">
                <ToggleEditor
                  isToggle={button.isToggle || false}
                  toggleStates={button.toggleStates || []}
                  onToggleChange={(isToggle) => onChange({ ...button, isToggle })}
                  onStatesChange={(toggleStates) => onChange({ ...button, toggleStates })}
                />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  );
}
