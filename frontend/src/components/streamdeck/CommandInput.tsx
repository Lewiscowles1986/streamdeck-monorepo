/**
 * CommandInput — a text input with completion (round 6, P17).
 *
 * A controlled dropdown rather than a native <datalist>: datalist UX is
 * browser-dependent (Chrome shows it only after two chars and its popup is
 * not stylable/testable deterministically), while this dropdown is fully
 * controlled — every suggestion is visible, keyboard-navigable and
 * click-selectable in E2E with no browser variance.
 *
 * Suggestions come from three sources, all filtered case-insensitively by
 * the current prefix (max 8, most-relevant-first):
 *  - COMMON_BINARIES: a static list of common macOS executables (a browser
 *    cannot read PATH, so "completion against PATH" means this static map).
 *  - recent history: localStorage streamdeck_recent_executables (cap 10,
 *    dedupe, most-recent-first) — executables the user has typed before.
 *  - template variables: when the value ends with "{{" (or the user clicks
 *    the {{ }} chip), the 7 TEMPLATE_VARIABLES complete inline; selection
 *    inserts the completion at the cursor.
 *
 * Flags helper: with an executable context that is a known binary, a
 * leading "-" in the value suggests that binary's flags from a tiny static
 * map.
 */

import * as React from "react";
import { Input } from "@/components/ui/input";
import { TEMPLATE_VARIABLES } from "@/types/streamdeck";

/** Static common-binary list (browser cannot scan PATH). */
export const COMMON_BINARIES = [
  "/usr/bin/env",
  "/bin/sh",
  "/usr/bin/open",
  "/usr/bin/osascript",
  "/usr/local/bin/brew",
  "/opt/homebrew/bin/brew",
  "/usr/sbin/systemsetup",
  "/usr/bin/defaults",
  "/usr/bin/curl",
  "/usr/bin/caffeinate",
];

/** Tiny static flag map for known binaries (arguments-input helper). */
export const COMMON_FLAGS: Record<string, string[]> = {
  "/usr/bin/osascript": ["-e"],
  "/usr/bin/open": ["-a", "-g"],
  "/usr/local/bin/brew": ["install", "services"],
  "/opt/homebrew/bin/brew": ["install", "services"],
  "/usr/bin/defaults": ["read", "write"],
  "/usr/bin/curl": ["-s", "-o"],
};

const HISTORY_KEY = "streamdeck_recent_executables";
const HISTORY_CAP = 10;
const SUGGESTION_CAP = 8;

/** Read the typed-executable history (most-recent-first, deduped). */
export function readExecutableHistory(): string[] {
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((v) => typeof v === "string") : [];
  } catch {
    return [];
  }
}

/**
 * Record a typed executable. Only absolute paths are stored (the history is
 * about full paths — bare names like `echo` are not reusable suggestions).
 */
export function recordExecutable(value: string): void {
  const trimmed = value.trim();
  if (!trimmed.startsWith("/") || !trimmed) return;
  try {
    const next = [trimmed, ...readExecutableHistory().filter((v) => v !== trimmed)];
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next.slice(0, HISTORY_CAP)));
  } catch {
    // Storage full/blocked: history is an enhancement, never a failure.
  }
}

export interface CommandInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  /** Known-binary context for the flags helper (the Executable field's value). */
  executableContext?: string;
  onBlur?: () => void;
  ariaLabel?: string;
}

export function CommandInput({
  value,
  onChange,
  placeholder,
  executableContext,
  onBlur,
  ariaLabel,
}: CommandInputProps) {
  const [open, setOpen] = React.useState(false);
  const [highlighted, setHighlighted] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const endsWithOpenBraces = value.endsWith("{{");
  const knownFlags = executableContext ? COMMON_FLAGS[executableContext.trim()] : undefined;
  const flagMode = Boolean(knownFlags && value.trimStart().startsWith("-") && !endsWithOpenBraces);

  const suggestions = React.useMemo(() => {
    const out: string[] = [];
    const push = (s: string) => {
      if (out.length >= SUGGESTION_CAP) return;
      if (!out.includes(s)) out.push(s);
    };

    // Template variables: value ends with "{{".
    if (endsWithOpenBraces) {
      for (const v of TEMPLATE_VARIABLES) push(v.name);
      return out;
    }

    // Flags helper: known binary + leading "-".
    if (flagMode && knownFlags) {
      for (const f of knownFlags) push(f.startsWith("-") ? f : `-${f}`);
      return out;
    }

    // Executable completion: static list + history, by current prefix.
    const prefix = value.trim().toLowerCase();
    if (prefix) {
      for (const bin of COMMON_BINARIES) {
        if (bin.toLowerCase().startsWith(prefix)) push(bin);
      }
      for (const hist of readExecutableHistory()) {
        if (hist.toLowerCase().startsWith(prefix)) push(hist);
      }
    }
    return out;
  }, [value, endsWithOpenBraces, flagMode, knownFlags]);

  // Keep the highlight inside bounds when the list changes.
  React.useEffect(() => {
    setHighlighted((h) => Math.min(h, Math.max(0, suggestions.length - 1)));
  }, [suggestions.length]);

  const showList = open && suggestions.length > 0;

  const insertAtCursor = (completion: string) => {
    const el = inputRef.current;
    if (!el) {
      onChange(value + completion);
      return;
    }
    const start = el.selectionStart ?? value.length;
    let before = value.slice(0, start);
    const after = value.slice(start);
    // Typing a completion at the cursor: drop an odd trailing "{" if the
    // completion itself supplies it, so `echo {` + `{{button_index}}` does
    // not become `echo {{{button_index}}`.
    let insert = completion;
    if (before.endsWith("{") && completion.startsWith("{{")) {
      before = before.slice(0, -1);
      insert = completion;
    }
    onChange(before + insert + after);
    // Restore the cursor after the inserted completion.
    requestAnimationFrame(() => {
      const pos = before.length + insert.length;
      el.setSelectionRange(pos, pos);
    });
  };

  const accept = (index: number) => {
    const s = suggestions[index];
    if (s === undefined) return;
    if (endsWithOpenBraces) {
      // Template variable: replace the trailing "{{" with the full variable.
      const head = value.slice(0, value.length - 2);
      onChange(head + s);
    } else if (flagMode) {
      // Flag: append after the leading dash.
      onChange(value.trimEnd() + s.slice(1));
    } else {
      // Executable: replace the whole prefix with the suggestion.
      onChange(s);
    }
    setOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (open && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlighted((h) => (h + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlighted((h) => (h - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        accept(highlighted);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
    }
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        value={value}
        aria-label={ariaLabel}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }
        }
        onFocus={() => {
          setHighlighted(0);
          setOpen(true);
        }}
        onBlur={() => {
          // Close immediately: suggestion selection uses onMouseDown +
          // preventDefault, which never blurs the input, so nothing needs
          // a deferred window. An immediate close also prevents two lists
          // being open at once when focus moves between fields.
          setOpen(false);
          recordExecutable(value);
          onBlur?.();
        }}
        onKeyDown={handleKeyDown}
      />
      {showList && (
        <div
          data-testid="command-suggestion-list"
          className="absolute z-50 mt-1 w-full overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md"
        >
          {suggestions.map((s, i) => (
            <button
              key={s}
              type="button"
              data-testid="command-suggestion"
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-secondary ${
                i === highlighted ? "bg-secondary" : ""
              }`}
              // onMouseDown (not onClick) so the selection lands before the
              // input's blur hides the list.
              onMouseDown={(e) => {
                e.preventDefault();
                accept(i);
              }}
            >
              <code className="text-xs text-primary">{s}</code>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}