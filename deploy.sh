#!/usr/bin/env bash
# Safe CircuitPython deployment and configuration reconciliation.
# Example: CIRCUITPY=/Volumes/CIRCUITPY ./deploy.sh --dry-run
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "${PYTHON:-python3}" "$ROOT/tools/deploy.py" "$@"
