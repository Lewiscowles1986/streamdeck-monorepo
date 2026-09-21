# Parity rules P1–P18

The frontend and backend must support every feature on both sides. The
authoritative contract is **[docs/parity.md](../../parity.md)** — this page
indexes it. The *executable form* of the contract is
`tests/test_parity.py`: **if a parity test fails, the two surfaces have
drifted** — fix the code or update both sides deliberately (and the table)
in the same change.

Status: **2026-09-20 — all 18 rows implemented and regression-tested**
(verified: exactly 18 rows, P1–P18, in `docs/parity.md`).

## The table (summarized)

| # | Rule (one line) | Primary tests |
| --- | --- | --- |
| P1 | UI-inserted template variables (`{{button_index}}` …) are expanded by the agent in `executable`, `arguments`, `cwd`, `env` | `test_expand_template_vars_*`, E2E template-var specs |
| P2 | UI font config is honored at render time; defaults = original port (Roboto 14, white, bottom) | `test_font_config_used_in_rendering`, E2E font persistence |
| P3 | `exit` action configurable in the UI; means the runner's bare-string `exit` | `test_exit_action_contract_is_bare_string` |
| P4 | Deleting a config clears `current_config_id` on devices (no dangling assignments) | `test_config_delete_clears_device_assignment`, E2E |
| P5 | CORS allows the UI origins (8080 demo, 8081 full-stack) | `test_cors_preflight_from_ui_port*` |
| P6 | Agent model dialect is snake_case (`last_seen`) — no camelCase aliases | `test_agent_dialect_is_snake_case` |
| P7 | `GET /device/{id}/config` returns camelCase device fields like every other endpoint | `test_device_config_endpoint_dialect` |
| P8 | Action `timeout` configurable in the UI, honored by the agent executor | `test_command_action_timeout_env_dialect`, wire-hop roundtrip |
| P9 | All 8 vendored deck types render a grid in both name dialects, with a safe fallback | `deviceDimensions()`/`deviceTypeLabel()` + E2E |
| P10 | Data-URI animated GIFs decode once per source into a shared `itertools.cycle`; 30 fps loop drives every button showing the source | frame-decode tests, GIF E2E (demo + fullstack) |
| P11 | Toggle mode end-to-end: UI editor (min 2 states, overrides) ↔ runner cycle `(old + 1) % len` | toggle tests + 4 E2E specs |
| P12 | `PUT /device/{id}/config/{config_id}` is exactly what the runner consumes via `GET /device/{id}/config` | `test_assigned_config_drives_button_render`, fullstack E2E |
| P13 | Animation pause: `pause`/`play`/`toggle-animation` (bare + dict), source-keyed shared pause, `animation {paused, frameIndex}` block, no repaint on animation-control presses | runner pause tests |
| P14 | Command `mode` attached/detached + crash-safe executor (`execute()` never raises) | `tests/test_agent.py`, detached roundtrip E2E |
| P15 | `switch-config` action swaps the active config at press time (bare + dict forms; failure keeps current) | runner switch tests, E2E picker + roundtrip |
| P16 | Config `triggers` blob + unconditional 5 s TriggerWatcher + crash-safe macOS probes + apply-once | `tests/test_triggers.py` (35), triggers E2E |
| P17 | Text completion: CLI shell completion enabled; UI `CommandInput` (static binaries + history + flags + inline `{{` completion) | `tests/test_cli.py`, completion E2E specs |
| P18 | Multi-step sequences: shared dispatch, continue-on-error default, `stopOnError`, per-step `delayMs` (cap 60000), depth cap 4, detached-counts-as-success | `tests/test_agent.py` sequence suite, E2E roundtrips |

The full table with every test name and E2E reference lives in
**[docs/parity.md](../../parity.md)** — read that for the fine print; this
page will not repeat it.

## How the contract is used

- **New feature ⇒ new row.** A feature isn't done until both sides agree
  and a test pins the agreement.
- **Backend-only surface is listed explicitly** (agent wire protocol,
  runner-facing endpoints) so nobody "adds a UI" or "removes an endpoint"
  by accident — see the "Backend-only surface" section of
  [docs/parity.md](../../parity.md).
- **Quirks are documented, not "fixed"**: human-name device types, whole-row
  PUT replace, snake_case agents, `DELETE /config` returning the row — all
  pinned in the "Backend quirks the frontend tolerates" section.

## Demo-mode parity

`frontend/src/lib/demo-api.ts` mirrors the REST surface and its *semantics*
(server-generated ids, whole-row replace, unknown ids throw, no phantom
`createdAt`/`updatedAt`) — the demo E2E specs save+reload through the mock
exactly like the fullstack specs do through the real API. The mock is part
of the contract, not a toy.

## Related

- [Explanation: testing philosophy](../explanation/testing-philosophy.md) —
  how the contract drives the builder→critic→judge loop
- [How-to: run the test suites](../how-to/run-tests.md)