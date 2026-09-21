# Reference

Information-oriented pages: dry, complete, accurate. Look things up; don't
read linearly.

- **[CLI reference](cli.md)** — every `streamdeck` command and option,
  including global shell-completion options.
- **[REST API reference](api.md)** — endpoints, wire dialects (camelCase vs
  snake_case), status codes, and the schema-less JSON columns.
- **[Config schema reference](config-schema.md)** — every key a config can
  carry: `ButtonConfig`, `idle`/`pressed`, `font`, `toggleStates`,
  `animation`, and all action types.
- **[Triggers block reference](triggers.md)** — the automatic-switching JSON
  and the evaluator's exact semantics.
- **[Parity rules P1–P18](parity.md)** — the frontend ↔ backend contract,
  one row per rule, linking to [docs/parity.md](../../parity.md) (the
  executable form: `tests/test_parity.py`).