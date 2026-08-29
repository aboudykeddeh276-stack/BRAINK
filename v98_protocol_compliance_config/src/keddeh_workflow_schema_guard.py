#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


@dataclass(frozen=True)
class WorkflowGuardReceipt:
    schema_id: str
    work_item_valid: bool
    branch_valid: bool
    pr_title_valid: bool
    commit_valid: bool
    labels_valid: bool
    errors: List[Dict[str, str]]
    receipt_path: str
    ledger_path: str
    outbox_manifest: str
    promotion_state: str
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


def append_ledger(path: Path, entry: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def normalize_slug(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:56].strip("-")


def regex_match(pattern: str, value: str) -> bool:
    return re.match(pattern, value or "") is not None


def validate_work_item(payload: Dict[str, Any], config: Dict[str, Any]) -> List[ValidationError]:
    errors: List[ValidationError] = []
    regex = config["regex"]

    if payload.get("level") not in config["levels"]:
        errors.append(ValidationError("level", "must use canonical workflow level"))
    if payload.get("status") not in config["statuses"]:
        errors.append(ValidationError("status", "must use canonical lifecycle vocabulary"))
    title = str(payload.get("title", ""))
    if not title or len(title) > 120:
        errors.append(ValidationError("title", "must be present and <= 120 characters"))
    if any(token in title.lower() for token in ("[p0]", "[p1]", "blocked", "wf-st-", "wf-pr-")):
        errors.append(ValidationError("title", "must not encode mutable metadata"))
    if not regex_match(regex["portable_slug"], str(payload.get("slug", ""))):
        errors.append(ValidationError("slug", "must match portable slug grammar"))
    for label in payload.get("labels", []):
        if not regex_match(regex["label"], str(label)):
            errors.append(ValidationError("labels", f"invalid structured label: {label}"))
    for field_name in ("created_ts", "updated_ts", "target_ts"):
        value = payload.get(field_name)
        if value and not regex_match(regex["rfc3339"], str(value)):
            errors.append(ValidationError(field_name, "must use RFC3339 timestamp"))
    release = payload.get("target_release_version")
    if release and not regex_match(regex["semver"], str(release)):
        errors.append(ValidationError("target_release_version", "must use SemVer"))
    return errors


def validate_branch(branch: str, config: Dict[str, Any]) -> bool:
    return regex_match(config["regex"]["branch"], branch)


def validate_pr_title(title: str, config: Dict[str, Any]) -> bool:
    return regex_match(config["regex"]["pr_title"], title)


def validate_commit_message(message: str, config: Dict[str, Any]) -> bool:
    return regex_match(config["regex"]["commit_message"], message)


def validate_labels(labels: List[str], config: Dict[str, Any]) -> bool:
    return all(regex_match(config["regex"]["label"], label) for label in labels)


def default_payload() -> Dict[str, Any]:
    return {
        "native_key": "KEX-98",
        "level": "task",
        "title": "Add workflow schema guard to service spine",
        "slug": "workflow-schema-guard-service-spine",
        "status": "in-review",
        "priority": "p1",
        "risk": "r1",
        "owner_team": "platform",
        "labels": ["wf-lvl-task", "wf-st-in-review", "wf-pr-p1", "wf-own-platform"],
        "created_ts": "2026-08-03T00:00:00Z",
        "updated_ts": "2026-08-03T00:00:00Z",
        "target_release_version": "0.98.0",
    }


def run_guard(root: Path, payload_path: Optional[Path] = None, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    config = read_json(root / "config" / "workflow_schema.json")
    payload = read_json(payload_path) if payload_path else default_payload()
    started = time.time()

    errors = validate_work_item(payload, config)
    branch = "feature/KEX-98/workflow-schema-guard-service-spine"
    pr_title = "KEX-98 Add workflow schema guard to service spine"
    commit = "feat(workflow): KEX-98 add schema guard receipts"
    labels = payload.get("labels", [])

    branch_valid = validate_branch(branch, config)
    pr_title_valid = validate_pr_title(pr_title, config)
    commit_valid = validate_commit_message(commit, config)
    labels_valid = validate_labels(labels, config)
    all_valid = not errors and branch_valid and pr_title_valid and commit_valid and labels_valid

    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / "runtime_volume" / "outbox" / "workflow_schema"
    outbox_dir.mkdir(parents=True, exist_ok=True)

    matrix_rows = [
        {"check": "work_item", "valid": str(not errors).lower(), "detail": ";".join(f"{e.field}:{e.message}" for e in errors) or "ok"},
        {"check": "branch", "valid": str(branch_valid).lower(), "detail": branch},
        {"check": "pr_title", "valid": str(pr_title_valid).lower(), "detail": pr_title},
        {"check": "commit", "valid": str(commit_valid).lower(), "detail": commit},
        {"check": "labels", "valid": str(labels_valid).lower(), "detail": ";".join(labels)},
    ]
    write_csv(exports_dir / "workflow_schema_guard_matrix.csv", matrix_rows)

    pre_receipt = {
        "schema_id": config["schema_id"],
        "payload": payload,
        "branch": branch,
        "pr_title": pr_title,
        "commit": commit,
        "errors": [asdict(error) for error in errors],
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    receipt_path = evidence_dir / "workflow_schema_guard_receipt.json"
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"
    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_WORKFLOW_SCHEMA_GUARD",
        "payload_path": str(receipt_path),
        "receipt_path": str(ledger),
        "next_target": "github_rulesets_hooks_and_project_fields",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if all_valid else "FAILED_CLOSED",
        "created_at": started,
    }
    write_json(outbox_path, handoff)
    ledger_entry = {"type": "workflow_schema_guard", "entry_hash": receipt_hash, "payload": pre_receipt, "outbox_manifest": str(outbox_path)}
    append_ledger(ledger, ledger_entry)
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger))

    receipt = WorkflowGuardReceipt(
        schema_id=config["schema_id"],
        work_item_valid=not errors,
        branch_valid=branch_valid,
        pr_title_valid=pr_title_valid,
        commit_valid=commit_valid,
        labels_valid=labels_valid,
        errors=[asdict(error) for error in errors],
        receipt_path=str(receipt_path),
        ledger_path=str(ledger),
        outbox_manifest=str(outbox_path),
        promotion_state="LOCAL_PASS" if all_valid and ledger_readback else "LOCAL_FAIL",
        timestamp=started,
    )
    final = {
        "receipt": asdict(receipt),
        "ledger_readback": ledger_readback,
        "hash_used_as_functional_proof": False,
        "telemetry_used_as_execution_proof": False,
        "schema_enforcement_is_delivery_proof": False,
    }
    if emit_receipt:
        write_json(receipt_path, final)
    return final


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--payload", default=None)
    parser.add_argument("--normalize", default=None)
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    if args.normalize is not None:
        print(normalize_slug(args.normalize))
        return 0
    result = run_guard(Path(args.root), Path(args.payload) if args.payload else None, emit_receipt=args.emit_receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["receipt"]["promotion_state"] == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
