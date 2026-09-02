from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import hashlib, json, time, uuid


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class WorkRequest:
    request_id: str
    sector: str
    service: str
    function: str
    payload: Dict[str, Any]
    authority_scope: str


class BrainKServiceRuntime:
    REQUIRED_GROUPS = ("research", "runtime", "verification", "evolution", "proof")

    def __init__(self, sector: str, service: str, function_register: Dict[str, Any], hr_registry=None):
        self.sector = sector
        self.service = service
        self.function_register = function_register
        self.hr_registry = hr_registry
        self.requests = {}
        self.receipts = []

    def submit(self, function: str, payload: Dict[str, Any], authority_scope: str = "CUSTOMER_SERVICE"):
        if function not in self.function_register["functions"]:
            return {"status": "REJECTED", "reason": "UNKNOWN_FUNCTION", "function": function}
        request = WorkRequest(
            "REQ-" + uuid.uuid4().hex[:16], self.sector, self.service,
            function, payload, authority_scope)
        self.requests[request.request_id] = request
        work_module_id = "WM-" + root({"request": request.request_id, "function": function})[:16]
        assignments = []
        if self.hr_registry is not None:
            assignments = self.hr_registry.assign_standard_groups(
                sector=self.sector, service=self.service, function=function,
                work_module_id=work_module_id,
                supervisor_id=f"supervisor://sector/{self.sector}/{function}")
        return {
            "status": "ACCEPTED",
            "request_id": request.request_id,
            "work_module_id": work_module_id,
            "required_groups": list(self.REQUIRED_GROUPS),
            "assignments": [a.assignment_id for a in assignments],
        }

    def receipt(self, request_id: str, status: str, evidence: Dict[str, Any]):
        rec = {
            "request_id": request_id,
            "status": status,
            "evidence_root": root(evidence),
            "created_ns": time.time_ns(),
        }
        self.receipts.append(rec)
        return rec
