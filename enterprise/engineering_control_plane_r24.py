from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping, Iterable
import hashlib, json, os, time


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class EngineeringDecision:
    decision_id: str
    title: str
    context: str
    decision: str
    consequences: tuple[str, ...]
    supersedes: str | None = None

    @property
    def decision_root(self) -> str:
        return root(asdict(self))


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    class_id: str
    subject: str
    status: str
    mechanism_ref: str
    test_ref: str
    evidence_root: str


class AppendOnlyLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        if self.path.exists():
            for line in self.path.read_text("utf-8").splitlines():
                if line.strip():
                    self.records.append(json.loads(line))
        self._verify_chain()

    def _verify_chain(self) -> None:
        predecessor = None
        for record in self.records:
            body = {k: v for k, v in record.items() if k != "record_root"}
            if body.get("predecessor_root") != predecessor:
                raise RuntimeError("LEDGER_CHAIN_BROKEN")
            if root(body) != record.get("record_root"):
                raise RuntimeError("LEDGER_HASH_MISMATCH")
            predecessor = record["record_root"]

    def append(self, event_type: str, subject: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        predecessor = self.records[-1]["record_root"] if self.records else None
        body = {
            "schema": "braink.r24.ledger-record/v1",
            "event_type": event_type,
            "subject": subject,
            "payload": dict(payload),
            "predecessor_root": predecessor,
            "produced_ns": time.time_ns(),
        }
        record = {**body, "record_root": root(body)}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.records.append(record)
        return record

    @property
    def ledger_root(self) -> str | None:
        return self.records[-1]["record_root"] if self.records else None


class ReconciliationEngine:
    VALID = {"IMPLEMENTED", "EXECUTED", "VERIFIED", "FAILED", "UNVERIFIED", "STALE", "REJECTED"}

    def reconcile(self, declared: Mapping[str, str], observed: Mapping[str, str]) -> dict[str, Any]:
        keys = sorted(set(declared) | set(observed))
        deltas = []
        for key in keys:
            d = declared.get(key, "ABSENT")
            o = observed.get(key, "ABSENT")
            if d != o:
                deltas.append({"subject": key, "declared": d, "observed": o, "classification": self._classify(d, o)})
        body = {"deltas": deltas, "delta_count": len(deltas)}
        body["reconciliation_root"] = root(body)
        return body

    def _classify(self, declared: str, observed: str) -> str:
        if declared == "VERIFIED" and observed not in {"VERIFIED", "EXECUTED"}:
            return "OVERCLAIM"
        if observed in {"FAILED", "REJECTED"}:
            return "FAULT"
        if declared == "ABSENT" and observed != "ABSENT":
            return "UNDOCUMENTED_RESIDENT_CAPABILITY"
        return "STATE_DRIFT"


class ReleaseManifestBuilder:
    def build(self, release_id: str, artifacts: Iterable[Mapping[str, Any]], decisions: Iterable[EngineeringDecision], evidence: Iterable[Evidence], predecessor_release_root: str | None = None) -> dict[str, Any]:
        artifacts = [dict(a) for a in artifacts]
        decisions = [asdict(d) | {"decision_root": d.decision_root} for d in decisions]
        evidence = [asdict(e) for e in evidence]
        body = {
            "schema": "braink.r24.release-manifest/v1",
            "release_id": release_id,
            "artifacts": sorted(artifacts, key=lambda x: x["path"]),
            "engineering_decisions": decisions,
            "evidence": evidence,
            "predecessor_release_root": predecessor_release_root,
        }
        body["release_root"] = root(body)
        return body


class PromotionGate:
    REQUIRED_QUALITY = {"functional_suitability", "performance_efficiency", "compatibility", "interaction_capability", "reliability", "security", "maintainability", "flexibility", "safety"}
    REQUIRED_SECURITY = {"prepare_organization", "protect_software", "produce_well_secured_software", "respond_to_vulnerabilities"}

    def evaluate(self, release: Mapping[str, Any], quality: Mapping[str, bool], security: Mapping[str, bool], tests: Mapping[str, bool], rollback_ready: bool, independent_verifier: bool) -> dict[str, Any]:
        quality_missing = sorted(k for k in self.REQUIRED_QUALITY if not quality.get(k, False))
        security_missing = sorted(k for k in self.REQUIRED_SECURITY if not security.get(k, False))
        failed_tests = sorted(k for k, passed in tests.items() if not passed)
        criteria = {
            "release_root_present": bool(release.get("release_root")),
            "quality_complete": not quality_missing,
            "security_complete": not security_missing,
            "tests_pass": not failed_tests,
            "rollback_ready": rollback_ready,
            "independent_verifier": independent_verifier,
        }
        status = "PROMOTED" if all(criteria.values()) else "REJECTED"
        body = {
            "status": status,
            "criteria": criteria,
            "quality_missing": quality_missing,
            "security_missing": security_missing,
            "failed_tests": failed_tests,
            "release_root": release.get("release_root"),
        }
        body["promotion_root"] = root(body)
        return body


class MarketReadinessEvaluator:
    def evaluate(self, technical: Mapping[str, float], operational: Mapping[str, float], commercial: Mapping[str, float], evidence_coverage: float) -> dict[str, Any]:
        def avg(values: Mapping[str, float]) -> float:
            return sum(values.values()) / max(1, len(values))
        scores = {
            "technical": round(avg(technical), 6),
            "operational": round(avg(operational), 6),
            "commercial": round(avg(commercial), 6),
            "evidence_coverage": round(evidence_coverage, 6),
        }
        weighted = round(scores["technical"] * 0.35 + scores["operational"] * 0.30 + scores["commercial"] * 0.20 + scores["evidence_coverage"] * 0.15, 6)
        if weighted >= 0.85 and min(scores.values()) >= 0.70:
            classification = "MARKET_READY_CANDIDATE"
        elif weighted >= 0.65:
            classification = "PILOT_READY"
        else:
            classification = "ENGINEERING_ONLY"
        body = {"scores": scores, "weighted_score": weighted, "classification": classification}
        body["evaluation_root"] = root(body)
        return body
