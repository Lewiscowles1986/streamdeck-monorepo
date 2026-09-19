import { Plus, Trash2, GripVertical } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { ActionEditor } from "./ActionEditor";
import type { ToggleState, ButtonAction } from "@/types/streamdeck";

interface ToggleEditorProps {
  isToggle: boolean;
  toggleStates: ToggleState[];
  onToggleChange: (isToggle: boolean) => void;
  onStatesChange: (states: ToggleState[]) => void;
}

export function ToggleEditor({
  isToggle,
  toggleStates,
  onToggleChange,
  onStatesChange,
}: ToggleEditorProps) {
  const addState = () => {
    onStatesChange([
      ...toggleStates,
      {
        name: `State ${toggleStates.length + 1}`,
      },
    ]);
  };

  const updateState = (index: number, updates: Partial<ToggleState>) => {
    const newStates = toggleStates.map((state, i) =>
      i === index ? { ...state, ...updates } : state
    );
    onStatesChange(newStates);
  };

  const removeState = (index: number) => {
    if (toggleStates.length <= 2) return; // Minimum 2 states for toggle
    onStatesChange(toggleStates.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Label>Toggle Mode</Label>
          <p className="text-xs text-muted-foreground">
            Enable to cycle through multiple states
          </p>
        </div>
        <Switch
          checked={isToggle}
          onCheckedChange={(checked) => {
            onToggleChange(checked);
            if (checked && toggleStates.length === 0) {
              onStatesChange([
                { name: "State 1" },
                { name: "State 2" },
              ]);
            }
          }}
        />
      </div>

      {isToggle && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Toggle States ({toggleStates.length})</Label>
            <Button variant="outline" size="sm" onClick={addState}>
              <Plus className="mr-1 h-4 w-4" />
              Add State
            </Button>
          </div>

          <Accordion type="multiple" className="space-y-2">
            {toggleStates.map((state, index) => (
              <AccordionItem
                key={index}
                value={`state-${index}`}
                className="rounded-lg border border-border bg-secondary/50"
              >
                <AccordionTrigger className="px-4 py-2 hover:no-underline">
                  <div className="flex items-center gap-2">
                    <GripVertical className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{state.name}</span>
                    <span className="text-xs text-muted-foreground">
                      (State {index + 1})
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4">
                  <div className="space-y-4">
                    <div className="flex items-end gap-2">
                      <div className="flex-1 space-y-2">
                        <Label>State Name</Label>
                        <Input
                          value={state.name}
                          onChange={(e) =>
                            updateState(index, { name: e.target.value })
                          }
                          placeholder="State name"
                        />
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeState(index)}
                        disabled={toggleStates.length <= 2}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="space-y-2">
                      <Label>Override Image</Label>
                      <Input
                        value={state.image || ""}
                        onChange={(e) =>
                          updateState(index, { image: e.target.value })
                        }
                        placeholder="Image URL or path"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>Override Text</Label>
                      <Input
                        value={state.text || ""}
                        onChange={(e) =>
                          updateState(index, { text: e.target.value })
                        }
                        placeholder="Button text"
                      />
                    </div>

                    <div className="border-t border-border pt-4">
                      <Label className="mb-2 block">Override Action</Label>
                      <ActionEditor
                        action={state.action}
                        onChange={(action) =>
                          updateState(index, { action: action || undefined })
                        }
                      />
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      )}
    </div>
  );
}
