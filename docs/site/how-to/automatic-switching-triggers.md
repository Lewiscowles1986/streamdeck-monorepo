# Set up automatic switching with triggers

**Goal:** a config that applies itself when the environment matches — an app
comes to the front, or you join a Wi-Fi network. This is the task-oriented
version of [the triggers tutorial](../tutorials/triggers.md); here it's a
compact recipe plus the exact rules the evaluator applies.

## Steps (UI)

1. Open a config in the editor.
2. Below the button grid, expand **Automatic Switching** (⚡).
3. Fill any of:
   - **Frontmost apps** — comma-separated app names, e.g. `Slack, Spotify`
     (stored as `triggers.app`, matched case-insensitively against the
     frontmost application name).
   - **WiFi SSID** — e.g. `HomeWifi` (stored as `network.ssid`, exact match
     after trimming).
   - **Interface** — optional, e.g. `en0` (stored as `network.interface`).
4. **Save**. Empty fields are dropped, and an all-empty block stores no
   `triggers` key at all (a payload without the block **clears** it — whole-
   row PUT replace semantics).

```ts
// From e2e/parity-demo.spec.ts
// ("triggers editor writes app + ssid into the config JSON"):
await page.getByTestId("triggers-toggle").click();
await page.getByTestId("triggers-apps").fill("Slack");
await page.getByTestId("triggers-ssid").fill("HomeWifi");
// save + reload → the block survives (demo update replaces the whole row,
// exactly like the real PUT)
```

## Steps (config JSON directly)

```json
{
  "name": "Comms",
  "deviceType": "stream-deck-xl",
  "buttons": [ … ],
  "triggers": {
    "app": ["Slack"],
    "network": { "ssid": "HomeWifi", "interface": "en0" }
  }
}
```

## What the runner does with it

- The **TriggerWatcher** polls every **5 seconds** and always reads the
  *current* config — so a config assigned later (or reached by a
  [switch-config press](switch-config-button.md)) arms immediately; no
  restart needed.
- Each poll runs two **macOS-only** probes:
  - frontmost app via `osascript` System Events (`PROBE_TIMEOUT` 2 s),
  - SSID via `ipconfig getsummary` (the modern path — the deprecated
    `airport -I` is deliberately not used).
- Branches combine as **OR**; app names match case-insensitively; SSID is an
  exact trimmed match; a `None` probe (failure, not-macOS, hidden network)
  never matches.
- A match **applies once** (swap + clear button/pause state + re-render).
  While the trigger still holds, subsequent polls do not re-apply.

Full semantics and the failure matrix: [triggers block reference](../reference/triggers.md).

## Verify

1. **Wire form** — save and check the API:
   ```sh
   curl -s http://127.0.0.1:8000/config/$CONFIG_ID | python3 -m json.tool | grep -A3 triggers
   ```
2. **Behavior** — assign the config, run the runner, then satisfy the trigger
   (focus the app / join the SSID). Within ~5 s the runner applies the
   config (log: the watcher's apply path). Clear the trigger condition and
   the config **stays** — triggers apply while they match, they don't revert.
3. **Evaluator unit semantics** (no hardware needed) — the pure function:
   ```python
   from streamdeck.triggers import evaluate_triggers
   evaluate_triggers({"app": ["Slack"]}, {"frontmost_app": "SLACK", "wifi_ssid": None})
   # True — app match is case-insensitive
   ```
4. **Regression suite** — `tests/test_triggers.py` (35 tests) covers the
   evaluator matrix, probe failures, apply-once, and the
   switch-into-triggered-config arming case.

## Clearing triggers

Delete the field contents in the UI and save — the block is removed from the
JSON. (The demo mock and the real API both replace the whole row on save, so
an omitted `triggers` key clears the block; pinned by the "clearing trigger
fields removes the triggers block" spec and the parity-fullstack PUT test.)

## Related

- [Triggers block reference](../reference/triggers.md) — every field, every rule
- [Switch configs from a button](switch-config-button.md)
- [Explanation: architecture — the runner's two loops](../explanation/architecture.md#the-runners-two-loops)