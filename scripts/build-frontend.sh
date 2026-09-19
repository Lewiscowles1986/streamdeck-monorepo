#!/usr/bin/env bash
# Build the frontend twice: a demo build (dist-demo, offline-first) and the
# normal full-stack build (dist, points at the API). Run from repo root.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

if command -v bun >/dev/null 2>&1; then
  PM="bun"
  RUN="bun"
else
  PM="npm"
  RUN="npx"
fi

echo "==> Installing frontend dependencies ($PM)"
$PM install

echo "==> Building demo bundle (dist-demo, VITE_DEMO_MODE=1)"
VITE_DEMO_MODE=1 $RUN run build
rm -rf dist-demo
mv dist dist-demo

echo "==> Building full-stack bundle (dist)"
$RUN run build

echo "==> Done. Serve with: uvx . streamdeck demo  /  uvx . streamdeck ui"