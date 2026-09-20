# Streamdeck Monorepo

One repo, your whole Stream Deck stack. A ported, provenance-tracked, monorepo
combining a device control library, a config API + device runner, and a web UI.

```sh
uvx --from /path/to/streamdeck-monorepo streamdeck serve    # API + runner backend
uvx --from /path/to/streamdeck-monorepo streamdeck demo     # UI with no server needed
uvx --from /path/to/streamdeck-monorepo streamdeck run      # device runner only
uvx --from /path/to/streamdeck-monorepo streamdeck list     # what's attached?
uvx --from /path lets user use their streamdeck more using a single uvx command!
```

## What's inside

| Path | Purpose | Ported from | Upstream |
| ---- | ------- | ----------- | -------- |
| `streamdeck/core/` | HID control of Elgato Stream Decks | fork `python-elgato-streamdeck` @ `47c97ad` | [abcminiuser v0.10.0](https://github.com/abcminiuser/python-elgato-streamdeck) (MIT) |
| `streamdeck/{app,db,models}.py` | FastAPI config API + SQLite storage | repo `streamdeck` @ `078b8b2` | — |
| `streamdeck/runner.py` | Device runner (renders buttons, handles key events) | `streamdeck/read_config/main.py` @ `078b8b2` | — |
| `streamdeck/agent.py` + API | Nominate-a-computer action routing | new (user use-case) | — |
| `frontend/` | React/Vite/shadcn web UI with **offline demo mode** | repo `streamdeck-frontend` @ `bef572b` | — |
| `e2e/` | Playwright suites (UI-only offline + full-stack with dummy deck) | new | — |
| `tests/` | Python integration tests (dummy transport, TestClient) | new | — |

See [PROVENANCE.md](PROVENANCE.md) for exact commits and licenses, and
[docs/dev.md](docs/dev.md) for development workflows.

## Quick start

```sh
# 0) Get it
git clone https://github.com/Lewiscowles1986/streamdeck-monorepo
cd streamdeck-monorepo

# 1) Serve the API + device runner
STREAMDECK_TRANSPORT=libusb uvx . streamdeck serve          # with hardware
STREAMDECK_TRANSPORT=dummy uvx . streamdeck serve           # hardware-free (dev/E2E)

# 2) Web UI, two ways:
uvx . streamdeck demo                                       # no server URL needed
uvx . streamdeck ui                                         # full-stack (talks to API on :8000)

# 3) Nominate a computer for actions (edge use-case)
uvx . streamdeck agent --server http://localhost:8000       # on the target machine

# 4) Shell completion (bash/zsh/fish — typer built-in)
uvx . streamdeck --install-completion                       # once per shell
```

`STREAMDECK_DB` (default `streamdeck.db` in cwd) selects the SQLite file;
`STREAMDECK_TRANSPORT=dummy` emulates decks for development, tests and E2E.

## Demo mode (no server, no device)

The frontend works without any server URL: on load, if the configured API is
unreachable, the UI transparently falls back to an in-browser mock (`src/lib/demo-api.ts`)
backed by `localStorage`. You can create configs, edit buttons, nominate agents
— everything except actually driving keys. This is the "mindshare" mode:
share the link, play with the UI, no device required.

- `streamdeck demo` serves a demo build (`dist-demo/`, built with
  `VITE_DEMO_MODE=1`) where demo mode is default-on. `streamdeck ui` serves
  the normal build.
- In the normal build, demo mode activates automatically when the API is down,
  with a banner and a "Try demo" action.