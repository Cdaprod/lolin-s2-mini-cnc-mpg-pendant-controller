#!/usr/bin/env bash
set -euo pipefail

CIRCUITPY="${CIRCUITPY:-/Volumes/CIRCUITPY}"

if [[ ! -d "$CIRCUITPY" ]]; then
  echo "CIRCUITPY drive not found: $CIRCUITPY" >&2
  exit 1
fi

echo "Deploying firmware to: $CIRCUITPY"

cp code.py "$CIRCUITPY/code.py"
cp patterns.py "$CIRCUITPY/patterns.py"

mkdir -p "$CIRCUITPY/src"
cp src/*.py "$CIRCUITPY/src/"

if [[ ! -f "$CIRCUITPY/settings.toml" ]]; then
  cp settings.toml.example "$CIRCUITPY/settings.toml"
  echo
  echo "Created settings.toml from example."
  echo "Edit Wi-Fi password before rebooting."
else
  echo "Existing settings.toml preserved."
fi

echo "Done."
