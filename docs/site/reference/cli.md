# CLI reference

The `streamdeck` command (installed as `streamdeck`, or run via
`.venv/bin/python -m streamdeck.cli`, or `uvx . streamdeck …`). One command
for the whole stack. Output below is from the real `--help`; every option
shown exists.

```text
Usage: streamdeck [OPTIONS] COMMAND [ARGS]...

  Standalone Stream Deck control stack (API, device runner, web UI).

Options:
  --install-completion   Install completion for the current shell.
  --show-completion      Show completion for the current shell, to copy it
                         or customize the installation.
  --help                 Show this message and exit.

Commands:
  serve          Run the configuration API (FastAPI + uvicorn).
  list-devices   List attached Stream Deck devices.
  run            Run the device runner against attached decks.
  agent          Run the nominate-a-computer agent loop on this machine.
  demo           Serve the web UI in offline demo mode (no API server
                 required).
  ui             Serve the built frontend pointing at the API (full-stack
                 mode).
  version        Print version information.
  export-config  Export a stored config as JSON (backup / sharing).
```

Global environment variables (not flags — set as env vars):

| Variable | Default | Meaning |
| --- | --- | --- |
| `STREAMDECK_DB` | `streamdeck.db` (cwd) | SQLite file for configs/devices/agents |
| `STREAMDECK_TRANSPORT` | `libusb` | `dummy` emulates decks (dev/tests/E2E) |
| `STREAMDECK_API` | `http://localhost:8000` | API base for the runner/agent/export clients |
| `STREAMDECK_UI_DIR` | — | override the UI directory `demo`/`ui` serve from |

---

## `streamdeck serve`

Run the configuration API (FastAPI + uvicorn).

| Option | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address for the API |
| `--port` | `8000` | Port for the API |
| `--reload` | off | Auto-reload on code changes |

Initializes the database (creates tables; migrates a legacy DB to add the
`triggers` column) before serving. See [API reference](api.md) for the
endpoints.

```sh
STREAMDECK_TRANSPORT=dummy streamdeck serve --port 8000
```

## `streamdeck list-devices`

List attached Stream Deck devices (type, serial, key count). No options.
Enumerates with the transport from `STREAMDECK_TRANSPORT`.

## `streamdeck run`

Run the device runner against attached decks.

| Option | Default | Meaning |
| --- | --- | --- |
| `--config` | — | Path to a config JSON file (bypasses the API-assigned config) |
| `--device-id` | first matching deck | Device serial number to drive |
| `--brightness` | `30` | Key brightness 0–100 |
| `--ignore-device-type-check` | off | Skip `deviceType` matching |

Notes:

- Without `--config`, the runner loads the config assigned to the device via
  `GET /device/{device_id}/config` (API base from `STREAMDECK_API`).
- Deck type is matched against the config's `deviceType` case-insensitively
  with space→dash tolerance; use `--ignore-device-type-check` to skip the
  check.
- The runner starts the 30 fps animation loop and the trigger watcher
  (5 s poll) per deck.

## `streamdeck agent`

Run the nominate-a-computer agent loop on this machine.

| Option | Default | Meaning |
| --- | --- | --- |
| `--server` | `$STREAMDECK_API` / `http://localhost:8000` | Base URL of the Stream Deck server |
| `--interval` | `5.0` | Poll interval in seconds |

Registers this machine (stable id in `~/.streamdeck-agent-id`), polls
`GET /agents/{id}/actions`, executes queued actions
([how-to](../how-to/nominate-agents.md)), reports results.

## `streamdeck demo`

Serve the web UI in **offline demo mode** (no API server required) — serves
the demo build (`dist-demo/`, built with `VITE_DEMO_MODE=1`); the in-browser
mock backs the app.

| Option | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8080` | Port |

If no built frontend exists the command exits with a hint to run
`scripts/build-frontend.sh`.

## `streamdeck ui`

Serve the built frontend pointing at the API (**full-stack mode**) — serves
the normal build (`dist/`). The UI talks to the API whose base URL is
configured in the UI's Settings page (localStorage) — default
`http://localhost:8000`.

| Option | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8080` | Port |

## `streamdeck version`

Print version information (currently `streamdeck 0.1.0`).

## `streamdeck export-config`

Export a stored config as JSON (backup / sharing). Reads from the API
(`STREAMDECK_API`).

| Argument/Option | Required | Meaning |
| --- | --- | --- |
| `config_id` (argument) | yes | Config UUID to export |
| `--output` | no | Output file (default: stdout) |

```sh
streamdeck export-config 6b57e5c5-7ec9-4a31-9189-ce60f2ef6a8c --output comms.json
```

---

## Completion (P17)

Shell completion is typer's built-in and stays enabled:
`--install-completion` / `--show-completion` (bash/zsh/fish). The parse path
is lazy — `--help` is bound to be fast by a regression test
(`tests/test_cli.py`). See [the completion how-to](../how-to/completion.md)
for the UI half.