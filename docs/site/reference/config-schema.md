# Config schema reference

What a **config** can contain. This is the JSON the UI writes, the API
stores verbatim, and the device runner reads. TypeScript types live in
[`frontend/src/types/streamdeck.ts`](../../../frontend/src/types/streamdeck.ts);
the backend column is schema-less JSON (see [API reference](api.md#dialect-rules)).

Top level (`StreamDeckConfig`):

```json
{
  "id": "server-generated uuid (read-only)",
  "name": "My layout",
  "deviceType": "stream-deck-xl",
  "buttons": [ ButtonConfig, … ],
  "triggers": { "app": ["Slack"], "network": {"ssid": "…"} }
}
```

| Key | Type | Notes |
| --- | --- | --- |
| `name` | string | Displayed everywhere; **duplicate names are legal** (the trigger apply-once guard keys on name — see the [triggers reference](triggers.md)) |
| `deviceType` | kebab id | `stream-deck` · `stream-deck-mini` · `stream-deck-xl` · `stream-deck-mk2` · `stream-deck-plus` · `stream-deck-neo` · `stream-deck-pedal` · `stream-deck-studio`. Human names ("Stream Deck XL") are tolerated everywhere too — both dialects render a grid ([P9](parity.md#the-table-summarized)) |
| `buttons` | ButtonConfig[] | Per-key entries; missing keys render blank |
| `triggers` | object \| null | Optional; see [triggers reference](triggers.md) |

Grid dimensions per type (rows × cols): original/MK.2 5×3, XL 8×4, Mini 3×2,
Plus/Neo 4×2, Pedal 3×1, Studio 16×2; unknown types fall back to 5×3.

## ButtonConfig

```json
{
  "index": 0,
  "idle":   { "image": "…", "text": "LIVE", "font": { … } },
  "pressed":{ "image": "…", "text": "ON AIR" },
  "action": { "type": "command", "executable": "/bin/echo" },
  "isToggle": false,
  "toggleStates": [ ToggleState, … ],
  "animation": { "paused": false, "frameIndex": 0 }
}
```

| Key | Type | Notes |
| --- | --- | --- |
| `index` | int | 0-based key position |
| `idle` / `pressed` | ButtonAppearance | Independent states (editing one never leaks into the other — pinned by E2E) |
| `action` | Action \| null | See [Actions](#actions) |
| `isToggle` + `toggleStates` | see [Toggle states](#toggle-states) | |
| `animation` | `{paused?: bool, frameIndex?: int}` | Button-level; applies to whichever state renders. See [animation](#animation) |

### ButtonAppearance

| Key | Type | Notes |
| --- | --- | --- |
| `image` | string | Data URI (what the uploader produces), `http(s)://` URL, or local path |
| `text` | string | Label drawn over the image |
| `font` | FontConfig | See below |

### font

```json
{ "family": "serif", "size": 20, "color": "#00ff00", "weight": "normal", "position": "top" }
```

| Key | Values | Default (pre-P2 configs render identically) |
| --- | --- | --- |
| `family` | `sans-serif` · `serif` · `monospace` · `Arial` · `Helvetica` · `Roboto` (UI select) — any string accepted; resolved at render | `Roboto` (bundled) |
| `size` | 8–48 in the editor | 14 |
| `color` | CSS color string | `white` |
| `weight` | `normal` \| `bold` | `normal` |
| `position` | `top` \| `center` \| `bottom` | `bottom` |

Font **resolution is platform-aware**: `monospace` maps to Menlo/Monaco on
macOS then DejaVu on Linux; `serif` to Times New Roman/Times/DejaVu Serif;
named faces are looked up in the package assets and `/Library/Fonts`
(macOS) before falling back to the bundled Roboto.

### Toggle states

```json
{
  "isToggle": true,
  "toggleStates": [
    { "name": "State 1", "image": "…", "text": "OFF", "action": { … } },
    { "name": "State 2", "text": "ON" }
  ]
}
```

- Each state merges **over the idle appearance** (state fields override).
- Per press, the runner cycles `(current + 1) % len(toggleStates)`.
- A state may override the action (e.g. state 2 fires a different command);
  otherwise the button's `action` fires.
- The UI enforces a **minimum of two states** (remove disabled at ≤ 2) and
  badges toggle buttons on the grid.

## Actions

The `action` value is a JSON dict (or one of the bare strings below). The
runner's key callback dispatches it; `command`/`sequence` go to the
nominated agent ([architecture](../explanation/architecture.md)).

### CommandAction

```json
{
  "type": "command",
  "executable": "/usr/bin/env",
  "arguments": "echo {{button_index}}",
  "cwd": "/tmp",
  "env": { "SD_BUTTON": "{{button_index}}" },
  "timeout": 30,
  "mode": "attached"
}
```

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `executable` | string | — (required) | Full path suggested by the UI's completion |
| `arguments` | string \| list | — | Shell-style string, split agent-side |
| `cwd` | string | inherit | Ignored if not an existing directory |
| `env` | object | `{}` | Merged over the agent's environment; non-dict collapses to `{}` |
| `timeout` | number | **30** | Attached only; corrupt/non-numeric falls back to 30 |
| `mode` | `"attached"` \| `"detached"` | `attached` | Detached = fire-and-forget (`start_new_session`), no timeout/capture. Implicit when attached (the UI omits the key) — [mode how-to](../how-to/attached-detached-commands.md) |

Template variables expand in `executable`, `arguments`, `cwd`, `env`, and
into sequence steps — see [template variables](../explanation/template-variables.md).

### ExitAction

```json
{ "type": "exit" }
```

Shuts the runner down (sets the closed event, resets + closes the deck).
The UI's "Exit (shut down the runner)" type. The runner also accepts the
bare string `"exit"` — the canonical parity contract ([P3](parity.md)).

### SwitchConfigAction

```json
{ "type": "switch-config", "configId": "<uuid>" }
```

(Also the bare-string form `"switch-config:<uuid>"`.) Swaps the runner's
active config at press time — [how-to](../how-to/switch-config-button.md).

### SequenceAction

```json
{
  "type": "sequence",
  "steps": [ CommandAction, … ],
  "stopOnError": false
}
```

Steps are full actions (dict-only; no bare-string form), each optionally
carrying `delayMs` (sleep before that step, sanitized: ≤ 0 → 0, cap
**60000**). Nesting capped at depth **4**. Aggregation: all-success
(`done`/`detached` steps) → `"done"`, all-failed → `"failed"`, mixed →
`"partial"`; `stopOnError` aborts remaining steps (reported `"skipped"`) on
the first failure — see the [sequence how-to](../how-to/multi-step-sequences.md).

### Bare-string runner actions

Handed to the runner's key callback directly (dict forms exist for all but
`exit`'s sibling controls — see [pause/resume](../how-to/pause-animation.md)):

| Bare string | Meaning |
| --- | --- |
| `"exit"` | Shut the runner down |
| `"pause"` / `"play"` / `"toggle-animation"` | Hold/resume/flip the animation for the key's image source |
| `"switch-config:<id>"` | Swap the active config |

### What's NOT accepted

`dispatch_action` only forwards dict actions of type `command` or
`sequence` to the agent queue. Unknown types, non-dict actions (other than
the bare strings above), and garbage shapes are ignored or answered with
structured errors — never a crash ([crash-safety](../explanation/crash-safety.md)).

## Animation

Button-level block (applies to whichever state is rendered):

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `paused` | bool | `false` | Start with the source held on its current frame |
| `frameIndex` | int | 0 | Advance the shared cycle N times **before** first paint (best-effort; corrupt values are ignored) |

Pause semantics (source-keyed, shared across buttons): the
[animation pipeline explanation](../explanation/animation-pipeline.md) and
the [pause how-to](../how-to/pause-animation.md).

## Legacy note: the old `font` key shape

Very old configs carried font fields directly on the state; current configs
always nest under `font`. The runner reads `state.font` only — the UI
always writes the nested shape.