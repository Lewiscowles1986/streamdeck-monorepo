# PROVENANCE

This repository is a **port** of three separate projects into one standalone
monorepo. This file records where every part came from, so history is never
lost ("provenance"). All vendored/port content keeps its original license.

| Source repository | Upstream / fork | Ported commit | License | Ported into |
| ----------------- | --------------- | ------------- | ------- | ----------- |
| [python-elgato-streamdeck](https://github.com/Lewiscowles1986/python-elgato-streamdeck) (fork) | [abcminiuser/python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck) v0.10.0 | `47c97ad508609cfc7312df556fb82a263533bd81` (2025-12-04, `master`) — "Bump minimum Python version to 3.10." | MIT (C) Dean Camera | `streamdeck/core/**` |
| [streamdeck](https://github.com/Lewiscowles1986/streamdeck) (backend + runner experiments) | — | `078b8b23b43120e28580512dbd842a957bdf837d` (2025-12-09, `main`) — "refactor: default button image to data uri" | see source repo | `streamdeck/{app,db,models,runner}.py`, `streamdeck/assets/**` |
| [streamdeck-frontend](https://github.com/Lewiscowles1986/streamdeck-frontend) (Lovable/Vite React UI) | — | `bef572b7e36109600794abee9ca3aebedf8c47a1` (2025-12-07, `main`) — "feat: link to configuration from device when assigned" | see source repo | `frontend/**` |

## Port map (source → destination)

```
python-elgato-streamdeck@47c97ad  src/StreamDeck/**        → streamdeck/core/**
streamdeck@078b8b2                api/app.py               → streamdeck/app.py   (+ agents, JSONResponse fixes)
streamdeck@078b8b2                api/db.py                → streamdeck/db.py    (+ init_db)
streamdeck@078b8b2                api/models.py            → streamdeck/models.py (+ Agent, AgentAction)
streamdeck@078b8b2                read_config/main.py      → streamdeck/runner.py
streamdeck@078b8b2                basic/main.py            → (reference only; its behavior is covered by runner)
streamdeck@078b8b2                basic/Assets/*           → streamdeck/assets/**
streamdeck-frontend@bef572b       src/**, configs          → frontend/**
(new in this port)                demo mode                → frontend/src/lib/demo-api.ts, DemoBanner.tsx
(new in this port)                agent / nominate machine → streamdeck/agent.py, app.py agent endpoints
(new in this port)                CLI + uvx packaging      → streamdeck/cli.py, pyproject.toml
(new in this port)                E2E + integration suites → tests/**, e2e/**, playwright.config.ts
```

## Local changes to vendored code

`streamdeck/core/Transport/Dummy.py` (test transport only, not used with real
hardware):
- Fixed upstream bug: an `is_open` **attribute** shadowed the `is_open()`
  method, breaking every guarded operation.
- `read_feature(0x03, …)` (serial number report) now returns a deterministic
  synthetic serial (`DUMMY<vid><pid>`), so emulated decks have stable unique
  IDs for API flows and E2E.

## Machine-readable snapshot

See `.git-provenance.json` for the same data in JSON form.

## Updating the vendored fork

1. Fetch the fork repository, note the new commit.
2. Copy `src/StreamDeck/**` over `streamdeck/core/**`.
3. Re-apply the `Dummy.py` deltas above (kept minimal on purpose).
4. Update the tables above, `streamdeck/core/PROVENANCE.md` and
   `.git-provenance.json`.