#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$HERE/run_btc_core_acceptance.zsh"
exec "$HERE/run_btc_core_acceptance.zsh"
