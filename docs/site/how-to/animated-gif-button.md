# Upload an animated GIF button

**Goal:** put an animated GIF on a Stream Deck key — from the browser upload
through to frames cycling on the deck at 30 fps.

## How it works (one paragraph)

The UI reads the file with `FileReader.readAsDataURL` and stores it as a
`data:image/gif;base64,…` **data URI** inside the config. The device runner
decodes every frame of that GIF **once**, caches the frames in an
`itertools.cycle` keyed by the full source string, and the 30 fps animate
loop pulls frames for every button showing that source. Same GIF on three
buttons = one decode, one cycle, all three keys in lockstep. (Design detail
in [the animation pipeline explanation](../explanation/animation-pipeline.md).)

## Steps

1. Open a config in the editor (**Configurations** → click the config).
2. Click the target button in the grid. The right panel opens on the
   **Idle** tab.
3. In the **Idle Image** drop zone, click and choose a `.gif`
   (the input accepts `image/png,image/gif`). Alternatively switch to the
   **URL** tab and paste an `https://…` image URL.
4. The preview shows the GIF with a **GIF** badge in its corner.
5. (Optional) Add **Text** — the label is drawn over the animation.
6. **Save** and wait for *Configuration saved successfully.*

![GIF uploaded: preview on the grid button, GIF badge in the panel, unsaved-changes indicator](../../screenshots/upload-gif-badge.png)

## Verify

**In the UI:** reload the page, reopen the button — the preview and GIF badge
persist. The **JSON View** tab proves the wire format the runner consumes:

```ts
// From e2e/parity-demo.spec.ts
// ("uploaded GIF survives a save + reload round-trip").
await page.getByRole("tab", { name: /json view/i }).click();
await expect(page.locator("pre")).toContainText("data:image/gif;base64,");
```

**Through the API:**

```sh
CONFIG_ID=<id from the editor URL>
curl -s http://127.0.0.1:8000/config/$CONFIG_ID | grep -o 'data:image/gif;base64,' | head -1
# data:image/gif;base64,
```

**On the deck:** with the runner running
([tutorial 1](../tutorials/zero-to-deck.md#step-6-run-the-device-runner)),
the key plays the animation at 30 fps. Two buttons showing the same GIF
advance in lockstep — pinned by
`tests/test_parity.py::test_animated_data_uri_is_shared_between_buttons` and
this spec:

```ts
// From e2e/parity-demo.spec.ts
// ("the same GIF can be assigned to two buttons (shared source)"):
// byte-identical data URIs must appear on both buttons.
const uris = text.match(/data:image\/gif;base64,[A-Za-z0-9+/=]+/g) ?? [];
expect(uris.length).toBeGreaterThanOrEqual(2);
expect(new Set(uris).size).toBe(1);
```

## Sources the runner accepts

The `image` value (idle, pressed, or toggle-state override) may be:

| Source | Example |
| --- | --- |
| Data URI (what the uploader produces) | `data:image/gif;base64,R0lGOD…` |
| HTTP(S) URL (fetched at render time) | `https://example.com/icon.png` |
| Local file path (`file://` stripped) | `/Users/me/pics/eye.gif` |

A corrupt or undecodable source renders the **blank key** instead of
crashing the runner ([crash-safety](../explanation/crash-safety.md#3-corrupt-images-fall-back-to-blank)).

## Troubleshooting

- **GIF badge missing** — the value isn't a `data:image/gif` URI (maybe a
  `.png` URL). Only animated data URIs get the badge; URLs render but the
  badge keys off `data:image/gif`.
- **Key shows blank on the deck** — the runner logged
  `[RENDER] image render failed …` and fell back; check the source decodes
  (PIL can open it) and, for URLs, that the runner host can reach it.
- **Pressed state overrides** — GIFs live per-state; a **Pressed** tab image
  only shows while held (the parity-demo spec
  "pressed-state image and text are independent from idle" pins this).

## Related

- [Pause and resume an animation](pause-animation.md) — hold a frame.
- [Config schema: `animation` block](../reference/config-schema.md#animation)
- [Explanation: the animation pipeline](../explanation/animation-pipeline.md)