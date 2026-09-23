# Test a real Stream Deck

**Goal:** go from a plugged-in Stream Deck to a verified, live deck on your
desk — HID backend installed, device enumerated, the opt-in smoke suite
green, and a manual exploratory pass over the interesting features
(animated GIF, pause/play, toggle, page switching) on the physical keys.

Everything else in this documentation runs hardware-free: the `dummy`
transport emulates decks so tests and tutorials never touch USB. This guide
is the one place where real hardware is the point.

## Before you start — the working directory

Every command in this guide runs from the **repository root** — the
directory containing `.venv/` and `scripts/`. If your shell is somewhere
else (e.g. the parent folder), `cd` there first:

```sh
cd streamdeck-monorepo    # adjust the path to where your clone lives
```

Each **new terminal** needs this again — the command blocks below repeat
it so they can be pasted verbatim.

## Prerequisites

- A Stream Deck (Original, Mini, XL, Plus, Pedal…) plugged in.
- The Python environment: `uv venv --python 3.12 && uv pip install -e '.[dev]'`
  (see [run the test suites](run-tests.md) for the full dev setup).
- **macOS:** the HID backend library. The vendored core loads
  `libhidapi.dylib` directly through `ctypes` (no Python HID bindings are
  involved); without the library on disk, every command fails with
  `No suitable LibUSB HIDAPI library found on this system`.

## Step 1 — Install the HID backend

macOS (Homebrew):

```sh
brew install hidapi
```

The vendored transport searches Homebrew's `lib/` directory as a fallback,
so the brew install is picked up with no extra configuration.

Linux (or as a cross-platform convenience):

```sh
bash scripts/install-hidapi.sh
```

The script maps to the system package manager (`apt`, `dnf`, `pacman`,
`brew`).

## Step 2 — Enumerate the deck

```sh
cd streamdeck-monorepo                                # if you're not already there
.venv/bin/python -m streamdeck.cli list-devices
```

`libusb` is the default transport, so no environment variable is needed
here (the smoke suite sets it explicitly to be explicit).

Expected:

```text
Found 1 Stream Deck(s)
- Stream Deck XL (Serial: CL42L2A02658, 32 keys)
```

**Verify:** the command prints your model and serial number. If it prints
`Found 0`, see [troubleshooting](#troubleshooting).

## Step 3 — Run the smoke suite

```sh
cd streamdeck-monorepo                                # if you're not already there
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m pytest -m hardware tests/test_hardware.py -v
```

`bash scripts/hardware-smoke.sh` does this step plus the enumeration above
in one go. Expect **5 passed**:

| Test | Proves |
| --- | --- |
| `test_deck_enumerates` | the deck opens and reports serial + type |
| `test_deck_metadata` | key count and image format are sane |
| `test_render_and_display` | an "E2E" image is written to key 0 — **look at the deck**, you'll see it flash |
| `test_brightness_roundtrip` | brightness commands are accepted |
| `test_full_stack_with_hardware` | the API's `/devices` reports the real serial as connected |

The suite is deselected from normal runs (`-m 'not hardware'`) and skips
itself when no deck is attached — it never breaks CI.

## Step 4 — Drive the deck live

Three terminals ([tutorial 1](../tutorials/zero-to-deck.md) walks the same
path with emulated decks) — `cd streamdeck-monorepo` in each one first:

```sh
cd streamdeck-monorepo                                              # each terminal
.venv/bin/python -m streamdeck.cli serve                            # API on :8000
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m streamdeck.cli run  # device runner
.venv/bin/python -m streamdeck.cli ui --port 8081                   # web UI
```

Open <http://127.0.0.1:8081>, create a config in **Configurations**, then
assign it to your deck under **Devices**. The runner picks the assignment up
and paints all keys.

## Step 5 — The manual exploratory pass

Everything below is driven by the stock CLI and config files — no custom
code anywhere. Two terminals from Step 4 (drop the `ui` one if you're
assigning via the API instead of the browser):

```sh
cd streamdeck-monorepo                                              # each terminal
.venv/bin/python -m streamdeck.cli serve                            # API on :8000
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m streamdeck.cli run  # device runner
```

Then create three configs and wire them together — either in the web UI
(Step 4's editor) or straight through REST with curl. The tour is just
three configs wired with `switch-config`:

| Page | Config buttons (JSON) | What pressing them proves |
| --- | --- | --- |
| **Welcome** | a labeled key + a `pressed` block | press pipeline: "Pressed!" shows while held |
| **Welcome** | a `command` action (`mode: detached`) | detached commands fire without blocking the deck |
| **Welcome** | `isToggle` + `toggleStates` | idle/pressed images flip each press |
| **Animation** | a GIF data URI on one key | frames cycle at 30 fps |
| **Animation** | `"action": "pause"` / `"play"` | the GIF HOLDS its frame; resume continues it |
| **Animation** | `"action": "toggle-animation"` | one key flips hold/resume |
| **Pages** | `"action": "switch-config:<id>"` × 2 | the whole deck repaints as the other page |
| **any page** | `"action": "exit"` | the runner shuts down cleanly |

The exact JSON for each row is in the [config schema](../reference/config-schema.md)
and the per-feature guides below. Two configs with `switch-config` buttons
pointing at each other is the fastest way to see "pages" change on the
hardware. Assign page 1 to your deck under **Devices** (or
`PUT /device/{serial}/config/{id}`), and press through the table with the
runner live — the terminal prints one `[EVENT]` line per press.

### Per-feature guides

Each row of the table links to the guide that builds that button:

| Press / observe | Expect on the physical deck | Guide |
| --- | --- | --- |
| a text-labeled key | label drawn in the chosen font/color | [tutorial 1](../tutorials/zero-to-deck.md) |
| an animated GIF key | frames cycle at 30 fps, GIF badge in the editor | [animated GIF button](animated-gif-button.md) |
| a `pause` / `play` key | the GIF holds its current frame; resume continues from it | [pause and resume an animation](pause-animation.md) |
| a toggle button | idle/pressed images flip each press | [config schema](../reference/config-schema.md#toggle-states) |
| a `switch-config` key | the whole deck repaints as the other page | [switch configs from a button](switch-config-button.md) |
| an attached command key | button state reports the command result | [attached vs detached commands](attached-detached-commands.md) |

Two configs with `switch-config` buttons pointing at each other is the
fastest way to see "pages" change on the hardware.

## Troubleshooting

- **`TransportError: Could not open HID device.`** — macOS HID opens are
  *exclusive*. Another process (commonly the official Elgato app) or a stale
  handle holds the deck; enumeration still succeeds but the open fails.
  Quit the other app and re-run — a single retry is usually enough.
- **`No suitable LibUSB HIDAPI library found`** — Step 1 was skipped, or the
  library is outside the searched paths. `brew install hidapi` puts it in
  Homebrew's `lib/`, which the vendored loader searches.
- **Deck enumerates but keys stay dark** — no config is driving it. Assign
  one in the UI, or pass a file directly: `streamdeck run --config my.json`.
- **Deck looks alive but presses do nothing** — the runner already exited;
  hardware RETAINS the last painted frame, so a frozen panel proves nothing.
  Check the runner process is running (its terminal prints one `[EVENT]`
  line per press), then re-run `streamdeck run`.

## Verify

The full loop works when: `list-devices` prints your deck, the smoke suite
reports `5 passed`, the E2E image flashed on key 0 during the run, and a
GIF assigned in the UI animates on the physical key at 30 fps.