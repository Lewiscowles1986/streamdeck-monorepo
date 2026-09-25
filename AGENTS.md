# AGENTS.md

Guidance for AI coding agents working in this repository. Written from the
post-port review of the session that created this repo (initial commit `9e76501`,
tag `v0.1.0`, 2026-09-19): 21 Python integration tests, 8 Playwright E2E tests,
and the `uvx` single-command UX all validated green — including every mistake
made along the way.

## What this repo is

A standalone monorepo porting three former git repos with recorded provenance:

| Part | Source | Lives here |
| ---- | ------ | ---------- |
| Core device library | `python-elgato-streamdeck` fork @ `47c97ad` (upstream v0.10.0, MIT) | `streamdeck/core/**` |
| Server/runner | `streamdeck` backend @ `078b8b2` | `streamdeck/{app,db,models,runner}.py`, `streamdeck/assets/**` |
| Web UI | `streamdeck-frontend` @ `bef572b` (Lovable/Vite/React) | `frontend/**` |
| New in this port | agent "nominate a computer", CLI, demo mode, tests | `streamdeck/agent.py`, `streamdeck/cli.py`, `frontend/src/lib/demo-api.ts`, `tests/**`, `e2e/**` |

**Never lose provenance.** `PROVENANCE.md` and `.git-provenance.json` record
exact source commits, the port map, and the only vendored-code deltas. If you
change vendored code under `streamdeck/core/`, document the delta in
`PROVENANCE.md` ("Local changes to vendored code") in the same change.

## Environment facts (verified, macOS)

- Toolchain: `uv` (Python env/deps), `bun` (frontend + Playwright runner). Setup:
  `uv venv --python 3.12 && uv pip install -e '.[dev]'`, then
  `(cd frontend && bun install)` and `./scripts/build-frontend.sh`.
- Python venv is at `.venv/`. Run tests as `.venv/bin/python -m pytest tests -q -m 'not hardware'`.
- Sandbox note: commands that `mkdir`/write outside the workspace tree (e.g.
  sibling repos) get blocked in the sandbox and must run unsandboxed.

## Commands that must stay true

```sh
.venv/bin/python -m pytest tests -q -m 'not hardware'   # integration, no hardware
.venv/bin/python -m pytest -m hardware tests/test_hardware.py  # opt-in, real deck
bunx playwright test --project=demo-ui                  # from repo root, not frontend/
bunx playwright test --project=full-stack               # from repo root
./scripts/build-frontend.sh                             # builds dist-demo AND dist
STREAMDECK_TRANSPORT=dummy uvx --from . streamdeck list-devices   # uvx smoke
```

CI (`.github/workflows/ci.yml`) mirrors exactly these commands. If you change
how a suite runs, update CI in the same change — the workflow was once written
assuming `playwright.config.ts` lived in `frontend/`; it lives at the **repo
root**, and the E2E specs in `e2e/`.

## Hard-won lessons (do not re-learn these)

### Vendored core (`streamdeck/core/`) quirks

- **`is_open` shadowing bug (fixed upstream bug, keep it fixed):** the Dummy
  transport once had an `is_open` *attribute* shadowing the `is_open()` *method*,
  producing `TypeError: 'bool' object is not callable` on every guarded
  operation. Any new transport must keep the method intact.
- **Dummy transport enumerates one deck per known PID (16 decks).** All decks
  must get a **deterministic synthetic serial** (`DUMMY<vid><pid>`). When serials
  were empty, every device row shared a primary key and API tests failed with
  DB PK-collision errors.
- **Serial report layouts differ by deck generation:** older decks read the
  serial via feature report `0x03` (data at offset 2), newer decks read report
  `0x06` (offsets 2 *and* 5 — Studio/Plus read offset 5 and showed truncated
  "MY…" serials otherwise). The Dummy writes the synthetic serial at **both
  offsets of both reports** so every deck class reads a clean, unique value.
- The core library raises if you open an already-open deck. Early CLI/runner
  code double-opened the deck and closed it before reading metadata
  ("read while closed" in `list-devices`). Capture metadata **inside the open
  window**; never open twice.

### API layer (FastAPI + SQLModel)

- **List endpoints + aliased table models are a trap.** Returning
  `list[AgentAction]` from an endpoint whose response model FastAPI clones
  degenerates to `[{}]` — fields `null`, aliased fields missing — even though a
  direct function call serializes fine. The durable fix used here: explicit
  `model_dump(by_alias=True)` serialization in the endpoint, serialized
  **before the commit** (attributes are expired on commit and come back `None`).
  Single-entity endpoints are fine; it's the list/ORM-requery paths that bite.
- **Alias dialect is camelCase.** The API accepts/returns camelCase aliases.
  The agent client initially posted snake_case and silently mismatched. Rule:
  **send camelCase, read both spellings** when resolving device/agent fields.
- **Never `importlib.reload` the models/db modules in tests.** Reloading
  duplicates SQLAlchemy table definitions (`Table 'X' is already defined`).
  Create tables lazily at app startup instead.

### Frontend

- **Vite only inlines `VITE_*`-prefixed env vars.** A build script that set
  `DEMO_MODE=1` silently baked nothing in; demo mode appeared broken. Use
  `VITE_DEMO_MODE=1` (see `scripts/build-frontend.sh`), and rebuild **both**
  bundles (`dist-demo` first, then `dist`) whenever demo-mode code changes.
- **Path resolution:** `frontend/` is at the **repo root**, not inside the
  Python package. Code resolving the frontend dir relative to
  `streamdeck/__file__` (`streamdeck/frontend`) is wrong — resolve from the
  repo root and fall back sensibly.
- The frontend was generated by Lovable. Watch for leftover branding
  (`<title>Lovable App</title>`, `@Lovable` footer) and strip it when touched.

### Tests & E2E

- **Match accessible names exactly.** `getByRole("link", { name: /configs/i })`
  never matched because the nav link is **"Configurations"**. Substring regexes
  must match the full accessible name; same trap for "Devices". Prefer exact
  roles + names copied from the UI.
- **Never share ports between Playwright projects.** Both projects once bound
  `8080`; the full-stack test was silently served the **demo build** (demo
  devices "Stream Deck XL (demo)" instead of the emulated deck). Ports are now:
  demo-ui `8080`, full-stack UI `8081`, API `8000`. Keep them separate.
- **State pollution makes flaky tests.** The full-stack assign test failed
  intermittently because a reused database already contained a duplicate
  "Stack Layout". E2E fixtures must reset/namespace their data (unique names,
  fresh `STREAMDECK_DB`).
- **Write device-agnostic tests.** A test once used key 31, which is out of
  range for the 15-key emulated Original deck. Derive indices from
  `key_count()` (e.g. exit button = last key) instead of hardcoding.
- **Hardware tests are opt-in** (`pytest -m hardware`, `tests/test_hardware.py`,
  `scripts/hardware-smoke.sh`). Never let them run in default suites/CI.

### Environment-dependent tests (green locally, red in CI)

Twice, a suite passed on this Mac and failed on CI for reasons that had nothing
to do with the code. Both classes are cheap to prevent:

- **Strip ANSI before asserting on CLI output.** Rich colourises `--help`
  whenever a colour env is present, and CI sets one, so `--install-completion`
  arrives wrapped (`"\x1b[1m--install-completion\x1b[0m"`) and a literal `in`
  assertion fails. Assert against `re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out)`
  — tests should pin content, not Rich's colour decisions. Reproduce with
  `FORCE_COLOR=1 .venv/bin/python -m pytest tests/test_cli.py`.
- **Force the platform gate when testing macOS-only logic.** `get_frontmost_app`
  / `get_wifi_ssid` return `None` on non-macOS *before* touching `subprocess`,
  so on the Linux runner a patched `subprocess.run` never fires: tests pass for
  the wrong reason, or raise `KeyError` when they read state the mock should
  have set (`tests/test_triggers.py` has an `on_macos` fixture for this). Keep
  the genuine non-macOS contract as its own test — "returns None **and spawns
  nothing**" — so the gate is pinned in both directions.
- **Reproduce under CI conditions before trusting a green local run.** If
  behaviour depends on an env var, terminal, or OS, a local pass proves nothing
  about CI. Cheapest habit: run the suite once with the CI-ish env
  (`FORCE_COLOR=1`, and think about which branches are platform-gated).
- **When CI is red and you can't read the log, publish the failure instead.**
  GitHub job **logs** need a sign-in; the **step summary** and `::error`
  annotations do not. Piping pytest to a file and writing the `FAILED`/`E`
  lines to `$GITHUB_STEP_SUMMARY` (as `.github/workflows/ci.yml` now does) makes
  any red run readable without credentials. Guessing at an unreadable failure
  costs far more than five lines of workflow.

### Editing discipline (mistakes that cost debugging time)

- One file edit left **old and new fragments interleaved**, corrupting
  `agent.py`; another edit **removed functions still referenced** by
  `ApiContext`. After any multi-hunk edit, immediately verify: import the
  module (Python) or typecheck/lint (TS), and grep for orphaned references.
  If a file comes out corrupted, rewrite the whole function/file cleanly
  rather than patching on top.
- Don't ship placeholder or "sloppy" code intending to fix later — a
  placeholder module docstring and an unused `_agent_identity` hack both had to
  be cleaned up before anything could pass. Write it right the first time.
- Prefer the file-editing tools over shell heredocs (`cat > file <<'EOF'`) —
  heredoc writes bypass review of diffs and are harder to undo.

## Working agreements that worked

1. **Read everything you need before writing anything.** The port went smoothly because
   all three source repos, their transports, and the frontend pages were read
   (and git provenance captured) before scaffolding.
2. **Plan in todos; keep one in-progress.** The 9–12 item todo list was kept
   current through the whole session — it's how the added "agent" requirement
   (requested mid-session) was folded in without losing the thread.
3. **Mocks like The Dummy transport can be a key unlock.** Everything (API tests, E2E,
   `list-devices`) runs without hardware via `STREAMDECK_TRANSPORT=dummy`.
   Preserve that property: new features must be testable without a device.
4. **Frontend must work with zero server.** Demo mode (in-browser REST mock +
   localStorage) is a first-class product surface, not a test shim — user
   requirement. Keep `demo-api.ts` in sync with any API surface change. In the future 
   nuance around what to seed may help parallelize tests without plugging in or 
   purchasing multiple hardware devices.
5. **Validate the user-facing UX, not just tests.** Demo mode was verified in a
   real browser (banner, seeded devices, config creation) *before* E2E was
   written — that caught the branding and env-var issues early.
6. **Commit hygiene.** Review `git status` before staging; respect user
   `.gitignore` edits (`test-results/`, `node_modules/` were user-added and
   kept); commits are authored as the user with the agent credited in a
   `Co-authored-by:` trailer; tag meaningful milestones (`v0.1.0`).

## Gotchas checklist before you finish a change

- [ ] `pytest tests -m 'not hardware'` green
- [ ] Suite also green under `FORCE_COLOR=1` if it asserts on CLI stdout, and
      macOS-only logic was tested with the platform gate forced (not the host OS)
- [ ] Both frontend bundles rebuilt if frontend changed (`./scripts/build-frontend.sh`)
- [ ] `bunx playwright test` green (run from repo root)
- [ ] `uvx --from . streamdeck --help` / `version` / dummy `list-devices` still work
- [ ] Vendored-code changes documented in `PROVENANCE.md`
- [ ] No new hardcoded ports colliding with 8080/8081/8000
- [ ] No leftover Lovable branding, placeholders, or dead code
- [ ] `git status` clean of build artifacts (`dist*/`, `test-results/`, `node_modules/`)