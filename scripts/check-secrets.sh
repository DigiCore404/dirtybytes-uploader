#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
work=$(mktemp -d "${TMPDIR:-/tmp}/dirtybytes-secret-check.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
python3 - "$work/gitleaks.tar.gz" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve('https://github.com/gitleaks/gitleaks/releases/download/v8.30.0/gitleaks_8.30.0_linux_x64.tar.gz',sys.argv[1])
PY
printf '%s  %s\n' 79a3ab579b53f71efd634f3aaf7e04a0fa0cf206b7ed434638d1547a2470a66e "$work/gitleaks.tar.gz" | sha256sum --check --strict
tar -xzf "$work/gitleaks.tar.gz" -C "$work" gitleaks
# Verify the scanner detects a synthetic canary before trusting a clean result.
mkdir "$work/canary"
python3 - "$work/canary/check.txt" <<'PY'
import secrets,sys
from pathlib import Path
Path(sys.argv[1]).write_text('github_token = "'+''.join(['gh','p_'])+secrets.token_hex(18)+'"\n')
PY
set +e
"$work/gitleaks" dir --no-banner --redact "$work/canary" >/dev/null 2>&1
status=$?
set -e
[[ $status -eq 1 ]] || { echo 'Secret scanner self-test failed; publication blocked.' >&2; exit 1; }
"$work/gitleaks" dir --no-banner --redact "$root"
