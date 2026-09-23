# Run the test suites

**Goal:** run everything the project uses to stay green — the Python
integration suite, the four Playwright E2E projects, the type check — and
use mutation verification when you change behavior.

## Prerequisites

Development setup ([docs/dev.md](../../dev.md) has the full story):

```sh
uv venv --python 3.12 && uv pip install -e '.[dev]'   # Python env
(cd frontend && bun install)                          # JS deps for E2E
scripts/build-frontend.sh                             # prebuilt UI bundles
```

The suites are **hardware-free** by default: the Python tests and the
full-stack E2E use the `dummy` transport (emulated decks, real library code
paths), and the demo E2E runs entirely in-browser.

## Python integration suite

```sh
.venv/bin/python -m pytest tests -q -m 'not hardware'
```

Expect **146 passed, 5 deselected** (the hardware smoke tests; opt in with
`-m hardware` against a real deck — prerequisites like macOS's
`brew install hidapi` are in [Test a real Stream Deck](real-hardware.md)).

| File | Covers |
| --- | --- |
| `tests/test_api.py` | REST surface, dialects, agent queue round-trip |
| `tests/test_agent.py` | executor: attached/detached, sequences, template expansion, never-raises |
| `tests/test_runner.py` | rendering, toggle machine, switch-config, apply/swap core |
| `tests/test_triggers.py` | evaluator matrix, probes, watcher lifecycle (35 tests) |
| `tests/test_hardening.py` | crash-safety regressions (corrupt images, write guards) |
| `tests/test_parity.py` | **the parity contract** — one test per P-rule |
| `tests/test_cli.py` | CLI surface incl. completion options + `--help` timing |
| `tests/test_device_core.py` | vendored core behavior through the dummy transport |

The shared fixtures (`tests/conftest.py`) wire each test to a fresh SQLite
file and force `STREAMDECK_TRANSPORT=dummy`.

## Playwright E2E (four projects)

From the repo root (the config lives there, not in `frontend/`):

```sh
bunx playwright test                                    # everything
bunx playwright test --project=demo-ui                  # UI only, demo build, :8080
bunx playwright test --project=parity-demo              # demo parity specs
bunx playwright test --project=full-stack               # real API + dummy deck (:8081/:8000)
bunx playwright test --project=parity-fullstack         # fullstack parity specs
```

Ports are owned by the projects: demo **8080**, full-stack UI **8081**, API
**8000** — don't share them between simultaneous runs (8090 is off-limits
too). Playwright starts its own web servers via `playwright.config.ts`
(`reuseExistingServer` locally), serving the **prebuilt** bundles.

> **Frontend changes need a rebuild** — the E2E suites serve `dist-demo/`
> and `dist/`, so source-only changes silently test stale code:
>
> ```sh
> scripts/build-frontend.sh
> ```

Current spec counts: `parity-demo` 29, `parity-fullstack` 11, `demo-ui` 5,
`full-stack` 3.

## Type check

```sh
cd frontend && bunx tsc --noEmit -p tsconfig.app.json
```

Expect a clean exit (this is the working invocation; there is no
`typecheck` script).

## Mutation verification

When a change is behavior-bearing, the project's practice (used every round;
see [testing philosophy](../explanation/testing-philosophy.md)) is to prove
your test has **teeth**: mutate the code so the behavior breaks, confirm the
test now fails, revert.

Examples from the project's history:

- Backend: flip the sequence `stopOnError` abort branch → the
  continue-on-error test must fail. Disable the depth cap → the cap test
  must fail.
- Frontend: disable the `Add step` handler, **rebuild bundles**
  (`scripts/build-frontend.sh` — otherwise the mutation is invisible), run
  the sequence E2E specs → all must fail. Revert + rebuild.

## Quick reference

```sh
# the two you'll run most:
.venv/bin/python -m pytest tests -q -m 'not hardware'   # 146 passed, 5 deselected
bunx playwright test                                     # 4 projects, 48 tests

# after frontend changes:
scripts/build-frontend.sh
(cd frontend && bunx tsc --noEmit -p tsconfig.app.json)
```

## Related

- [Explanation: testing philosophy](../explanation/testing-philosophy.md)
- [Parity rules P1–P18](../reference/parity.md) — what each E2E/pytest lock
- [docs/dev.md](../../dev.md) — environment setup and env vars