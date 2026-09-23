# Loop Roadmap — long-horizon memory

> Updated each round. Committed on every green cycle so it survives sessions.
> Loop pattern per round: builder → critic → judge (subagents), commit on green.

## Done

- **R1 (certified, `bcb949f`)** — animated GIF parity: upload→data URI→badge E2E (demo+fullstack), runner multi-frame decode + shared cycle pytest tests. P10 rule added.
- **R2 (certified, `cd7d0ae`)** — config-editor parity: template-var insertion UI (P1), timeout/env editor + wire hop (P8), font config round-trip (P2), pressed-state independence. 45 pytest / 25 E2E green.

## Round 3 (current)

- **A. Toggle E2E** — toggle editor switch, add/remove state, per-state overrides (image/text/action), save+reload, ButtonCell badge. Plus **device assign→render loop** test: assign config to dummy deck via API → runner renders its buttons (candidate #1).
- **B. Animation pause (worktree `worktrees/anim-pause`) — implementation complete, pending critic+judge.** Per-source pause on a frame: `"pause"` / `"play"` / `"toggle-animation"` bare-string actions (alongside `"exit"`), optional `frameIndex` advance-and-hold, `paused_images: dict[str, bool]` keyed by source string (shared-pause semantics per P10); config surface `animation: {paused, frameIndex}` in ButtonConfig. **UI surface (ActionEditor controls + E2E) explicitly deferred to the merge round.** Parity rule P13 recorded in docs/parity.md; pytest: pause holds frame, resume continues from held position, toggle-animation action contract, start-paused config — mutation-verified.
- Decision recorded: **shared pause** (source-keyed) — consistent with P10 shared-cycle; per-button pause deferred as a follow-up if needed.

## Round 4 — command hardening + new action types (implementation complete, pending critic+judge)

- **launch/attached/detached — DONE.** CommandAction gains `mode: "attached" | "detached"` (default attached = pre-existing run+wait+capture behavior). Detached = `Popen(start_new_session=True)` without waiting; reports `{"status": "detached", "pid": N}`, no timeout kill, no output capture. Executor hardened: `execute()` never raises (garbage actions → structured failed results; timeout coerced via `int()` fallback 30; env coerced to `{}` if not a dict; bad cwd ignored). Tests: `tests/test_agent.py` (13). Parity rule **P14**.
- **switch-config action — DONE.** Bare-string `"switch-config:<config_id>"` + dict `{"type":"switch-config","configId":...}` in `key_change_callback`; runner helper `fetch_config_by_id` + `switch_config` (swap module `config`, clear button/pause state, re-render all keys; unknown config / API down → keep current). UI: ActionEditor "Switch Config" type with config picker + manual id input. Parity rule **P15**; E2E in parity-demo + parity-fullstack.
- **change-screen action**: `{"type":"screen","page":N}` or `"screen:<n>"` — concept: multiple "pages" of buttons on one deck; paging flips the button grid. Needs a page model in config (pages[] or offset). Scope carefully in builder round; may defer to R5 if it balloons.
- Hardening sweep — DONE for the executor + runner callback paths: catch-all around the key callback body (`key_change_callback` → `_handle_key_change`, a raising callback can break the StreamDeck library's callback delivery), corrupt-config defense in `get_button_config` (`buttons: None` / `config: None` → blank key). TransportError isolation in the animate loop pre-existed. Critic pass extended the sweep (round 4 judge): corrupt image source → blank key + no raise, per-key write failures skipped in `update_key_image`/`animate_tick` (TransportError still propagates as deck-gone), corrupt `frameIndex` ignored, `main()` device-type check reads `config.get("device_type")`. Regression tests: `tests/test_hardening.py` (8, mutation-verified).
- **Deferred to R5 — detached-mode zombie reaping: DONE in Round 5** (daemon waitpid thread per detached child; see Round 5 section).

## Round 5 — auto config switching (triggers) — DONE (critic+judge certified)

- **Config triggers — DONE.** Config gains optional schema-less `triggers`: `{"app": ["Slack"], "network": {"ssid": "...", "interface": "en0"}}` (JSON column like `buttons`, no strict validation — the API round-trip preserves any shape). UI: ConfigEditor "Automatic Switching" collapsible (frontmost apps as a comma-separated list, wifi SSID, optional interface) writing `config.triggers` through the normal save path. Parity rule **P16**.
- **Runner trigger engine — DONE.** New module `streamdeck/triggers.py`: pure `evaluate_triggers` (app names case-insensitive OR ssid equality, malformed input → False), crash-safe macOS probes (`get_frontmost_app` via `osascript` System Events, 2s timeout; `get_wifi_ssid` via `ipconfig getsummary` parse — modern path; `airport -I` deliberately NOT used, removed on Sequoia), and `TriggerWatcher` (injectable get_config_fn/apply_fn/poll_seconds/should_continue_fn/probes; daemon thread; probe failures and apply failures never kill the loop; run() itself is wrapped so even an exploding should_continue_fn only logs — a dead watcher never takes the runner down). `run_deck` starts the watcher UNCONDITIONALLY (judge fix: get_config_fn re-reads the CURRENT config every poll, so a config reached later by switch-config or API assign arms immediately — a conditional start leaves those configs unwatched until a runner restart; a triggerless tick is a cheap no-op).
- **Priority rule (documented, minimal):** explicit press > triggers holds by construction — triggers evaluate only from the CURRENT config (no cross-config trigger jumping); a switch-config press or API assign naturally re-aims the watcher at the new config. A matched config applies once (apply-once guard); re-arming happens when the current config changes or the trigger stops matching.
- **Swap-core refactor:** `runner.apply_config(deck, config)` is the single swap path (assign + clear button/pause state + full re-render); `switch_config` now delegates to it, and the watcher's apply_fn is the same helper.
- **Zombie reaping (deferred from R4) — DONE.** `_execute_detached` spawns a per-child daemon thread that blocks on `os.waitpid(pid, 0)` (wait_fn injectable seam; `ChildProcessError` swallowed, other failures logged) — fire-and-forget for the caller, buried for the OS. Tests assert waitpid is called with `(pid, 0)` after the child exits and that a failing reaper never affects the detached result.
- **DB migration note:** `init_db` now idempotently `ALTER TABLE`s pre-existing SQLite DBs that lack the `triggers` column (`create_all` only creates missing tables — a legacy `streamdeck.db` would otherwise 500 on every config write).
- **Tests:** `tests/test_triggers.py` (35; judge replaced the two conditional-start integration tests with unconditional-start + switch-into-trigger-config regression, both mutation-verified — the switch test needed a startup-race gate: a test that flips shared state immediately after thread start lets the mutant path never execute). E2E: parity-demo triggers trio + parity-fullstack real-API round-trip; both pairs re-run green on rebuilt bundles after the demo-api fix. Final counts: pytest 124 passed (5 hardware-deselected), demo pair 27, fullstack pair 12, tsc clean.
- **Judge fixes (all mutation-verified):** (1) unconditional watcher start above; (2) demo-api `update()` now CLEARS triggers when the payload omits the key — the builder's version preserved the old block, diverging from the real PUT's replace semantics (the clear E2E never saved+reloaded, so it missed this); (3) watcher `run()` outer containment so an exploding `should_continue_fn` logs and returns instead of raising out of the thread.
- **Deferred — apply-once keyed on config NAME:** two configs with the same name can suppress each other's applies (the guard compares `name` strings). Config ids exist server-side but not in `--config`-file configs, so name is the only universal key today; duplicate names are plausible but low-probability. Roadmap follow-up: pass the config id through when present and fall back to name.

## Round 6 — text completion: DONE (2026-09-20, builder round)

- **CLI**: DONE — typer's built-in shell completion was silently disabled by `add_completion=False`; removed, so `streamdeck --install-completion` / `--show-completion` (bash/zsh/fish) work. `tests/test_cli.py` (6 subprocess tests) pins the options' presence, the documented command list, a `--show-completion` script, and the `--help` timing bound (imports stay lazy — the smoke `streamdeck --help` never pulls uvicorn/pillow/db at parse time; measured ~0.15s).
- **UI**: DONE — `CommandInput` (controlled dropdown; datalist rejected as browser-dependent) wired into ActionEditor Executable + Arguments. Executables: static `COMMON_BINARIES` (browser can't scan PATH) + typed history (`localStorage streamdeck_recent_executables`, cap 10, absolute paths only). Arguments: static `COMMON_FLAGS` per known binary after a leading `-`. Both: the 7 template variables complete inline after `{{` (closing braces inserted; label-row popovers remain). First item highlighted on open; Enter/Arrows/Escape/click; blur records history. Mutations (all rebuilt + killed): empty filter → 5 fail; history write removed → history spec fails; flags map disabled → flags spec fails.
- Deeper automations: multi-step sequences (`{"type":"sequence","steps":[...]}` with optional delays), chained toggle-state actions.

## Round 7 — multi-step sequence actions: DONE (2026-09-20, builder round, P18)

- **Agent execution — DONE.** `execute()` recognizes `{"type": "sequence", "steps": [...]}`; refactor extracts `_execute_one(action, context, depth)` so top-level actions and sequence steps share ONE dispatch path (steps may be commands or nested sequences; nesting capped at `MAX_SEQUENCE_DEPTH = 4` — deeper yields a structured error for that step, never runaway recursion). Aggregation: continue-on-error by DEFAULT (`"done"` / `"partial"` / `"failed"`-if-all-failed; a P14 `"detached"` step counts as a successful launch — mixed detached+done is `"done"` and stopOnError does NOT abort after one); `stopOnError: true` aborts remaining steps on first failure (`"failed"`, unexecuted steps `{"status": "skipped"}`). Per-step `delayMs` sleeps BEFORE the step, sanitized by `_as_delay_ms` (non-numeric/negative → 0, clamped at `MAX_DELAY_MS = 60000`). No sequence-level timeout (per-step command timeouts already bound each step — documented in the P18 parity row). Template expansion recurses into steps with the same button context (verified: `expand_template_vars` was already recursive over dicts/lists; end-to-end stdout test pins `{{button_index}}` inside a step's arguments). Crash-safety holds: the outer catch-all now wraps `_execute_one`, and the garbage matrix (missing/non-list `steps`, non-dict steps, corrupt step types) returns structured results.
- **Runner wiring — DONE, minimal.** `dispatch_action`'s dict gate widened from `type == "command"` to `type in ("command", "sequence")`; sequences are dict-only by design (they carry a steps payload a bare string cannot hold). The JSON column already preserves nested dicts (round-2 proof), so no other change; `test_parity.py::test_sequence_action_reaches_agent_queue` pins the verbatim queue payload.
- **UI — DONE (structured minimal editor).** ActionEditor gains "Sequence (run multiple actions)": per-step compact cards (Executable + Arguments via CommandInput, attached/detached mode, per-step "Delay before step (ms)" number input, remove button), "Add step", sequence-level "Stop on Error" switch (aria-labeled — the Action tab also hosts the Toggle Mode switch; unlabeled `getByRole("switch")` is a strict-mode violation), and an Advanced JSON fallback textarea for step types the card form does not host (nested-per-step ActionEditor deliberately NOT built — sequences of commands cover the 90% case). JSON View round-trips `{"type": "sequence", "steps": [...]}`.
- **Tests:** `tests/test_agent.py` +12 (now 30): happy path, continue-on-error→partial, all-failed, stopOnError with marker-file never-ran proof, delayMs respected (elapsed ≥ 0.2s), clamp unit test + monkeypatched-sleep clamp test, `_as_delay_ms` sanitizer, depth-2 nesting, depth-4 cap, garbage-sequence matrix, template recursion + end-to-end expansion. `test_parity.py` +1 (sequence reaches agent queue verbatim). E2E: parity-demo +3 (build+JSON round-trip, delay/stopOnError persistence, step removal), parity-fullstack +1 (two-step sequence round-trips `GET /config/{id}` structurally). Mutations (all killed + reverted): (a) abort-on-first-failure → continue-on-error test fails; (b) depth cap disabled → cap test fails; (c) clamp removed → sanitizer + clamp tests fail; (d) gate back to command-only → dispatch test fails; (e) Add-step handler disabled + REBUILD → all 3 demo sequence E2E fail. Final: pytest **143** / demo pair **34** / fullstack pair **14** / tsc clean.

## Round 8 (next) — candidates

- Deeper automations (continued): chained toggle-state actions (a toggle state's action could itself be a sequence — supported by the agent already; needs UI affordance), step types beyond commands in the structured editor (switch-config, exit), sequence results surfaced in the UI (agent result polling display).
- Sequence step templates: per-step `delayMs` exists; a sequence-level default delay is a possible follow-up.

## Round 8 — Diátaxis documentation site: DONE (2026-09-20, builder round)

- **docs/site/ built** — the whole solution documented in Diátaxis structure
  (tutorials / how-to / reference / explanation), 18 pages + index:
  - Tutorials: [zero-to-deck](../site/tutorials/zero-to-deck.md) (uvx install → serve → ui →
    config in browser → assign → runner renders), [triggers](../site/tutorials/triggers.md)
    (frontmost app + wifi end-to-end, incl. the priority rule and apply-once behavior).
  - How-to (9): animated GIF upload, pause/resume animation, attached vs detached,
    multi-step sequences, switch-config from a button, automatic-switching triggers,
    nominate agents, completion (CLI + UI), run-the-test-suites — every guide with
    numbered steps + verification; real Playwright snippets quoted/adapted from
    `e2e/parity-demo.spec.ts` / `e2e/parity-fullstack.spec.ts` with source attribution.
  - Reference: CLI (every command/flag from real `--help`), REST API (13 endpoints,
    dialect rules incl. camelCase-vs-snake_case, schema-less JSON columns, whole-row PUT,
    DELETE-returns-row), config schema (ButtonConfig, idle/pressed, font, toggleStates,
    animation, all action types), triggers block, parity P1–P18 index.
  - Explanation: architecture (+4 Mermaid diagrams: system map, queue→poll→result
    lifecycle, trigger-watcher loop, action-execution flow), animation pipeline
    (pipeline + pause state machine diagrams), template variables (expansion-points
    diagram), crash-safety (catch-all layer diagram + one-status-list-or-many lesson),
    testing philosophy (builder→critic→judge diagram), provenance rule.
- **Accuracy grounding:** every CLI flag/endpoint/config key/default checked against
  source (cli.py, app.py, agent.py, runner.py, triggers.py, models.py, types/streamdeck.ts,
  ActionEditor/ToggleEditor/TriggersEditor/CommandInput/ImageUpload, demo-api.ts,
  openapi.yaml, parity.md). CLI verified against live `--help` output for all 8 commands;
  API spot-checked with curl against a scratch dummy-transport instance (GET /devices,
  POST/GET /config, PUT /device/{id}/config/{id}, GET /device/{id}/config,
  DELETE /config → 200-with-row, GET/POST /agents, POST /agent-actions → 202);
  parity row count confirmed (exactly 18, P1–P18).
- **Screenshots restored:** `docs/screenshots/` was EMPTY while docs/parity.md referenced
  6 PNGs — captured all six (fullstack-dashboard, fullstack-agents, agents-empty-state,
  agents-nominated, upload-gif-badge, action-editor-exit) with the local playwright-core +
  cached chromium (no network installs), seeded via REST-only scripts against scratch
  ports (all servers killed after). UI's localStorage API URL had to be set through the
  Settings flow in the capture script (default :8000 ≠ scratch ports).
- **Root README** gained a Documentation section linking docs/site/README.md.
- **Loop status: COMPLETE** — 8 rounds, P1–P18 all implemented, parity-certified and
  now documented. Remaining candidates (chained toggle-state action affordances,
  sequence step types beyond commands in the structured editor, sequence results in
  the UI, per-button pause, apply-once keyed by config id) live in the candidates list
  above; nothing in P1–P18 is open.
- Verification at time of writing: pytest **146 passed, 5 deselected**;
  `bunx tsc --noEmit -p tsconfig.app.json` clean; docs link-check script green
  (all relative links + image paths resolve).

## Round 9 — multi-button image backgrounds (P19): DONE (2026-09-23, builder round)

- **Config surface — DONE.** `StreamDeckConfig.backgrounds`: schema-less JSON
  column like `buttons`/`triggers` — `[{"id": "hero", "image": <source>,
  "x": 0, "y": 0, "width": 4, "height": 2}]` (region in key cells, x/y =
  top-left). Same whole-row PUT replace semantics as `triggers` (omitted key
  clears the block); idempotent `PRAGMA`-checked `ALTER TABLE` migration
  generalized to `_migrate_json_columns` (triggers + backgrounds) for legacy
  DBs. API round-trip pinned by `test_backgrounds_roundtrip_through_real_api`.
- **Runner rendering — DONE.** `streamdeck/runner.py`: `_normalized_backgrounds`
  (malformed entries dropped: non-dict, no image, non-numeric/negative region,
  zero-sized; string numerics coerced), `_covering_background` (region test in
  deck-layout coordinates; z-order = last covering entry wins),
  `_background_frames` (decoded PIL frames cached per bg id), and
  `_background_composite` — ONE full-deck canvas per frame, image scaled to
  COVER the region (aspect preserved, center-cropped), then
  `_tile_for_key` slices each key's tile and pre-applies the INVERSE of the
  deck's per-key transform (`key_image_format` flip/rotation) so the vendored
  `_to_native_format` conversion restores display orientation — spans stay
  seamless on Original/XL/Mini/Neo, the flip/rotate decks. Each tile registers
  under the synthetic source `background:<id>#<key>` in `persistent_images`
  (animated → `itertools.cycle`, static → plain bytes, so the tick neither
  pulls nor rewrites stills), riding the EXISTING animate loop and repaint
  paths. `update_key_image` consults backgrounds only when the button has no
  image of its own (own-image-wins); text-only covered keys draw their label
  over the tile. P13 pause extended: pause on any covered key sets EVERY tile
  source of that background (per-key pause would tear the span);
  button-image pause untouched. `apply_config` purges tile cycles + frame +
  composite caches on every config swap.
- **UI — DONE.** New **Backgrounds** page (`frontend/src/pages/Backgrounds.tsx`,
  sidebar item + `/config/:id/backgrounds` route + ConfigEditor header link):
  config picker, per-span card (ImageUpload + x/y/width/height), add/remove,
  live per-cell preview using the SAME crop math as the runner
  (`backgroundTileStyle` in ButtonGrid, mirrored on the page). The
  ConfigEditor grid shows span tiles behind imageless cells (last covering
  span wins, mirroring runner z-order). Demo-api `update()` replace semantics
  extended to `backgrounds`.
- **Tests — DONE.** `tests/test_backgrounds.py` (19, mutation-verified:
  paint-hook disabled → 8 fail, restored clean): normalization matrix,
  coverage/z-order, tile bytes on covered keys, own-image-wins (animated
  source so registration is observable), text-over-tile, one-composite
  slicing, inverse-transform round-trip (pixel-exact), animated cycle + tick
  advance, static-as-bytes, shared pause across the span + isolation from
  button-image pause, corrupt-image defense, indexed-id fallback, apply_config
  purge + repaint, press-repaint keeps tile. E2E: parity-demo +4 (sidebar
  link, upload+coverage preview, save+reload+JSON round-trip, empty-span
  skip, remove — 34 total) and parity-fullstack +2 (span round-trips through
  the real API with region + data URI verbatim; PUT-without-key clears — 16
  total). LESSON: the Backgrounds page URL is `/config/{id}/backgrounds` —
  the config id is the SECOND-to-last URL segment; a `.pop()` id extraction
  grabs the word "backgrounds" and 404s. Also: a stale server on :8000
  (Playwright `reuseExistingServer`) served pre-P19 code — `backgrounds`
  missing from GET responses was a server-restart issue, not a code bug.
- **Docs — DONE.** Parity rule **P19** in `docs/parity.md` (19 rows verified)
  + summarized row in `docs/site/reference/parity.md` (P1–P19);
  `backgrounds` in the config-schema reference (new section with runner
  semantics) + openapi.yaml (`BackgroundSpan` schema + Config property);
  new how-to [compose multi-button image backgrounds](docs/site/how-to/image-backgrounds.md)
  (indexed in how-to/index.md + site README, cross-linked from
  animated-gif-button + real-hardware's manual-pass table); link check green
  on all touched docs.
- Final counts: pytest **177 passed, 5 deselected**; demo pair **34** /
  demo-ui **5** / fullstack pair **16** / full-stack **3**; `bunx tsc
  --noEmit -p tsconfig.app.json` clean.

## Rules of engagement

- Commit message convention: `feat:`, `test:`, `docs:`, `fix:` prefixes (see git log).
- Every round: builder red→green → critic audit (mutation-verified, flake-checked) → judge certify → commit.
- Frontend mutations require `./scripts/build-frontend.sh` (bundles are prebuilt; source-only mutations are silent no-ops).
- Ports: 8080/8081/8000 free for Playwright; 8090 is a live session — never touch.
- Worktrees under `worktrees/` for parallel approaches; merge to main only after critic+judge.