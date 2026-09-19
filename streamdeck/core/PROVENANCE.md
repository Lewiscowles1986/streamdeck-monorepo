# Provenance: `streamdeck/core`

`streamdeck/core` is a vendored fork of the
[python-elgato-streamdeck](https://github.com/abcminiuser/python-elgato-streamdeck)
library by Dean Camera (abcminiuser), used under the MIT license.

## Fork lineage

| Step | Repository | Commit | Notes |
| ---- | ---------- | ------ | ----- |
| Upstream | https://github.com/abcminiuser/python-elgato-streamdeck | tag `0.10.0` | MIT, (C) Dean Camera |
| Fork | https://github.com/Lewiscowles1986/python-elgato-streamdeck | `47c97ad508609cfc7312df556fb82a263533bd81` (2025-12-04, `master`) | "Bump minimum Python version to 3.10." |
| Vendored | this repository | import of `src/StreamDeck/**` at the fork commit above | re-homed to `streamdeck/core` |

## What changed when vendoring

- Only the package location changed (`src/StreamDeck` → `streamdeck/core`).
- An `__init__.py` re-export was added (`DeviceManager`, `ProbeError`).
- No functional code was modified. To update the fork, re-vendor from the fork
  repository and diff against this folder.