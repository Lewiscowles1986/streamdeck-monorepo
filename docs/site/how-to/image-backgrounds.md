# Compose multi-button image backgrounds

Paint **one image across several keys** — a header banner over the top row,
a full-deck hero image, or a picture that continues seamlessly under a row
of labeled buttons. The feature is the config's `backgrounds` block
([P19](../../parity.md)); the schema is in the
[config reference](../reference/config-schema.md#backgrounds-p19).

Everything here works hardware-free: the
[dummy transport](../explanation/testing-philosophy.md) emulates decks for
the web UI, and the runner renders spans on real decks identically.

## Before you start — the working directory

Every command runs from the **repository root** (the directory containing
`.venv/` and `scripts/`). Each **new terminal** needs it again:

```sh
cd streamdeck-monorepo    # adjust the path to where your clone lives
```

## Prerequisites

- A config to decorate — create one in the web UI under **Configurations**
  (the [tutorial](../tutorials/zero-to-deck.md) walks this), or straight
  through REST:

```sh
cd streamdeck-monorepo                                        # repo root
curl -s -X POST http://localhost:8000/config \
  -H 'Content-Type: application/json' \
  -d '{"name": "Spanned", "deviceType": "stream-deck-xl", "buttons": []}'
```

- The three terminals from
  [drive the deck live](real-hardware.md#step-4-drive-the-deck-live)
  (API + runner + UI) if you want to watch a real (or emulated) deck paint
  the span.

## Step 1 — Open the Backgrounds page

In the web UI, pick either entry point:

- the sidebar's **Backgrounds** item, or
- a config editor's header **Backgrounds** button (lands pre-selected).

```sh
cd streamdeck-monorepo                                        # each terminal
.venv/bin/python -m streamdeck.cli serve                      # API on :8000
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m streamdeck.cli run  # runner
.venv/bin/python -m streamdeck.cli ui --port 8081             # web UI
```

**Verify:** the page shows the heading and a **Configuration** picker.

## Step 2 — Add a span

1. Pick your config in the picker.
2. **Add background** — a new span card appears (default 2×2 cells at the
   top-left).
3. **Upload** the image (or paste a URL). Animated GIFs are welcome — the
   span animates at 30 fps.
4. Set **Column (x)**, **Row (y)**, **Width**, **Height** — all in key cells,
   with `x`/`y` the top-left cell.

The preview grid on the right mirrors the runner exactly: every covered cell
shows its own crop of the image, so what you see is what the deck paints.

**Verify:** covered cells in the preview show the image; cells outside the
region stay dark.

## Step 3 — Mix in buttons

Backgrounds and buttons compose by a simple rule: **a button's own image
always wins**; the background shows only on covered keys that have no image
of their own.

So the typical layout is:

- upload the span once in **Backgrounds**, and
- give individual keys text labels (a text-only key draws its label **over**
  the tile) or their own images where a key should stand out.

A text-only covered key in JSON:

```json
{
  "index": 0,
  "idle": { "text": "LIVE", "font": { "position": "top" } }
}
```

**Verify:** press keys in the editor grid — cells with an image keep it;
empty covered cells show the span; labels draw on top of the span.

## Step 4 — Save and watch the deck repaint

```sh
cd streamdeck-monorepo                                        # if needed
```

- Click **Save** on the Backgrounds page, then **assign the config to your
  deck** under **Devices** (or
  `PUT /device/{serial}/config/{id}` — see the
  [API reference](../reference/api.md)).
- The runner repaints on assignment; covered keys show the span immediately.

The runner-side behavior, for the record: the image is scaled to cover the
region (aspect preserved, center-cropped), composited at native key
resolution, and sliced per key — the tiles come from **one composite**, which
is why the span is seamless across key borders. On decks whose keys are
flipped/rotated (Original, XL, Mini, Neo) each tile is pre-inverted, so the
picture stays continuous there too.

## Step 5 — Pause an animated span

If the span is an animated GIF, any covered key can control it — add a
button action like the [pause guide](pause-animation.md) describes
(`pause` / `play` / `toggle-animation`) on a key inside the span:

- **pause** holds the WHOLE span on its current frame (one tile freezing
  while its siblings cycle would tear the picture).
- **play** resumes; **toggle-animation** flips.
- The pause is shared per background, matching the
  [per-source pause rule](../explanation/animation-pipeline.md) for buttons.

## Step 6 — Layer and combine spans

- Add a second span over the first: **later entries composite over earlier
  ones** (z-order = list order). A 1×1 "badge" over a full-deck hero is the
  canonical use.
- Remove a span with its card's **Remove** button, then Save.
- Replace everything by saving a config whose JSON has no `backgrounds` key —
  the whole-row PUT clears the block (the same replace semantics as
  [triggers](automatic-switching-triggers.md)).

## Troubleshooting

- **The span doesn't appear on the deck** — check the config was *assigned*
  to the device (the Backgrounds page only saves the config) and that the
  runner is running.
- **A key inside the span stays blank instead of showing the picture** —
  the runner skips malformed spans; open the config's JSON View and check the
  entry has an `image` and numeric `x`/`y`/`width`/`height` ≥ 1.
- **A key shows its own image instead of the span** — that's the rule, not a
  bug: a button's own idle/pressed image always wins. Clear the button's
  image to let the span through.
- **The span is torn/rotated on a real deck** — you're on a build older than
  P19; the per-key flip/rotation inversion landed with it.
- **Config swap left a stale span** — spans are purged on every config swap
  (press or trigger); if you see leftovers, the runner predates P19.

## Verify

The full loop works when: the preview shows per-cell crops, **Save**
succeeds, the assigned config's covered keys paint the span on the deck, a
key with its own image still shows that image, and (for a GIF span)
`pause` on a covered key freezes the whole span and `play` resumes it.