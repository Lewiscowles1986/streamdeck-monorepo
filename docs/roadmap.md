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
- **Deferred to R5 — detached-mode zombie reaping.** A detached child that exits while the agent stays up is not reaped (no `waitpid`), leaving a zombie entry per finished child. Accepted for now: the agent is a long-lived CLI process, so this is cosmetic, not a leak of memory/fds. Fix candidate: spawn via a small daemon thread that `os.waitpid(pid, 0)`s after the Popen returns (keeps fire-and-forget semantics — the executor still returns immediately; the thread just buries the child later).

## Round 5 — auto config switching (triggers)

- Config gains optional `triggers`: `{"app": ["Slack"], "network": {"ssid": "...", "interface": "en0"}}` (macOS first: `osascript`/`lsappinfo` for frontmost app, `airport -I`/`networksetup` for SSID).
- Runner polls (e.g. 5s) or subscribes; on match, swaps active config and re-renders. Priority: explicit user press > app trigger > network trigger > default.
- Tests: trigger evaluation pure-function + pytest; E2E: trigger editor UI surface.

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