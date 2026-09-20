# Loop Roadmap — long-horizon memory

> Updated each round. Committed on every green cycle so it survives sessions.
> Loop pattern per round: builder → critic → judge (subagents), commit on green.

## Done

- **R1 (certified, `bcb949f`)** — animated GIF parity: upload→data URI→badge E2E (demo+fullstack), runner multi-frame decode + shared cycle pytest tests. P10 rule added.
- **R2 (certified, `cd7d0ae`)** — config-editor parity: template-var insertion UI (P1), timeout/env editor + wire hop (P8), font config round-trip (P2), pressed-state independence. 45 pytest / 25 E2E green.

## Round 3 (current)

- **A. Toggle E2E** — toggle editor switch, add/remove state, per-state overrides (image/text/action), save+reload, ButtonCell badge. Plus **device assign→render loop** test: assign config to dummy deck via API → runner renders its buttons (candidate #1).
- **B. Animation pause (worktree `worktrees/anim-pause`)** — per-source pause on a frame: `"pause"` / `"play"` / `"toggle-animation"` bare-string actions (alongside `"exit"`), optional `frameIndex` advance-and-hold, `paused_images: dict[str, bool]` keyed by source string (shared-pause semantics per P10); config surface `animation: {paused, frameIndex}` in ButtonConfig + ActionEditor UI; pytest: pause holds frame, resume continues from held position, toggle-animation action contract; E2E: UI exposes the controls.
- Decision recorded: **shared pause** (source-keyed) — consistent with P10 shared-cycle; per-button pause deferred as a follow-up if needed.

## Round 4 — command hardening + new action types

- **launch/attached/detached**: extend CommandAction with `mode: "detached" | "attached"` (default attached = current behavior). Detached = Popen without wait (process survives agent); attached = current run with timeout. Focus: server NEVER crashes — all exceptions caught, reported via action result.
- **switch-config action**: `{"type":"switch-config","configId":...}` or bare-string `"switch-config:<id>"` — runner swaps its active config (and re-renders all keys). Backend + ActionEditor UI + tests.
- **change-screen action**: `{"type":"screen","page":N}` or `"screen:<n>"` — concept: multiple "pages" of buttons on one deck; paging flips the button grid. Needs a page model in config (pages[] or offset). Scope carefully in builder round; may defer to R5 if it balloons.
- Hardening sweep: subprocess with `timeout=...`, kill on timeout (already in agent), stdout/stderr capture bounded, try/except around every dispatch path, TransportError isolation.

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