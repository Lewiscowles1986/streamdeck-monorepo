# Explanation

Understanding-oriented pages: why the system is the way it is. Read these
when a how-to or reference page leaves you asking "*why*".

- **[Architecture overview](architecture.md)** — who talks to what: the
  FastAPI app, the SQLModel database, the device runner, and the agent
  protocol; the queue→poll→result lifecycle; why the dialect is camelCase
  except agents; why configs and actions are schema-less JSON columns.
- **[The animation pipeline](animation-pipeline.md)** — data URI → decode
  once → `itertools.cycle` → 30 fps tick, and the shared pause/play state
  machine.
- **[Template variables](template-variables.md)** — where `{{...}}` expands,
  what context it gets, and why expansion recurses.
- **[Crash-safety design](crash-safety.md)** — the catch-all layers: the
  callback wrapper, the executor that never raises, the contained trigger
  watcher, and `TransportError` isolation.
- **[Testing philosophy](testing-philosophy.md)** — the parity contract as
  tests, red-green TDD, mutation verification, and the builder→critic→judge
  round structure.
- **[Vendored-core provenance](provenance.md)** — where every part came from
  and the rule that keeps port history honest ([PROVENANCE.md](../../../PROVENANCE.md)).