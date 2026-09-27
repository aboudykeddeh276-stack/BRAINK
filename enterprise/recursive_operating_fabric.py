from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence
import hashlib
import json
import time


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FabricError(RuntimeError):
    pass


class AdmissionError(FabricError):
    pass


class PromotionError(FabricError):
    pass


class LifecycleState(str, Enum):
    DECLARED = "DECLARED"
    IMPLEMENTED = "IMPLEMENTED"
    EXECUTED = "EXECUTED"
    DEPLOYED = "DEPLOYED"
    ACTIVE = "ACTIVE"
    FUNCTIONING = "FUNCTIONING"
    INTEGRATED = "INTEGRATED"
    VERIFIED = "VERIFIED"
    SUSTAINED = "SUSTAINED"


STATE_ORDER = tuple(LifecycleState)
PREDECESSOR = {STATE_ORDER[i]: STATE_ORDER[i - 1] for i in range(1, len(STATE_ORDER))}


class NodeKind(str, Enum):
    BUILD = "BUILD"
    SKILL = "SKILL"
    SUBSKILL = "SUBSKILL"
    WORKFLOW = "WORKFLOW"
    STATE = "STATE"
    ACTUATOR = "ACTUATOR"
    SUBSTRATE = "SUBSTRATE"
    RUNTIME = "RUNTIME"
    OBSERVER = "OBSERVER"
    VERIFIER = "VERIFIER"
    EVIDENCE = "EVIDENCE"
    GOVERNANCE = "GOVERNANCE"
    OPTIMISATION = "OPTIMISATION"
    REDEPLOYMENT = "REDEPLOYMENT"


REQUIRED_OPERATION_FIELDS = (
    "what",
    "how",
    "how_is",
    "how_operates",
    "acts_on",
    "change",
    "change_location",
    "observer_id",
    "verifier_id",
    "evidence_predicate",
    "next_state_predicate",
)


@dataclass(frozen=True)
class AuthorityContext:
    authority_id: str
    capabilities: tuple[str, ...]
    parent_authority_id: Optional[str] = None

    def derive(self, authority_id: str, capabilities: Sequence[str]) -> "AuthorityContext":
        child = set(capabilities)
        parent = set(self.capabilities)
        if not child.issubset(parent):
            raise AdmissionError("DERIVED_CONTEXT_AUTHORITY_ESCALATION")
        return AuthorityContext(authority_id, tuple(sorted(child)), self.authority_id)


@dataclass(frozen=True)
class OperationalLine:
    line_id: str
    what: str
    how: str
    how_is: str
    how_operates: str
    acts_on: str
    change: str
    change_location: str
    observer_id: str
    verifier_id: str
    evidence_predicate: str
    next_state_predicate: str
    actuator_id: str
    substrate_id: str
    runtime_id: str
    persistence_id: str
    failure_behavior: str
    recovery_procedure: str

    def validate(self) -> None:
        data = asdict(self)
        missing = [k for k in REQUIRED_OPERATION_FIELDS if not str(data.get(k, "")).strip()]
        if missing:
            raise AdmissionError("UNRESOLVED_OPERATION_FIELDS:" + ",".join(sorted(missing)))
        for key in ("actuator_id", "substrate_id", "runtime_id", "persistence_id", "failure_behavior", "recovery_procedure"):
            if not str(data.get(key, "")).strip():
                raise AdmissionError("UNRESOLVED_OPERATION_FIELD:" + key)
        unresolved = ("TODO", "TBD", "SOMEHOW", "MAGIC", "SIMULATE_SUCCESS", "FAKE_SUCCESS")
        joined = " ".join(str(v).upper() for v in data.values())
        bad = [token for token in unresolved if token in joined]
        if bad:
            raise AdmissionError("UNRESOLVED_OR_FAKE_SEMANTICS:" + ",".join(bad))


@dataclass
class FabricNode:
    node_id: str
    kind: NodeKind
    parent_id: Optional[str]
    authority: AuthorityContext
    state: LifecycleState = LifecycleState.DECLARED
    operational_lines: list[OperationalLine] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    evidence: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    state_history: list[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        body = {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "parent_id": self.parent_id,
            "authority": asdict(self.authority),
            "state": self.state.value,
            "children": sorted(self.children),
            "operational_lines": [asdict(x) for x in self.operational_lines],
            "evidence": self.evidence,
            "metadata": self.metadata,
        }
        return {**body, "snapshot_hash": sha256(body)}


class RecursiveOperatingFabric:
    """Strict recursive execution fabric.

    It intentionally refuses state inference. Every lifecycle promotion is
    sequential and requires state-specific evidence for the target state.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, FabricNode] = {}
        self.events: list[Dict[str, Any]] = []

    def register(self, node: FabricNode) -> FabricNode:
        if node.node_id in self.nodes:
            raise AdmissionError("DUPLICATE_NODE_ID")
        if node.parent_id and node.parent_id not in self.nodes:
            raise AdmissionError("PARENT_NOT_REGISTERED")
        if node.parent_id:
            parent = self.nodes[node.parent_id]
            if not set(node.authority.capabilities).issubset(set(parent.authority.capabilities)):
                raise AdmissionError("DESCENDANT_AUTHORITY_EXCEEDS_PARENT")
            parent.children.append(node.node_id)
        self.nodes[node.node_id] = node
        self._event("NODE_REGISTERED", node.node_id, {"kind": node.kind.value, "parent_id": node.parent_id})
        return node

    def _event(self, kind: str, node_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        body = {
            "event_seq": len(self.events) + 1,
            "event": kind,
            "node_id": node_id,
            "observed_ns": time.time_ns(),
            "payload": dict(payload),
        }
        event = {**body, "event_hash": sha256(body)}
        self.events.append(event)
        return event

    def add_line(self, node_id: str, line: OperationalLine) -> None:
        line.validate()
        node = self.nodes[node_id]
        refs = {
            "actuator_id": (line.actuator_id, NodeKind.ACTUATOR),
            "substrate_id": (line.substrate_id, NodeKind.SUBSTRATE),
            "runtime_id": (line.runtime_id, NodeKind.RUNTIME),
            "observer_id": (line.observer_id, NodeKind.OBSERVER),
            "verifier_id": (line.verifier_id, NodeKind.VERIFIER),
            "persistence_id": (line.persistence_id, None),
        }
        for label, (ref, kind) in refs.items():
            if ref not in self.nodes:
                raise AdmissionError(f"UNDEFINED_{label.upper()}:{ref}")
            if kind is not None and self.nodes[ref].kind != kind:
                raise AdmissionError(f"INVALID_{label.upper()}_KIND:{ref}")
        if line.observer_id == line.verifier_id:
            raise AdmissionError("OBSERVER_AND_VERIFIER_MUST_BE_DISTINCT")
        node.operational_lines.append(line)
        self._event("OPERATIONAL_LINE_ADMITTED", node_id, {"line_id": line.line_id})

    def admission_report(self, root_id: str) -> Dict[str, Any]:
        if root_id not in self.nodes:
            raise AdmissionError("ROOT_NOT_REGISTERED")
        reachable = set()
        stack = [root_id]
        findings: list[Dict[str, Any]] = []
        while stack:
            nid = stack.pop()
            if nid in reachable:
                findings.append({"node_id": nid, "code": "CYCLE_OR_DUPLICATE_REACHABILITY"})
                continue
            reachable.add(nid)
            node = self.nodes[nid]
            stack.extend(node.children)
            if node.kind in {NodeKind.SKILL, NodeKind.SUBSKILL, NodeKind.WORKFLOW, NodeKind.ACTUATOR} and not node.operational_lines:
                findings.append({"node_id": nid, "code": "NO_OPERATIONAL_LINE"})
            for line in node.operational_lines:
                try:
                    line.validate()
                except AdmissionError as exc:
                    findings.append({"node_id": nid, "line_id": line.line_id, "code": str(exc)})
        for nid, node in self.nodes.items():
            if node.parent_id and nid not in reachable:
                findings.append({"node_id": nid, "code": "ORPHANED_OR_UNREACHABLE_NODE"})
        return {
            "root_id": root_id,
            "admitted": not findings,
            "reachable_count": len(reachable),
            "node_count": len(self.nodes),
            "findings": findings,
            "report_hash": sha256({"root_id": root_id, "reachable": sorted(reachable), "findings": findings}),
        }

    def record_evidence(self, node_id: str, state: LifecycleState | str, packet: Mapping[str, Any]) -> str:
        target = LifecycleState(state)
        node = self.nodes[node_id]
        body = dict(packet)
        body["target_state"] = target.value
        evidence_hash = sha256(body)
        node.evidence[target.value] = {**body, "evidence_hash": evidence_hash}
        self._event("EVIDENCE_RECORDED", node_id, {"target_state": target.value, "evidence_hash": evidence_hash})
        return evidence_hash

    def promote(self, node_id: str, target: LifecycleState | str) -> Dict[str, Any]:
        target = LifecycleState(target)
        node = self.nodes[node_id]
        if target == LifecycleState.DECLARED:
            raise PromotionError("DECLARED_IS_INITIAL_STATE")
        expected = PREDECESSOR[target]
        if node.state != expected:
            raise PromotionError(f"SEQUENTIAL_PROMOTION_REQUIRED:{node.state.value}->{target.value}")
        evidence = node.evidence.get(target.value)
        if not evidence:
            raise PromotionError("TARGET_STATE_EVIDENCE_MISSING")
        self._validate_state_evidence(node, target, evidence)
        previous = node.snapshot()["snapshot_hash"]
        node.state = target
        resulting = node.snapshot()["snapshot_hash"]
        transition = {
            "from": expected.value,
            "to": target.value,
            "previous_state_ref": previous,
            "resulting_state_ref": resulting,
            "evidence_hash": evidence["evidence_hash"],
        }
        node.state_history.append(transition)
        self._event("STATE_PROMOTED", node_id, transition)
        return transition

    def _validate_state_evidence(self, node: FabricNode, target: LifecycleState, e: Mapping[str, Any]) -> None:
        if e.get("simulated") or e.get("fake_success"):
            raise PromotionError("SIMULATED_OR_FAKE_SUCCESS_REJECTED")
        if target == LifecycleState.IMPLEMENTED:
            self._need(e, "source_ref", "source_hash", "implementation_readback")
        elif target == LifecycleState.EXECUTED:
            self._need(e, "command_id", "execution_authority", "computational_transition", "post_state_hash")
            if e.get("exit_code") != 0:
                raise PromotionError("EXECUTION_EXIT_NONZERO")
            if not e.get("effect_observed"):
                raise PromotionError("INVOCATION_WITHOUT_EFFECT")
            if e.get("gate_telemetry") == e.get("execution_authority"):
                raise PromotionError("GATE_TELEMETRY_IS_NOT_EXECUTION_AUTHORITY")
        elif target == LifecycleState.DEPLOYED:
            self._need(e, "target_substrate_id", "deployment_command_id", "realization_readback", "target_artifact_hash")
            if not e.get("realization_readback"):
                raise PromotionError("DEPLOYMENT_WITHOUT_SUBSTRATE_READBACK")
        elif target == LifecycleState.ACTIVE:
            self._need(e, "participation_probe", "heartbeat_observed_at", "runtime_identity")
            if not e.get("participating"):
                raise PromotionError("ACTIVE_WITHOUT_PARTICIPATION")
        elif target == LifecycleState.FUNCTIONING:
            self._need(e, "specified_behavior", "expected_result", "observed_result")
            if not e.get("behavior_passed"):
                raise PromotionError("FUNCTIONING_BEHAVIOR_NOT_DEMONSTRATED")
        elif target == LifecycleState.INTEGRATED:
            self._need(e, "integration_edges", "edge_readbacks")
            edges = list(e.get("integration_edges") or [])
            readbacks = list(e.get("edge_readbacks") or [])
            if not edges or len(edges) != len(readbacks) or not all(bool(x) for x in readbacks):
                raise PromotionError("INTEGRATION_EDGES_NOT_OBSERVED")
        elif target == LifecycleState.VERIFIED:
            self._need(e, "actor_id", "verifier_id", "verifier_report_ref", "post_state_hash", "independent_readback")
            if e["actor_id"] == e["verifier_id"]:
                raise PromotionError("ACTOR_CANNOT_VERIFY_OWN_DELIVERY")
            if not e.get("independent_readback"):
                raise PromotionError("VERIFICATION_WITHOUT_INDEPENDENT_READBACK")
            if e.get("receipt_hash") and e.get("receipt_hash") == e.get("post_state_hash"):
                raise PromotionError("RECEIPT_IS_NOT_POST_STATE_EVIDENCE")
        elif target == LifecycleState.SUSTAINED:
            self._need(e, "observation_count", "observation_window", "recovery_procedure", "recovery_readback")
            if int(e.get("observation_count", 0)) < 2:
                raise PromotionError("SUSTAINED_REQUIRES_REPEATED_OBSERVATION")
            if not e.get("recovery_readback"):
                raise PromotionError("SUSTAINED_REQUIRES_RECOVERY_EVIDENCE")

    @staticmethod
    def _need(e: Mapping[str, Any], *keys: str) -> None:
        missing = [k for k in keys if e.get(k) in (None, "", [], {})]
        if missing:
            raise PromotionError("STATE_EVIDENCE_FIELDS_MISSING:" + ",".join(sorted(missing)))

    def descendant_admission(self, root_id: str) -> Dict[str, Any]:
        report = self.admission_report(root_id)
        if not report["admitted"]:
            return report
        root = self.nodes[root_id]
        semantic_root = root.metadata.get("directive_semantic_root")
        for nid in self._descendants(root_id):
            child = self.nodes[nid]
            if semantic_root and child.metadata.get("directive_semantic_root") not in (None, semantic_root):
                report["admitted"] = False
                report["findings"].append({"node_id": nid, "code": "SEMANTIC_REDUCTION_OR_DIVERGENCE"})
        report["report_hash"] = sha256({k: v for k, v in report.items() if k != "report_hash"})
        return report

    def _descendants(self, root_id: str) -> Iterable[str]:
        stack = list(self.nodes[root_id].children)
        while stack:
            nid = stack.pop()
            yield nid
            stack.extend(self.nodes[nid].children)

    def optimise(self, node_id: str, metrics: Mapping[str, Any], invariant_checks: Mapping[str, bool]) -> Dict[str, Any]:
        node = self.nodes[node_id]
        if STATE_ORDER.index(node.state) < STATE_ORDER.index(LifecycleState.FUNCTIONING):
            raise PromotionError("OPTIMISATION_REQUIRES_DEMONSTRATED_MECHANICS")
        if not invariant_checks or not all(invariant_checks.values()):
            raise PromotionError("OPTIMISATION_INVARIANT_FAILURE")
        required_metrics = {
            "execution_latency",
            "failure_recovery",
            "idempotency",
            "concurrency",
            "persistence",
            "evidence_completeness",
            "dependency_depth",
            "duplicate_work",
            "actuator_reliability",
            "verification_cost",
        }
        missing = sorted(required_metrics.difference(metrics))
        if missing:
            raise PromotionError("OPTIMISATION_METRICS_MISSING:" + ",".join(missing))
        body = {
            "node_id": node_id,
            "state": node.state.value,
            "metrics": dict(metrics),
            "invariants": dict(invariant_checks),
            "requires_redeployment": True,
        }
        receipt = {**body, "optimisation_root": sha256(body)}
        self._event("OPTIMISATION_QUALIFIED", node_id, receipt)
        return receipt

    def redeploy_revision(self, node_id: str, optimisation_receipt: Mapping[str, Any], new_source_ref: str, new_source_hash: str) -> FabricNode:
        node = self.nodes[node_id]
        if not optimisation_receipt.get("requires_redeployment"):
            raise AdmissionError("REDEPLOYMENT_RECEIPT_REQUIRED")
        revision = int(node.metadata.get("revision", 1)) + 1
        new_id = f"{node_id}@r{revision}"
        meta = dict(node.metadata)
        meta.update({
            "revision": revision,
            "predecessor": node_id,
            "optimisation_root": optimisation_receipt.get("optimisation_root"),
            "new_source_ref": new_source_ref,
            "new_source_hash": new_source_hash,
        })
        child = FabricNode(
            node_id=new_id,
            kind=node.kind,
            parent_id=node.parent_id,
            authority=node.authority,
            metadata=meta,
        )
        self.register(child)
        return child

    @staticmethod
    def parent_outcome(actuator_results: Sequence[Mapping[str, Any]]) -> str:
        eligible = [x for x in actuator_results if x.get("eligible", True)]
        if not eligible:
            return "BLOCKED_NO_ELIGIBLE_ACTUATOR"
        succeeded = [x for x in eligible if x.get("status") in {"EXECUTED", "DEPLOYED", "FUNCTIONING", "VERIFIED", "SUSTAINED"}]
        failed = [x for x in eligible if x.get("status") in {"FAILED", "DOWN", "REJECTED"}]
        if succeeded and failed:
            return "DEGRADED_CONTINUE_ELIGIBLE_PATHS"
        if succeeded:
            return "CONTINUE"
        return "BLOCKED_ALL_ELIGIBLE_ACTUATORS_FAILED"

    def snapshot(self) -> Dict[str, Any]:
        body = {
            "schema": "braink.recursive-operating-fabric.r25/v1",
            "states": [x.value for x in STATE_ORDER],
            "nodes": {nid: node.snapshot() for nid, node in sorted(self.nodes.items())},
            "events": self.events,
        }
        return {**body, "fabric_root": sha256(body)}
