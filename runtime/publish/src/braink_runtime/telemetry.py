from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any

WORKER_RE = re.compile(r"^keddeh\.blade\d{2,}$")
REF_ERROR_MARKERS = ("#REF!", "#VALUE!", "#N/A", "#NAME?", "#DIV/0!")

class TelemetryError(ValueError):
    pass

@dataclass(frozen=True)
class StreamSample:
    worker_id: str
    accepted_shares: int
    rejected_shares: int
    last_reject_reason: str = "NONE"
    status: str = "ONLINE"
    difficulty: int | None = None
    job_id: str | None = None
    carrier_uri: str = "carrier://tl2"
    source_kind: str = "CARRIER_READBACK"
    observed_ns: int = 0

    @property
    def reject_rate_pct(self) -> float:
        total = self.accepted_shares + self.rejected_shares
        return round((self.rejected_shares / total) * 100, 4) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["reject_rate_pct"] = self.reject_rate_pct
        return value

def _reject_spreadsheet_error(value: Any, field: str) -> None:
    if isinstance(value, str) and any(marker in value.upper() for marker in REF_ERROR_MARKERS):
        raise TelemetryError(f"TELEMETRY_REFERENCE_ERROR:{field}:{value}")

def normalize_sample(raw: dict[str, Any]) -> StreamSample:
    for key, value in raw.items():
        _reject_spreadsheet_error(value, key)
    worker = str(raw.get("worker_id") or raw.get("worker") or "").strip()
    if not WORKER_RE.fullmatch(worker):
        raise TelemetryError(f"INVALID_WORKER_ID:{worker}")
    try:
        accepted = int(raw.get("accepted_shares", 0)); rejected = int(raw.get("rejected_shares", 0))
    except (TypeError, ValueError) as exc:
        raise TelemetryError("SHARE_COUNTS_MUST_BE_INTEGERS") from exc
    if accepted < 0 or rejected < 0:
        raise TelemetryError("SHARE_COUNTS_MUST_BE_NONNEGATIVE")
    difficulty = raw.get("difficulty")
    if difficulty is not None:
        try: difficulty = int(difficulty)
        except (TypeError, ValueError) as exc: raise TelemetryError("DIFFICULTY_MUST_BE_INTEGER") from exc
        if difficulty <= 0: raise TelemetryError("DIFFICULTY_MUST_BE_POSITIVE")
    source_kind = str(raw.get("source_kind", "CARRIER_READBACK")).strip().upper()
    if source_kind not in {"CARRIER_READBACK", "POOL_API_READBACK", "SHEET_PROJECTION", "LOCAL_TEST"}:
        raise TelemetryError(f"UNSUPPORTED_SOURCE_KIND:{source_kind}")
    return StreamSample(
        worker_id=worker, accepted_shares=accepted, rejected_shares=rejected,
        last_reject_reason=str(raw.get("last_reject_reason", "NONE") or "NONE"),
        status=str(raw.get("status", "ONLINE") or "ONLINE").upper(), difficulty=difficulty,
        job_id=(str(raw["job_id"]) if raw.get("job_id") is not None else None),
        carrier_uri=str(raw.get("carrier_uri", "carrier://tl2")), source_kind=source_kind,
        observed_ns=int(raw.get("observed_ns") or time.time_ns()),
    )

class TelemetryFabric:
    """Resident BRAINK telemetry authority.

    Carrier/host owns transport. Sheets are projection/readback only.
    """
    def __init__(self, data_dir: str | Path | None = None, *, stale_after_s: float = 180.0):
        self._lock = RLock(); self._samples = {}; self._quarantine = []
        self._stale_after_ns = int(stale_after_s * 1_000_000_000)
        self._ledger = Path(data_dir) / "telemetry_receipts.jsonl" if data_dir else None
        if self._ledger: self._ledger.parent.mkdir(parents=True, exist_ok=True)

    def ingest(self, raw: dict[str, Any]) -> dict[str, Any]:
        try: sample = normalize_sample(raw)
        except Exception as exc:
            receipt = {"status":"QUARANTINED","reason":str(exc),"worker_id":str(raw.get("worker_id") or raw.get("worker") or "UNKNOWN"),"observed_ns":time.time_ns()}
            with self._lock:
                self._quarantine.append(receipt); self._append(receipt)
            return receipt
        with self._lock:
            previous = self._samples.get(sample.worker_id)
            if previous and sample.observed_ns < previous.observed_ns:
                return {"status":"REJECTED_STALE_SAMPLE","worker_id":sample.worker_id,"previous_observed_ns":previous.observed_ns,"observed_ns":sample.observed_ns}
            self._samples[sample.worker_id] = sample
            receipt = {"status":"INGESTED","worker_id":sample.worker_id,"claim_class":"POOL_SHARE_TELEMETRY","accepted_shares":sample.accepted_shares,"rejected_shares":sample.rejected_shares,"reject_rate_pct":sample.reject_rate_pct,"source_kind":sample.source_kind,"observed_ns":sample.observed_ns}
            self._append(receipt); return receipt

    def _append(self, receipt: dict[str, Any]) -> None:
        if not self._ledger: return
        with self._ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")

    def snapshot(self, *, now_ns: int | None = None) -> dict[str, Any]:
        now_ns = int(now_ns or time.time_ns())
        with self._lock:
            samples = [self._samples[k] for k in sorted(self._samples)]; quarantine_count = len(self._quarantine)
        active = [s for s in samples if s.status == "ONLINE" and (now_ns - s.observed_ns) <= self._stale_after_ns]
        stale = [s for s in samples if s not in active]
        total_acc = sum(s.accepted_shares for s in active); total_rej = sum(s.rejected_shares for s in active); total = total_acc + total_rej
        return {
            "schema":"braink.kex.telemetry.snapshot.v1","authority":"KEX://BRAINK/TELEMETRY/FABRIC",
            "transport_authority":"carrier/host runtime","sheet_role":"PROJECTION_READBACK_ONLY",
            "active_streams":len(active),"known_streams":len(samples),"stale_streams":len(stale),"quarantined_samples":quarantine_count,
            "total_accepted_shares":total_acc,"total_rejected_shares":total_rej,"fleet_reject_rate_pct":round((total_rej/total)*100,4) if total else 0.0,
            "claim_class":"POOL_SHARE_TELEMETRY","bitcoin_block_discovery":False,
            "block_claim_rule":"Only separately verified Bitcoin network-target acceptance may assert block discovery.",
            "streams":[s.to_dict() for s in active],"stale":[s.to_dict() for s in stale],
        }

    def sheet_projection(self) -> list[dict[str, Any]]:
        return [{"WORKER":s["worker_id"],"ACCEPTED_SHARES":s["accepted_shares"],"REJECTED_SHARES":s["rejected_shares"],"REJECT_RATE_PCT":s["reject_rate_pct"],"LAST_REJECT_REASON":s["last_reject_reason"],"STATUS":s["status"],"CARRIER_URI":s["carrier_uri"],"SOURCE_KIND":s["source_kind"],"CLAIM_CLASS":"POOL_SHARE_TELEMETRY"} for s in self.snapshot()["streams"]]
