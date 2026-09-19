#!/usr/bin/env bash
# Hardware smoke test — run when a real Stream Deck is attached.
# Exercises: enumeration, metadata, image render + display, brightness.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  uv venv --python 3.12
  uv pip install -e '.[dev]'
fi

echo "==> Attached decks:"
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m streamdeck.cli list || true

echo "==> Hardware smoke tests (opt-in marker)"
STREAMDECK_TRANSPORT=libusb .venv/bin/python -m pytest -m hardware tests/test_hardware.py -v

echo "==> Done. If all green, your deck is working through the full stack."