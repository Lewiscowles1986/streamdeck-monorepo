# Vendored-core provenance rule

How this repository relates to its upstream, and the rule that keeps port
history honest.

## The short version

Code in `streamdeck/core/` is **vendored**: it comes from an upstream
project ([`abcminiuser/python-elgato-streamdeck`](https://github.com/abcminiuser/python-elgato-streamdeck),
v0.10.0, MIT, © Dean Camera) via our fork. When we change vendored files,
the delta must be **documented** — where it came from, what changed, and
why — in [PROVENANCE.md](../../../PROVENANCE.md). History is never silently
rewritten.

## What's vendored, and why

| Path | What | Why vendored |
| --- | --- | --- |
| `streamdeck/core/` | HID control of Elgato Stream Decks (fork of `python-elgato-streamdeck` @ `47c97ad`) | The repo consumes it as a stable embedded core, not a moving dependency; a vendored copy pins behavior and keeps the stack zero-config (no package-install step, no version drift). |

The vendored fork's deltas are *deliberately minimal* and each is recorded
(see "Local changes to vendored code" in [PROVENANCE.md](../../../PROVENANCE.md)):
an `is_open` attribute/method shadowing fix in the Dummy transport, and a
deterministic synthetic serial (`DUMMY<vid><pid>`) so emulated decks have
stable unique ids for API flows and E2E. Anything beyond that shape belongs
in an upstream contribution, not a local patch — that's the provenance
rule's point: **history is honest or it's useless**.

## Where the rule is written

- [PROVENANCE.md](../../../PROVENANCE.md) — the file itself: what was ported,
  from which upstream commit, under which license, plus "Updating the
  vendored fork".
- [docs/dev.md](../../dev.md) — the toolchain context (uv, bun) the port
  lives in.
- [docs/roadmap.md](../../../docs/roadmap.md) — the decision trail that led here.

## The rule, in practice

1. **Vendored deltas are documented at the moment they're made** — file,
   reason, upstream link (or "local-only"), in the provenance log.
2. **Prefer upstream-first fixes**: if a bug is in vendored code, the fix
   should land upstream; the local patch is a bridge, documented as such.
3. **No silent deltas.** A vendored file that differs from upstream without
   a provenance entry is a bug in itself — the next reader inherits a lie.
4. **License hygiene is part of the delta**: vendored code keeps its
   original license headers and copyright; the port adds none.

## Source map (what's where)

| Source | Upstream | Ported commit | Into |
| --- | --- | --- | --- |
| `python-elgato-streamdeck` (fork) | upstream Elgato library | `47c97ad…` | `streamdeck/core/**` |
| `streamdeck` backend + runner experiments | — | `078b8b2…` | `streamdeck/{app,db,models,runner}.py` |
| `streamdeck-frontend` (Lovable/Vite UI) | — | `bef572b…` | `frontend/**` |

## Why this matters

A monorepo outlives its authors' memory. Provenance is the difference
between "why does this file say *that*?" being answerable and being
archaeology. The rule is small; keeping it is cheap; losing it is how
repos rot. If you change vendored behavior, the *test* that pins the
behavior and the *provenance entry* explaining it land in the same commit.