from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any
import time

@dataclass(frozen=True)
class ObserverDecision:
    action:str
    severity:str
    subject:str
    reason:str
    continuation_priority:float
    created_ns:int

class ObserverPolicyEngine:
    def decide(self, signal:Dict[str,Any])->ObserverDecision:
        kind=signal["kind"]
        subject=signal["subject"]
        payload=signal.get("payload",{})
        if kind in {"HASH_MISMATCH","CONTRADICTION"}:
            return ObserverDecision("QUARANTINE_AND_REPAIR","CRITICAL",subject,kind,100.0,time.time_ns())
        if kind in {"HOLE_UNBOUND","ADAPTER_UNAVAILABLE"}:
            return ObserverDecision("DEFER_AND_RESOLVE","HIGH",subject,kind,40.0,time.time_ns())
        if kind in {"READBACK_MISMATCH","RELEASE_MARKER_MISMATCH"}:
            return ObserverDecision("AMEND_OR_REPAIR","HIGH",subject,kind,60.0,time.time_ns())
        if kind in {"PUBLIC_READBACK","HTTP_READBACK"} and payload.get("status") in {200,"200","PASS"}:
            return ObserverDecision("CONTINUE","INFO",subject,"OBSERVER_CONFIRMED",5.0,time.time_ns())
        if kind in {"PROCESS_EXECUTED","PROCESS_SIGNALED"}:
            return ObserverDecision("CONTINUE","INFO",subject,kind,10.0,time.time_ns())
        return ObserverDecision("RECONCILE","MEDIUM",subject,kind,20.0,time.time_ns())
    def as_dict(self, signal):
        return asdict(self.decide(signal))
