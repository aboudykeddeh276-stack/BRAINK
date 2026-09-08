#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOCKET="${BRAINK_EXECUTION_SOCKET:-/run/braink/execution.sock}"
ENV_FILE="${BRAINK_EXECUTION_ENV_FILE:-/etc/braink/execution.env}"
STATE_DIR="${BRAINK_EXECUTION_STATE:-/var/lib/braink/resident-execution}"
WORK_ROOT="${BRAINK_ANTIGRAVITY_WORK_ROOT:-/var/lib/braink/antigravity}"

if [[ "$EUID" -ne 0 ]]; then echo ROOT_REQUIRED >&2; exit 20; fi

bash "$ROOT/deployment/install_braink_execution_fabric.sh" install
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export BRAINK_EXECUTION_SOCKET="$SOCKET"
export BRAINK_EXECUTION_STATE="$STATE_DIR"
export BRAINK_EXECUTION_SIGNER_STATE="$STATE_DIR"
export BRAINK_ANTIGRAVITY_WORK_ROOT="$WORK_ROOT"

WORK_ID="antigravity-deploy-$(date +%s)-$$"
RESULT="$(python3 /opt/braink/current/deployment/braink_execctl.py --socket "$SOCKET" dispatch antigravity-deploy RUN_ONCE --work-id "$WORK_ID" --actor-type DEPLOYMENT_AUTHORITY --actor-id owner-host-antigravity)"
READBACK="$(python3 /opt/braink/current/deployment/braink_execctl.py --socket "$SOCKET" readback "$WORK_ID")"
RECEIPT="$WORK_ROOT/BRAINK_ANTIGRAVITY_DEPLOYMENT_RECEIPT.json"

python3 - "$WORK_ID" "$RESULT" "$READBACK" "$RECEIPT" <<'PY'
import json, pathlib, sys
work_id, result_raw, readback_raw, receipt_path = sys.argv[1:]
result=json.loads(result_raw); readback=json.loads(readback_raw); p=pathlib.Path(receipt_path)
assert result.get('status')=='COMPLETED', result
assert len(result.get('proof',''))==64, result
assert readback.get('status')=='PASS', readback
assert readback['work']['state']=='COMPLETED', readback
assert [e['state'] for e in readback['events']]==['ADMITTED','EXECUTING','COMPLETED'], readback
assert p.is_file(), f'MISSING_DEPLOYMENT_RECEIPT:{p}'
receipt=json.loads(p.read_text())
assert receipt.get('overall') is True, receipt
assert receipt.get('status')=='DEPLOYED_ANTIGRAVITY_LAYER2_READBACK_PASS', receipt
print(json.dumps({
  'status':'BRAINK_ANTIGRAVITY_ACTIVATED',
  'work_id':work_id,
  'execution_proof_root':result['proof'],
  'deployment_status':receipt['status'],
  'candidate_dist_root':receipt.get('candidate_dist_root'),
  'build_readback_root':receipt.get('build_readback_root'),
  'domains':{k:v.get('status') for k,v in receipt.get('domains',{}).items()},
  'receipt':str(p),
},sort_keys=True))
PY
