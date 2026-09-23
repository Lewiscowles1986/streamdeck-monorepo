# Development guide

## Layout

```
streamdeck/            Python package (core lib, API, runner, agent, CLI)
streamdeck/core/       vendored python-elgato-streamdeck fork (see PROVENANCE.md)
frontend/              React/Vite/shadcn UI (demo mode included)
tests/                 Python integration tests (no hardware; dummy transport)
e2e/                   Playwright suites (demo-ui + full-stack)
scripts/               build-frontend.sh, hardware-smoke.sh, install-hidapi.sh,
                       hardware-tour.py (interactive real-deck eval TUI)
```

## Setup

```sh
uv venv --python 3.12 && uv pip install -e '.[dev]'
(cd frontend && bun install)          # or npm install
scripts/build-frontend.sh             # builds dist (full-stack) + dist-demo (offline)
```

## Everyday commands

| Command | What it does |
| ------- | ------------ |
| `uvx . streamdeck serve` | API on :8000 (env `STREAMDECK_TRANSPORT=dummy` for no hardware) |
| `uvx . streamdeck demo` | UI on :8080 in offline demo mode (no backend) |
| `uvx . streamdeck ui` | UI on :8080 talking to the API |
| `uvx . streamdeck run` | device runner only |
| `uvx . streamdeck agent` | agent loop for this machine |
| `.venv/bin/python -m pytest tests` | integration suite (dummy transport) |
| `.venv/bin/python -m pytest -m hardware tests/test_hardware.py` | hardware smoke tests (opt-in; needs hidapi — see [the real-hardware guide](site/how-to/real-hardware.md)) |
| `.venv/bin/npx playwright test --project=demo-ui` | UI-only E2E (no backend) |
| `.venv/bin/npx playwright test --project=full-stack` | full-stack E2E (dummy device) |

## Environment variables

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `STREAMDECK_DB` | `./streamdeck.db` | SQLite file for configs/devices/agents |
| `STREAMDECK_TRANSPORT` | `libusb` | `dummy` emulates decks (dev/tests/E2E) |
| `STREAMDECK_API` | `http://localhost:8000` | API base for runner/agent clients |

## Demo mode design

- `frontend/src/lib/demo-api.ts` implements the REST surface in-browser
  (localStorage persistence). `lib/api.ts` routes every call through it when
  demo mode is on.
- Demo builds are produced with `DEMO_MODE=1` (script sets it) →
  `VITE_DEMO_MODE=1` is baked in; demo mode is the default there and can be
  exited (banner button), which persists.
- Normal builds fall back to demo only via explicit user action
  ("Try demo mode") on the not-connected screens.
- Why: the UI must be shareable without a server or device (mindshare), while
  device functionality stays first-class and is covered by its own E2E suite.

## Agent (nominate a computer)

1. On the target machine: `streamdeck agent --server http://deck-server:8000`
2. In the UI (or API), nominate that agent for a device:
   `PUT /device/{id}/agent/{agent_id}`
3. Buttons with `action: {type: "command", executable, arguments}` route to
   the nominated agent via the queue (`/agent-actions` → `/agents/{id}/actions`).
4. The agent executes (`subprocess.run`) and reports results.

## Vendored core updates

See `PROVENANCE.md` "Updating the vendored fork". Keep `Dummy.py` deltas
minimal and documented.