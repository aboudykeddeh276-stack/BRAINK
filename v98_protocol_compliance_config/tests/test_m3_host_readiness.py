from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.keddeh_m3_host_readiness import build_receipt, read_json, validate_receipt


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_valid_receipt_passes_with_required_labels_and_checks(monkeypatch) -> None:
    root = _root()
    monkeypatch.setenv('RUNNER_LABELS', 'self-hosted,macOS,ARM64,KEDDEH-M3')
    monkeypatch.setenv('GITHUB_SHA', 'a' * 40)
    checks = {name: True for name in read_json(root / 'config' / 'm3_host_readiness_contract.json')['requiredExecutableChecks']}
    receipt = build_receipt(root, checks)
    receipt['host_facts']['architecture'] = 'arm64'
    receipt['host_facts']['free_disk_bytes'] = 10 * 1024 * 1024 * 1024
    receipt['host_facts']['logical_cpu_count'] = 8
    body = {key: value for key, value in receipt.items() if key != 'receipt_hash'}
    import hashlib
    receipt['receipt_hash'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    contract = read_json(root / 'config' / 'm3_host_readiness_contract.json')
    assert validate_receipt(contract, receipt) == []


def test_missing_runner_labels_is_bounded_host_failure(monkeypatch) -> None:
    root = _root()
    monkeypatch.setenv('RUNNER_LABELS', 'self-hosted,macOS')
    checks = {name: True for name in read_json(root / 'config' / 'm3_host_readiness_contract.json')['requiredExecutableChecks']}
    receipt = build_receipt(root, checks)
    receipt['host_facts']['architecture'] = 'arm64'
    receipt['host_facts']['free_disk_bytes'] = 10 * 1024 * 1024 * 1024
    receipt['host_facts']['logical_cpu_count'] = 8
    body = {key: value for key, value in receipt.items() if key != 'receipt_hash'}
    import hashlib
    receipt['receipt_hash'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    errors = validate_receipt(read_json(root / 'config' / 'm3_host_readiness_contract.json'), receipt)
    assert 'runner_labels_incomplete' in errors


def test_failed_check_does_not_invalidate_unaffected_domains(monkeypatch) -> None:
    root = _root()
    monkeypatch.setenv('RUNNER_LABELS', 'self-hosted,macOS,ARM64,KEDDEH-M3')
    required = read_json(root / 'config' / 'm3_host_readiness_contract.json')['requiredExecutableChecks']
    checks = {name: True for name in required}
    checks['cloudworkspace_contract_validation'] = False
    receipt = build_receipt(root, checks)
    assert receipt['promotion_state'] == 'BOUNDED_STOP'
    assert receipt['global_stop'] is False
