from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from runtime.btc_consensus import build_candidate, compact_target, dsha256


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class LineageReceipt:
    stage: str
    status: str
    object_digest: str
    observed_at: str
    evidence: dict[str, Any]
    previous_receipt_digest: str | None = None

    def digest(self) -> str:
        return canonical_digest({
            "stage": self.stage,
            "status": self.status,
            "object_digest": self.object_digest,
            "observed_at": self.observed_at,
            "evidence": self.evidence,
            "previous_receipt_digest": self.previous_receipt_digest,
        })


@dataclass
class MiningRun:
    run_id: str
    template: dict[str, Any]
    template_digest: str
    previousblockhash: str
    receipts: list[LineageReceipt] = field(default_factory=list)

    @classmethod
    def from_template(cls, template: dict[str, Any]) -> "MiningRun":
        required = ("height", "previousblockhash", "version", "bits", "coinbasevalue")
        missing = [key for key in required if key not in template]
        if missing:
            raise ValueError(f"template missing required fields: {', '.join(missing)}")
        template_digest = canonical_digest(template)
        run_id = canonical_digest({
            "template_digest": template_digest,
            "previousblockhash": str(template["previousblockhash"]).lower(),
            "height": int(template["height"]),
        })
        run = cls(run_id, template, template_digest, str(template["previousblockhash"]).lower())
        run.record("TEMPLATE_BOUND", "PASS", template_digest, {
            "height": int(template["height"]),
            "previousblockhash": run.previousblockhash,
            "bits": str(template["bits"]).lower(),
            "workid": template.get("workid"),
        })
        return run

    def record(self, stage: str, status: str, object_digest: str, evidence: dict[str, Any]) -> LineageReceipt:
        previous = self.receipts[-1].digest() if self.receipts else None
        receipt = LineageReceipt(stage, status, object_digest, utc_now(), evidence, previous)
        self.receipts.append(receipt)
        return receipt

    def build(self, payout_address: str, extranonce: bytes, nonce: int, ntime: int | None = None) -> dict[str, Any]:
        candidate = build_candidate(self.template, payout_address, extranonce, nonce, ntime)
        candidate["run_id"] = self.run_id
        candidate["template_digest"] = self.template_digest
        candidate["lineage"] = {
            "previousblockhash": self.previousblockhash,
            "height": int(self.template["height"]),
            "workid": self.template.get("workid"),
        }
        self.verify_candidate(candidate)
        return candidate

    def verify_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if candidate.get("run_id") != self.run_id:
            raise ValueError("candidate run_id does not match MiningRun")
        if candidate.get("template_digest") != self.template_digest:
            raise ValueError("candidate template_digest does not match MiningRun")
        block = bytes.fromhex(str(candidate["block_hex"]))
        header = bytes.fromhex(str(candidate["header_hex"]))
        if len(header) != 80 or block[:80] != header:
            raise ValueError("candidate block does not preserve exact header bytes")
        digest = dsha256(header)
        block_hash = digest[::-1].hex()
        if block_hash != str(candidate["block_hash"]).lower():
            raise ValueError("candidate block_hash does not reconstruct from header")
        previousblockhash = header[4:36][::-1].hex()
        if previousblockhash != self.previousblockhash:
            raise ValueError("candidate previousblockhash does not match bound template")
        bits = int.from_bytes(header[72:76], "little")
        if f"{bits:08x}" != str(self.template["bits"]).lower():
            raise ValueError("candidate bits do not match bound template")
        target = compact_target(bits)
        hash_integer = int.from_bytes(digest, "little")
        target_valid = hash_integer <= target
        verification = {
            "run_id": self.run_id,
            "template_digest": self.template_digest,
            "header_digest": hashlib.sha256(header).hexdigest(),
            "block_digest": hashlib.sha256(block).hexdigest(),
            "block_hash": block_hash,
            "previousblockhash": previousblockhash,
            "bits": f"{bits:08x}",
            "target": target,
            "hash_integer": hash_integer,
            "target_valid": target_valid,
        }
        self.record("CANDIDATE_RECONSTRUCTED", "PASS", verification["block_digest"], verification)
        return verification

    def submission_gate(self, candidate: dict[str, Any], current_tip: str) -> dict[str, Any]:
        verification = self.verify_candidate(candidate)
        fresh = str(current_tip).lower() == self.previousblockhash
        allowed = bool(fresh and verification["target_valid"])
        result = {
            "run_id": self.run_id,
            "fresh_tip": fresh,
            "target_valid": verification["target_valid"],
            "submission_ready": allowed,
            "reason": "ready" if allowed else ("stale_tip" if not fresh else "network_target_not_met"),
        }
        self.record("SUBMISSION_GATE", "PASS" if allowed else "NOT_TRIGGERED", canonical_digest(result), result)
        return result

    def evidence(self) -> list[dict[str, Any]]:
        return [{
            "stage": r.stage,
            "status": r.status,
            "object_digest": r.object_digest,
            "observed_at": r.observed_at,
            "evidence": r.evidence,
            "previous_receipt_digest": r.previous_receipt_digest,
            "receipt_digest": r.digest(),
        } for r in self.receipts]
