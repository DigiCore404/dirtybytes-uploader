#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -x .venv/bin/python ]] || { echo 'Run bash install.sh first.' >&2; exit 1; }
if [[ -d tools/archive/bin ]]; then export PATH="$PWD/tools/archive/bin:$PATH"; fi
if [[ -d tools/browser && -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ]]; then export PLAYWRIGHT_BROWSERS_PATH="$PWD/tools/browser"; fi
exec .venv/bin/python uploader.py "$@"
