from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping, Iterable
import hashlib, json, os, time, re
import fcntl


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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
    """Single-host durable append-only ledger with stale-writer convergence.

    Writers serialize through an advisory lock file, reload and verify the canonical
    chain while holding the lock, then append from the current predecessor. This
    closes the stale in-memory predecessor race for cooperating processes on the
    same filesystem. It does not claim distributed or Byzantine consensus.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.records: list[dict[str, Any]] = []
        self._reload_and_verify()

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text("utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def _verify_records(self, records: list[dict[str, Any]]) -> None:
        predecessor = None
        for record in records:
            body = {k: v for k, v in record.items() if k != "record_root"}
            if body.get("predecessor_root") != predecessor:
                raise RuntimeError("LEDGER_CHAIN_BROKEN")
            if root(body) != record.get("record_root"):
                raise RuntimeError("LEDGER_HASH_MISMATCH")
            predecessor = record["record_root"]

    def _reload_and_verify(self) -> None:
        records = self._read_records()
        self._verify_records(records)
        self.records = records

    def _fsync_directory(self) -> None:
        fd = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def append(self, event_type: str, subject: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not event_type or not subject:
            raise ValueError("LEDGER_EVENT_AND_SUBJECT_REQUIRED")
        self.lock_path.touch(exist_ok=True)
        with self.lock_path.open("r+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                self._reload_and_verify()
                predecessor = self.records[-1]["record_root"] if self.records else None
                body = {
                    "schema": "braink.r24.ledger-record/v2",
                    "event_type": event_type,
                    "subject": subject,
                    "payload": dict(payload),
                    "predecessor_root": predecessor,
                    "produced_ns": time.time_ns(),
                }
                record = {**body, "record_root": root(body)}
                existed = self.path.exists()
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                if not existed:
                    self._fsync_directory()
                self.records.append(record)
                return record
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

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
        if not release_id.strip():
            raise ValueError("RELEASE_ID_REQUIRED")
        artifacts = [dict(a) for a in artifacts]
        seen_paths: set[str] = set()
        for artifact in artifacts:
            path = str(artifact.get("path", "")).strip()
            digest = str(artifact.get("sha256", "")).lower()
            if not path or path.startswith("/") or ".." in Path(path).parts:
                raise ValueError("INVALID_ARTIFACT_PATH")
            if path in seen_paths:
                raise ValueError("DUPLICATE_ARTIFACT_PATH")
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError("INVALID_ARTIFACT_SHA256")
            artifact["path"] = path
            artifact["sha256"] = digest
            seen_paths.add(path)
        decisions = [asdict(d) | {"decision_root": d.decision_root} for d in decisions]
        evidence = [asdict(e) for e in evidence]
        for item in evidence:
            if not _SHA256_RE.fullmatch(str(item.get("evidence_root", "")).lower()):
                raise ValueError("INVALID_EVIDENCE_ROOT")
        if predecessor_release_root is not None and not _SHA256_RE.fullmatch(predecessor_release_root.lower()):
            raise ValueError("INVALID_PREDECESSOR_RELEASE_ROOT")
        body = {
            "schema": "braink.r24.release-manifest/v2",
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
    REQUIRED_TESTS = {"unit", "integration", "fault_injection"}

    def evaluate(self, release: Mapping[str, Any], quality: Mapping[str, bool], security: Mapping[str, bool], tests: Mapping[str, bool], rollback_ready: bool, independent_verifier: bool) -> dict[str, Any]:
        quality_missing = sorted(k for k in self.REQUIRED_QUALITY if not quality.get(k, False))
        security_missing = sorted(k for k in self.REQUIRED_SECURITY if not security.get(k, False))
        test_missing = sorted(k for k in self.REQUIRED_TESTS if k not in tests)
        failed_tests = sorted(k for k, passed in tests.items() if not passed)
        release_root = str(release.get("release_root", ""))
        criteria = {
            "release_root_valid": bool(_SHA256_RE.fullmatch(release_root)),
            "quality_complete": not quality_missing,
            "security_complete": not security_missing,
            "required_tests_present": not test_missing,
            "tests_pass": not failed_tests and not test_missing,
            "rollback_ready": bool(rollback_ready),
            "independent_verifier": bool(independent_verifier),
        }
        status = "PROMOTED" if all(criteria.values()) else "REJECTED"
        body = {
            "status": status,
            "criteria": criteria,
            "quality_missing": quality_missing,
            "security_missing": security_missing,
            "test_missing": test_missing,
            "failed_tests": failed_tests,
            "release_root": release.get("release_root"),
        }
        body["promotion_root"] = root(body)
        return body


class MarketReadinessEvaluator:
    def evaluate(self, technical: Mapping[str, float], operational: Mapping[str, float], commercial: Mapping[str, float], evidence_coverage: float) -> dict[str, Any]:
        vectors = {"technical": technical, "operational": operational, "commercial": commercial}
        if any(not values for values in vectors.values()):
            raise ValueError("MARKET_VECTOR_EMPTY")
        values = [float(v) for group in vectors.values() for v in group.values()] + [float(evidence_coverage)]
        if any(v < 0.0 or v > 1.0 for v in values):
            raise ValueError("MARKET_SCORE_OUT_OF_RANGE")

        def avg(group: Mapping[str, float]) -> float:
            return sum(float(v) for v in group.values()) / len(group)

        scores = {
            "technical": round(avg(technical), 6),
            "operational": round(avg(operational), 6),
            "commercial": round(avg(commercial), 6),
            "evidence_coverage": round(float(evidence_coverage), 6),
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
