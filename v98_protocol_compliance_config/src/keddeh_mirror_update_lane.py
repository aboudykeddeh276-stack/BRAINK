#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class MirrorDocumentReceipt:
    path: str
    exists: bool
    byte_length: int
    sha256: str
    role: str


@dataclass(frozen=True)
class MirrorLaneReceipt:
    lane_id: str
    lane_state: str
    source_documents_checked: int
    mirror_documents_checked: int
    all_documents_present: bool
    manual_promotion_allowed: bool
    agent_self_promotion_allowed: bool
    ledger_readback: bool
    outbox_manifest: str
    promotion_state: str
    timestamp: float


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def document_receipt(root: Path, relative: str, role: str) -> MirrorDocumentReceipt:
    path = root / relative
    if not path.exists() or not path.is_file():
        return MirrorDocumentReceipt(relative, False, 0, "", role)
    data = path.read_bytes()
    return MirrorDocumentReceipt(relative, True, len(data), hashlib.sha256(data).hexdigest(), role)


def append_ledger(ledger: Path, entry: Dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def read_ledger(ledger: Path) -> List[Dict[str, Any]]:
    if not ledger.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


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


def run_mirror_lane(root: Path, emit_receipt: bool = False) -> Dict[str, Any]:
    root = root.expanduser().resolve()
    config = read_json(root / "config" / "mirror_update_lane.json")
    started = time.time()

    source_receipts = [document_receipt(root, rel, "source") for rel in config["source_documents"]]
    mirror_receipts = [document_receipt(root, rel, "mirror") for rel in config["required_mirror_documents"]]
    all_docs = source_receipts + mirror_receipts
    all_documents_present = all(receipt.exists for receipt in all_docs)

    promotion_rules = config["promotion_rules"]
    manual_promotion_allowed = bool(promotion_rules["manual_promotion_allowed"])
    agent_self_promotion_allowed = bool(promotion_rules["agent_self_promotion_allowed"])
    promotion_guard_passed = not manual_promotion_allowed and not agent_self_promotion_allowed

    evidence_dir = root / "evidence"
    exports_dir = root / "exports"
    ledger = root / "runtime_volume" / "proof_bundles.ledger"
    outbox_dir = root / config["outbox_target"]
    outbox_dir.mkdir(parents=True, exist_ok=True)

    matrix_rows = [asdict(receipt) for receipt in all_docs]
    write_csv(exports_dir / "mirror_update_lane_matrix.csv", matrix_rows)

    pre_receipt = {
        "lane_id": config["lane_id"],
        "source_documents": [asdict(r) for r in source_receipts],
        "mirror_documents": [asdict(r) for r in mirror_receipts],
        "all_documents_present": all_documents_present,
        "promotion_guard_passed": promotion_guard_passed,
        "timestamp": started,
    }
    receipt_hash = canonical_hash(pre_receipt)
    handoff = {
        "handoff_id": receipt_hash,
        "source": "KEDDEH_V98_MIRROR_UPDATE_LANE",
        "payload_path": str(evidence_dir / "mirror_update_lane_receipt.json"),
        "receipt_path": str(ledger),
        "next_target": "self_hosted_macos_arm64_runner_then_vfs_mirror_volume",
        "status": "READY_FOR_TARGET_HOST_EXECUTION" if all_documents_present and promotion_guard_passed else "FAILED_CLOSED",
        "created_at": started,
    }
    outbox_path = outbox_dir / f"{receipt_hash}.handoff.json"
    write_json(outbox_path, handoff)

    ledger_entry = {
        "type": "mirror_update_lane_receipt",
        "entry_hash": receipt_hash,
        "payload": pre_receipt,
        "outbox_manifest": str(outbox_path),
    }
    append_ledger(ledger, ledger_entry)
    ledger_readback = any(entry.get("entry_hash") == receipt_hash for entry in read_ledger(ledger))

    receipt = MirrorLaneReceipt(
        lane_id=config["lane_id"],
        lane_state=config["lane_state"],
        source_documents_checked=len(source_receipts),
        mirror_documents_checked=len(mirror_receipts),
        all_documents_present=all_documents_present,
        manual_promotion_allowed=manual_promotion_allowed,
        agent_self_promotion_allowed=agent_self_promotion_allowed,
        ledger_readback=ledger_readback,
        outbox_manifest=str(outbox_path),
        promotion_state="LOCAL_PASS" if all_documents_present and promotion_guard_passed and ledger_readback else "LOCAL_FAIL",
        timestamp=started,
    )

    final = {
        "receipt": asdict(receipt),
        "receipt_hash": receipt_hash,
        "hash_used_as_functional_proof": False,
        "certification_claimed": False,
        "remote_provider_claimed": False,
        "target_host_claimed": False,
    }
    if emit_receipt:
        write_json(evidence_dir / "mirror_update_lane_receipt.json", final)
    return final


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--emit-receipt", action="store_true")
    args = parser.parse_args(argv)
    final = run_mirror_lane(Path(args.root), emit_receipt=args.emit_receipt)
    print(json.dumps(final, indent=2, sort_keys=True))
    return 0 if final["receipt"]["promotion_state"] == "LOCAL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
