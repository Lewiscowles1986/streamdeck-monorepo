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

## Round 6 — text completion

- **CLI**: typer completion via `streamdeck --install-completion` (click/typer built-in) for zsh/bash/fish.
- **UI**: completer for command fields (executable path completion against PATH, flag completion for common binaries via a static map), template-var autocomplete in the ActionEditor fields (insert-or-complete inline).
- Deeper automations: multi-step sequences (`{"type":"sequence","steps":[...]}` with optional delays), chained toggle-state actions.

## Rules of engagement

- Commit message convention: `feat:`, `test:`, `docs:`, `fix:` prefixes (see git log).
- Every round: builder red→green → critic audit (mutation-verified, flake-checked) → judge certify → commit.
- Frontend mutations require `./scripts/build-frontend.sh` (bundles are prebuilt; source-only mutations are silent no-ops).
- Ports: 8080/8081/8000 free for Playwright; 8090 is a live session — never touch.
- Worktrees under `worktrees/` for parallel approaches; merge to main only after critic+judge.