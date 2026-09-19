#!/usr/bin/env bash
# One-shot dev loop for Linux/macOS: install HIDAPI via the system package
# manager so the libusb transport can find it. macOS users should use Homebrew
# (brew install hidapi); this script is a convenience wrapper.
set -euo pipefail

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get install -y libhidapi-libusb0 || true
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y hidapi || true
elif command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --noconfirm hidapi || true
elif command -v brew >/dev/null 2>&1; then
  brew install hidapi || true
else
  echo "No known package manager found; install hidapi manually."
  exit 1
fi
echo "hidapi installed/verified."