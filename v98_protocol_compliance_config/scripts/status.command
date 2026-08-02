#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FINAL="$ROOT/evidence/FINAL_VERIFICATION.json"
LEDGER="$ROOT/runtime_volume/proof_bundles.ledger"
OUTBOX="$ROOT/runtime_volume/outbox"
echo "KEDDEH V98 STATUS"
echo "root=$ROOT"
if [[ -f "$FINAL" ]]; then
  python3 - <<'PY' "$FINAL"
import json, sys
p=sys.argv[1]
d=json.load(open(p, encoding='utf-8'))
print('status=' + d.get('status','UNKNOWN'))
print('services_connected=' + str(d.get('services_connected','UNKNOWN')))
print('services_passed=' + str(d.get('services_passed','UNKNOWN')))
print('target_gate_count=' + str(d.get('target_gate_count','UNKNOWN')))
print('ledger_readback=' + str(d.get('ledger_readback','UNKNOWN')))
PY
else
  echo "status=NO_FINAL_VERIFICATION"
fi
[[ -f "$LEDGER" ]] && echo "ledger_lines=$(wc -l < "$LEDGER")" || echo "ledger_lines=0"
[[ -d "$OUTBOX" ]] && echo "outbox_count=$(find "$OUTBOX" -name '*.handoff.json' | wc -l | tr -d ' ')" || echo "outbox_count=0"
