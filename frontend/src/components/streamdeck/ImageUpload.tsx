import { useState, useRef } from "react";
import { Upload, Link, Image as ImageIcon, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ImageUploadProps {
  value?: string;
  onChange: (value: string | undefined) => void;
  label?: string;
}

export function ImageUpload({ value, onChange, label = "Image" }: ImageUploadProps) {
  const [urlInput, setUrlInput] = useState(value || "");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result as string;
        onChange(result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUrlSubmit = () => {
    if (urlInput.trim()) {
      onChange(urlInput.trim());
    }
  };

  const clearImage = () => {
    onChange(undefined);
    setUrlInput("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const isGif = value?.toLowerCase().includes(".gif") || value?.startsWith("data:image/gif");

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>{label}</Label>
        {value && (
          <Button variant="ghost" size="sm" onClick={clearImage} className="h-6 px-2 text-xs">
            <X className="mr-1 h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      {value ? (
        <div className="relative">
          <div className="relative aspect-square w-full max-w-[200px] overflow-hidden rounded-lg border border-border bg-secondary">
            <img
              src={value}
              alt="Button preview"
              className="h-full w-full object-cover"
            />
            {isGif && (
              <span className="absolute bottom-1 right-1 rounded bg-primary/80 px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
                GIF
              </span>
            )}
          </div>
        </div>
      ) : (
        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="upload" className="text-xs">
              <Upload className="mr-1 h-3 w-3" />
              Upload
            </TabsTrigger>
            <TabsTrigger value="url" className="text-xs">
              <Link className="mr-1 h-3 w-3" />
              URL
            </TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="mt-3">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-border bg-secondary/50 p-6 transition-colors hover:border-primary hover:bg-secondary"
            >
              <ImageIcon className="mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Click to upload</p>
              <p className="text-xs text-muted-foreground">PNG, GIF (512×512)</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/gif"
              onChange={handleFileChange}
              className="hidden"
            />
          </TabsContent>

          <TabsContent value="url" className="mt-3">
            <div className="flex gap-2">
              <Input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://example.com/icon.png"
                className="flex-1"
              />
              <Button onClick={handleUrlSubmit} disabled={!urlInput.trim()}>
                Set
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
