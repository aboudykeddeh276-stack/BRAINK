from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import hashlib, json, time, uuid


def root(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class HRRole:
    role_id: str
    function: str
    authority_scope: str
    supervision_only: bool = False


@dataclass(frozen=True)
class AgentAssignment:
    assignment_id: str
    sector: str
    service: str
    function: str
    work_module_id: str
    supervisor_id: str
    agent_group: str
    authority_scope: str
    created_ns: int


class HRBrainKRegistry:
    """Unified HR/BRAINK control plane for sector product repositories."""

    REQUIRED_GROUPS = ("research", "runtime", "verification", "evolution", "proof")

    def __init__(self):
        self.roles: Dict[str, HRRole] = {}
        self.assignments: Dict[str, AgentAssignment] = {}
        self.receipts: List[Dict[str, Any]] = []

    def register_role(self, role: HRRole) -> HRRole:
        self.roles[role.role_id] = role
        return role

    def assign_group(self, *, sector: str, service: str, function: str,
                     work_module_id: str, supervisor_id: str,
                     agent_group: str, authority_scope: str) -> AgentAssignment:
        assignment = AgentAssignment(
            assignment_id="ASN-" + uuid.uuid4().hex[:16],
            sector=sector, service=service, function=function,
            work_module_id=work_module_id, supervisor_id=supervisor_id,
            agent_group=agent_group, authority_scope=authority_scope,
            created_ns=time.time_ns())
        self.assignments[assignment.assignment_id] = assignment
        return assignment

    def assign_standard_groups(self, *, sector: str, service: str,
                               function: str, work_module_id: str,
                               supervisor_id: str) -> List[AgentAssignment]:
        return [self.assign_group(
            sector=sector, service=service, function=function,
            work_module_id=work_module_id, supervisor_id=supervisor_id,
            agent_group=group, authority_scope=f"{sector}:{service}:{function}:{group}"
        ) for group in self.REQUIRED_GROUPS]

    def receipt(self, assignment: AgentAssignment, status: str, evidence: Dict[str, Any]):
        rec = {
            "assignment_id": assignment.assignment_id,
            "work_module_id": assignment.work_module_id,
            "status": status,
            "evidence_root": root(evidence),
            "created_ns": time.time_ns(),
        }
        self.receipts.append(rec)
        return rec

    def state(self) -> Dict[str, Any]:
        return {
            "roles": {k: asdict(v) for k, v in self.roles.items()},
            "assignments": {k: asdict(v) for k, v in self.assignments.items()},
            "receipts": list(self.receipts),
            "root": root({
                "roles": {k: asdict(v) for k, v in self.roles.items()},
                "assignments": {k: asdict(v) for k, v in self.assignments.items()},
                "receipts": self.receipts,
            }),
        }
