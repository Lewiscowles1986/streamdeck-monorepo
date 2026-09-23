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

### Fast path: the guided tour (recommended)

`scripts/hardware-tour.py` turns the deck itself into a self-guided
evaluation surface — three built-in pages that exercise everything an
operator cares about, driven by the deck's own keys. No API, no web UI, no
config files; the terminal mirrors what happens:

```sh
cd streamdeck-monorepo                                # if you're not already there
STREAMDECK_TRANSPORT=libusb .venv/bin/python scripts/hardware-tour.py
```

You should see the deck light up with page 1 and the terminal print:

```text
Opened Stream Deck XL (CL42L2A02658, 32 keys) — brightness 50%
[PAGE] 1/3 — Welcome

Terminal controls: n/p page · 1-9 jump · b/B brightness · q quit
Everything else happens ON THE DECK (arrows, exit, pause, toggle).
```

What to try, and what each proves:

| Page | Press / observe | Expect on the physical deck |
| --- | --- | --- |
| Welcome | the **Press me** key | repaints to "Pressed!" on press and back on release (press pipeline) |
| Welcome | **Bright +/−** keys | deck brightness changes in 10% steps |
| Animation | watch key 0 | a 30 fps animated counter (synthetic frames — no asset needed) |
| Animation | the **Pause ⏸** key | frame counter HOLDS; **Play ▶** resumes from the same frame |
| Toggle & jump | the **OFF/ON** key | label and color flip each press (toggle machine) |
| Toggle & jump | the **Go p1** key | the whole deck repaints as page 1 (page switching) |
| any page | **◀ Prev / Next ▶** arrows | move between the three pages on-deck |
| any page | the **Exit ⏏** key | tour exits; deck is reset to blank |

Terminal fallback: `n`/`p` switch pages, `1`–`3` jump, `b`/`B` brightness,
`q` quits.

This exercises the same feature set as the config-driven runner (labels,
press states, animation + pause, toggles, switching) without building
anything first. To evaluate those features with real configs, data-URI GIFs
and the web editor, run the full stack instead (Step 4) and work through
the checklist below.

### Config-driven checklist

With the runner live, work through this checklist. Each row links to the
guide that builds that button:

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

> The tour script and the config runner exercise the same machinery from
> different sides: the tour is self-contained (synthetic pages, no API),
> while the runner consumes UI-built configs. If a feature works in the
> tour but misbehaves through a config, the difference is the config →
> runner pipeline — check the JSON View tab in the editor against the
> [config schema](../reference/config-schema.md).

## Troubleshooting

- **`TransportError: Could not open HID device.`** — macOS HID opens are
  *exclusive*. Another process (commonly the official Elgato app) or a stale
  handle holds the deck; enumeration still succeeds but the open fails.
  Quit the other app and re-run — a single retry is usually enough.
- **`No suitable LibUSB HIDAPI library found`** — Step 1 was skipped, or the
  library is outside the searched paths. `brew install hidapi` puts it in
  Homebrew's `lib/`, which the vendored loader searches.
- **Deck enumerates but keys stay dark** — no config is driving it. Assign
  one in the UI, or pass a file directly: `streamdeck run --config my.json`
  — or run the tour script (Step 5), which paints its own pages with no
  config at all.

## Verify

The full loop works when: `list-devices` prints your deck, the smoke suite
reports `5 passed`, the E2E image flashed on key 0 during the run, and a
GIF assigned in the UI animates on the physical key at 30 fps.