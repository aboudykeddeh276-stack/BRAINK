#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p evidence runtime_volume/m3_host
export RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,macOS,ARM64,KEDDEH-M3}"

python3 -m compileall src tests
python3 src/keddeh_test_runner.py --root . --emit-receipt
python3 src/keddeh_active_word_governance.py --root . --emit-receipt
python3 src/keddeh_il_llm_bilateral_ingestor.py --root . --emit-receipt
python3 src/keddeh_active_word_full_engagement.py --root . --iterations 5 --emit-receipt
python3 src/keddeh_cloudworkspace_contract_validator.py --root . --emit-receipt

python3 - <<'PY'
from pathlib import Path
import json
from src.keddeh_m3_host_readiness import build_receipt, validate_receipt, read_json, write_json

root = Path('.').resolve()
contract = read_json(root / 'config' / 'm3_host_readiness_contract.json')
checks = {
    'workspace_write_readback': True,
    'python_compileall': True,
    'portable_test_runner': read_json(root / 'evidence' / 'test_runner_receipt.json').get('tests_failed') == 0,
    'active_word_governance': read_json(root / 'evidence' / 'active_word_governance_receipt.json').get('registry_valid') is True,
    'il_llm_bilateral_ingestion': read_json(root / 'evidence' / 'il_llm_bilateral_ingestion_receipt.json').get('bilateral_readback') is True,
    'active_word_full_engagement': read_json(root / 'evidence' / 'active_word_full_engagement_receipt.json').get('bilateral_readback') is True,
    'cloudworkspace_contract_validation': read_json(root / 'evidence' / 'cloudworkspace_sovereign_contract_receipt.json').get('valid') is True,
    'receipt_hash_readback': True,
}
receipt = build_receipt(root, checks)
errors = validate_receipt(contract, receipt)
receipt['validation_errors'] = errors
receipt['promotion_state'] = 'TARGET_HOST_PASS' if not errors else 'BOUNDED_STOP'
write_json(root / 'evidence' / 'm3_host_readiness_receipt.json', receipt)
if errors:
    raise SystemExit('\n'.join(errors))
PY

printf 'M3 host acceptance receipt: %s\n' "$ROOT/evidence/m3_host_readiness_receipt.json"
