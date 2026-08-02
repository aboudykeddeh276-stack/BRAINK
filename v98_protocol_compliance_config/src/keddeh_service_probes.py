#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

LOCAL_PASS = "LOCAL_PASS"
LOCAL_FAIL = "LOCAL_FAIL"
TARGET_HOST_REQUIRED = "TARGET_HOST_REQUIRED"
PROVIDER_REQUIRED = "PROVIDER_REQUIRED"
EXTERNAL_CERTIFICATION_REQUIRED = "EXTERNAL_CERTIFICATION_REQUIRED"
UNSUPPORTED_IN_THIS_RUNTIME = "UNSUPPORTED_IN_THIS_RUNTIME"

ALLOWED_STATES = {
    LOCAL_PASS,
    LOCAL_FAIL,
    TARGET_HOST_REQUIRED,
    PROVIDER_REQUIRED,
    EXTERNAL_CERTIFICATION_REQUIRED,
    UNSUPPORTED_IN_THIS_RUNTIME,
}


@dataclass(frozen=True)
class ProbeCoreResult:
    classification: str
    executed: bool
    positive_test_passed: bool
    negative_test_passed: bool
    details: Dict[str, Any]


@dataclass(frozen=True)
class ServiceProbeReceipt:
    service_id: str
    owner_plane: str
    boundary: str
    classification: str
    executed: bool
    positive_test_passed: bool
    negative_test_passed: bool
    receipt_written: bool
    readback_passed: bool
    handoff_written: bool
    evidence_path: str
    outbox_manifest: str
    probe_name: str
    details: Dict[str, Any]
    timestamp: float


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def operational_files(root: Path) -> Iterable[Path]:
    roots = [root / "src", root / "config", root.parent / ".github" / "workflows"]
    for candidate_root in roots:
        if not candidate_root.exists():
            continue
        for path in candidate_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".json", ".yml", ".yaml", ".sh", ".command"}:
                yield path


def probe_agent_static_guard(root: Path) -> ProbeCoreResult:
    python_files = sorted((root / "src").glob("*.py"))
    parsed = 0
    errors: List[str] = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            parsed += 1
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"{path.name}:{exc}")
    negative_passed = False
    try:
        ast.parse("def broken(:\n    pass\n")
    except SyntaxError:
        negative_passed = True
    return ProbeCoreResult(
        classification=LOCAL_PASS if parsed > 0 and not errors and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=parsed > 0 and not errors,
        negative_test_passed=negative_passed,
        details={"python_files_parsed": parsed, "syntax_errors": errors},
    )


def detect_secret_markers(text: str) -> List[str]:
    patterns = {
        "pem_private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "github_pat": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        "openai_style_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    }
    return [name for name, pattern in patterns.items() if pattern.search(text)]


def probe_secret_boundary_guard(root: Path) -> ProbeCoreResult:
    findings: List[str] = []
    scanned = 0
    for path in operational_files(root):
        if path.name == Path(__file__).name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for marker in detect_secret_markers(text):
            findings.append(f"{path.relative_to(root.parent)}:{marker}")
    negative_sample = "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n"
    negative_passed = "pem_private_key" in detect_secret_markers(negative_sample)
    positive_passed = scanned > 0 and not findings
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"files_scanned": scanned, "findings": findings},
    )


def probe_safe_asset_receipt_pipeline(root: Path) -> ProbeCoreResult:
    target = root / "runtime_volume" / "service_probe_assets" / "asset.json"
    payload = {"asset_id": "probe-asset", "content": "non-secret", "created_at": time.time()}
    write_json(target, payload)
    positive_passed = read_json(target) == payload
    blocked_payload = {"content": "-----BEGIN " + "PRIVATE KEY-----"}
    negative_passed = bool(detect_secret_markers(blocked_payload["content"]))
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"asset_path": str(target), "secret_payload_rejected": negative_passed},
    )


def probe_vfs_volume_custody(root: Path) -> ProbeCoreResult:
    ledger = root / "runtime_volume" / "service_probe_custody.ledger"
    entry = {"probe": "vfs_volume_custody", "value": canonical_hash({"time": time.time()})}
    append_jsonl(ledger, entry)
    positive_passed = any(item == entry for item in read_jsonl(ledger))
    negative_passed = False
    with tempfile.TemporaryDirectory() as tmp:
        malformed = Path(tmp) / "malformed.ledger"
        malformed.write_text("{not-json}\n", encoding="utf-8")
        try:
            read_jsonl(malformed)
        except json.JSONDecodeError:
            negative_passed = True
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"ledger_path": str(ledger)},
    )


def probe_orphan_service_reconciler(root: Path) -> ProbeCoreResult:
    items = read_json(root / "config" / "orphan_registry.json")["orphaned_items"]
    allowed_states = {
        TARGET_HOST_REQUIRED,
        PROVIDER_REQUIRED,
        EXTERNAL_CERTIFICATION_REQUIRED,
        UNSUPPORTED_IN_THIS_RUNTIME,
        LOCAL_PASS,
        LOCAL_FAIL,
    }
    positive_passed = bool(items) and all(
        item.get("item_id") and item.get("assigned_service") and item.get("resolution_state") in allowed_states
        for item in items
    )
    invalid_item = {"item_id": "invalid", "assigned_service": "", "resolution_state": LOCAL_PASS}
    negative_passed = not (
        invalid_item.get("item_id")
        and invalid_item.get("assigned_service")
        and invalid_item.get("resolution_state") in allowed_states
    )
    state_counts: Dict[str, int] = {}
    for item in items:
        state = str(item.get("resolution_state"))
        state_counts[state] = state_counts.get(state, 0) + 1
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"items_reconciled": len(items), "resolution_state_counts": state_counts},
    )


def probe_mirror_update_lane(root: Path) -> ProbeCoreResult:
    from keddeh_mirror_update_lane import run_mirror_lane

    result = run_mirror_lane(root, emit_receipt=True)
    receipt = result["receipt"]
    positive_passed = (
        receipt["promotion_state"] == LOCAL_PASS
        and receipt["all_documents_present"] is True
        and receipt["ledger_readback"] is True
    )
    negative_passed = False
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run_mirror_lane(Path(tmp), emit_receipt=False)
        except FileNotFoundError:
            negative_passed = True
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"mirror_receipt": result},
    )


def probe_agent_registry_service(root: Path) -> ProbeCoreResult:
    from keddeh_agent_registry import run_agent_registry, validate_agent

    result = run_agent_registry(root, emit_receipt=True)
    positive_passed = result["receipt"]["promotion_state"] == LOCAL_PASS
    required = read_json(root / "config" / "agent_registry.json")["required_agent_fields"]
    invalid_agent = {"agent_id": "invalid"}
    negative_passed = validate_agent(invalid_agent, required) is False
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={"registry_receipt": result},
    )


def probe_agent_runtime_service(root: Path) -> ProbeCoreResult:
    from keddeh_agent_runtime_service import AgentRuntimeService

    runtime = AgentRuntimeService(root)
    positive = runtime.execute_work_order(
        "acceptance_harness_agent",
        "write_receipt",
        "agent_registry_service",
        {"probe": "agent_runtime_service"},
    )
    negative = runtime.execute_work_order(
        "codex_implementation_agent",
        "promote_local_pass",
        "agent_static_guard",
        {"probe": "unauthorized_promotion"},
    )
    positive_passed = positive.authorized and positive.executed and Path(positive.receipt_path).exists()
    negative_passed = not negative.authorized and not negative.executed
    return ProbeCoreResult(
        classification=LOCAL_PASS if positive_passed and negative_passed else LOCAL_FAIL,
        executed=True,
        positive_test_passed=positive_passed,
        negative_test_passed=negative_passed,
        details={
            "authorized_work_order": positive.work_order_id,
            "rejected_work_order": negative.work_order_id,
            "rejection_reason": negative.reason,
        },
    )


def gated_probe(classification: str, reason: str) -> ProbeCoreResult:
    return ProbeCoreResult(
        classification=classification,
        executed=False,
        positive_test_passed=False,
        negative_test_passed=False,
        details={"gate_reason": reason},
    )


def probe_zero_heap_compiler(root: Path) -> ProbeCoreResult:
    return gated_probe(
        UNSUPPORTED_IN_THIS_RUNTIME,
        "No qualified C/Rust no-heap compiler implementation or compile receipt exists in the portable runtime.",
    )


def probe_peer_ack_verifier(root: Path) -> ProbeCoreResult:
    return gated_probe(
        PROVIDER_REQUIRED,
        "A real provider-signed acknowledgement envelope is required; local schema or HMAC data is insufficient.",
    )


def probe_hyper_explicit_mesh_runtime(root: Path) -> ProbeCoreResult:
    return gated_probe(
        UNSUPPORTED_IN_THIS_RUNTIME,
        "No executable mesh scheduler/runtime probe is present in this package.",
    )


def probe_hemos_family_of_five_runtime(root: Path) -> ProbeCoreResult:
    return gated_probe(
        UNSUPPORTED_IN_THIS_RUNTIME,
        "No executable Family-of-Five consensus engine and adversarial consensus receipt are present.",
    )


def probe_indefinite_network_runtime(root: Path) -> ProbeCoreResult:
    return gated_probe(
        UNSUPPORTED_IN_THIS_RUNTIME,
        "No executable route-controller implementation or packet-path test is present in the portable package.",
    )


def probe_virtual_gpu_hci_dashboard(root: Path) -> ProbeCoreResult:
    return gated_probe(
        TARGET_HOST_REQUIRED,
        "Dashboard source exists, but framebuffer/render/readback execution requires the target workstation runtime.",
    )


PROBES: Dict[str, Callable[[Path], ProbeCoreResult]] = {
    "agent_static_guard": probe_agent_static_guard,
    "secret_boundary_guard": probe_secret_boundary_guard,
    "zero_heap_compiler": probe_zero_heap_compiler,
    "peer_ack_verifier": probe_peer_ack_verifier,
    "hyper_explicit_mesh_runtime": probe_hyper_explicit_mesh_runtime,
    "hemos_family_of_five_runtime": probe_hemos_family_of_five_runtime,
    "indefinite_network_runtime": probe_indefinite_network_runtime,
    "safe_asset_receipt_pipeline": probe_safe_asset_receipt_pipeline,
    "virtual_gpu_hci_dashboard": probe_virtual_gpu_hci_dashboard,
    "vfs_volume_custody": probe_vfs_volume_custody,
    "orphan_service_reconciler": probe_orphan_service_reconciler,
    "mirror_update_lane": probe_mirror_update_lane,
    "agent_registry_service": probe_agent_registry_service,
    "agent_runtime_service": probe_agent_runtime_service,
}


def execute_service_probe(root: Path, service: Dict[str, Any]) -> ServiceProbeReceipt:
    root = root.expanduser().resolve()
    service_id = service["service_id"]
    owner_plane = service["owner_plane"]
    boundary = service.get("boundary", "")
    probe = PROBES.get(service_id)
    started = time.time()
    if probe is None:
        core = gated_probe(
            UNSUPPORTED_IN_THIS_RUNTIME,
            "No executable probe is registered for this declared service.",
        )
        probe_name = "unregistered_probe"
    else:
        probe_name = probe.__name__
        try:
            core = probe(root)
        except Exception as exc:  # fail closed and preserve the exception as evidence
            core = ProbeCoreResult(
                classification=LOCAL_FAIL,
                executed=True,
                positive_test_passed=False,
                negative_test_passed=False,
                details={"exception_type": type(exc).__name__, "exception": str(exc)},
            )
    if core.classification not in ALLOWED_STATES:
        core = ProbeCoreResult(
            classification=LOCAL_FAIL,
            executed=True,
            positive_test_passed=False,
            negative_test_passed=False,
            details={"invalid_classification": core.classification},
        )

    evidence_path = root / "evidence" / "service_probes" / f"{service_id}.json"
    outbox_path = root / "runtime_volume" / "outbox" / "service_probes" / f"{service_id}.handoff.json"
    ledger_path = root / "runtime_volume" / "proof_bundles.ledger"

    pre_receipt = {
        "service_id": service_id,
        "owner_plane": owner_plane,
        "boundary": boundary,
        "classification": core.classification,
        "executed": core.executed,
        "positive_test_passed": core.positive_test_passed,
        "negative_test_passed": core.negative_test_passed,
        "probe_name": probe_name,
        "details": core.details,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    write_json(evidence_path, pre_receipt)
    receipt_written = evidence_path.exists() and read_json(evidence_path) == pre_receipt

    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_SERVICE_PROBE",
        "service_id": service_id,
        "classification": core.classification,
        "payload_path": str(evidence_path),
        "receipt_path": str(ledger_path),
        "next_target": (
            "self_hosted_macos_arm64_runner"
            if core.classification == TARGET_HOST_REQUIRED
            else "provider_receipt_gate"
            if core.classification == PROVIDER_REQUIRED
            else "implementation_backlog"
            if core.classification == UNSUPPORTED_IN_THIS_RUNTIME
            else "acceptance_summary"
        ),
        "status": "READY" if core.classification != LOCAL_FAIL else "FAILED_CLOSED",
        "created_at": started,
    }
    write_json(outbox_path, handoff)
    handoff_written = outbox_path.exists() and read_json(outbox_path) == handoff

    ledger_entry = {
        "type": "service_probe_receipt",
        "entry_hash": receipt_hash,
        "service_id": service_id,
        "classification": core.classification,
        "evidence_path": str(evidence_path),
        "outbox_manifest": str(outbox_path),
    }
    append_jsonl(ledger_path, ledger_entry)
    readback_passed = any(
        entry.get("entry_hash") == receipt_hash and entry.get("service_id") == service_id
        for entry in read_jsonl(ledger_path)
    )

    return ServiceProbeReceipt(
        service_id=service_id,
        owner_plane=owner_plane,
        boundary=boundary,
        classification=core.classification,
        executed=core.executed,
        positive_test_passed=core.positive_test_passed,
        negative_test_passed=core.negative_test_passed,
        receipt_written=receipt_written,
        readback_passed=readback_passed,
        handoff_written=handoff_written,
        evidence_path=str(evidence_path),
        outbox_manifest=str(outbox_path),
        probe_name=probe_name,
        details=core.details,
        timestamp=started,
    )


def run_all_service_probes(root: Path, services: List[Dict[str, Any]]) -> List[ServiceProbeReceipt]:
    return [execute_service_probe(root, service) for service in services]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    services = read_json(root / "config" / "service_protocols.json")["services"]
    receipts = run_all_service_probes(root, services)
    print(json.dumps([asdict(receipt) for receipt in receipts], indent=2, sort_keys=True))
    return 1 if any(receipt.classification == LOCAL_FAIL for receipt in receipts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
