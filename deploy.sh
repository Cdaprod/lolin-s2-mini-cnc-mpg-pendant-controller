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
while IFS= read -r source; do
  destination="$CIRCUITPY/$source"
  mkdir -p "$(dirname "$destination")"
  cp "$source" "$destination"
done < <(find src -type f -name '*.py' -print)

# Any third-party CircuitPython libraries are vendored under lib/ and copied
# verbatim so imports resolve from the CIRCUITPY filesystem.
mkdir -p "$CIRCUITPY/lib"
cp -R lib/. "$CIRCUITPY/lib/"

if [[ ! -f "$CIRCUITPY/settings.toml" ]]; then
  cp settings.toml.example "$CIRCUITPY/settings.toml"
  echo
  echo "Created settings.toml from example."
  echo "Edit Wi-Fi password before rebooting."
else
  echo "Existing settings.toml preserved."
fi

echo "Done."
