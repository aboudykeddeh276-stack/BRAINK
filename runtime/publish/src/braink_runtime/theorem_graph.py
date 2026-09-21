from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
import json
from collections import defaultdict, deque
from typing import Any, Callable, Iterable, Mapping, Sequence


class GraphViolation(RuntimeError):
    pass


class ClaimState(str, Enum):
    DECLARED = "DECLARED"
    SPECIFIED = "SPECIFIED"
    IMPLEMENTED = "IMPLEMENTED"
    EXECUTED = "EXECUTED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    CONTESTED = "CONTESTED"
    FALSIFIED = "FALSIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RelationType(str, Enum):
    DEPENDS_ON = "depends_on"
    IMPLIES = "implies"
    REFINES = "refines"
    CONSTRAINS = "constrains"
    EQUIVALENT_TO = "equivalent_to"
    CONTRADICTS = "contradicts"
    INSTANTIATED_BY = "instantiated_by"


class PropagationOutcome(str, Enum):
    STRENGTHENED = "STRENGTHENED"
    COMPATIBLE = "COMPATIBLE"
    CONTRADICTED = "CONTRADICTED"
    INVALIDATED = "INVALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNCHANGED = "UNCHANGED"
    TYPE_REJECTED = "TYPE_REJECTED"
    ROUTE_REJECTED = "ROUTE_REJECTED"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    kind: str
    state: ClaimState
    ref: str
    root: str | None = None


@dataclass(frozen=True)
class OperatorSet:
    inherited: tuple[str, ...] = ()
    local: tuple[str, ...] = ()
    overridden: tuple[str, ...] = ()
    prohibited: tuple[str, ...] = ()

    def resolved(self, parent: "OperatorSet | None" = None) -> tuple[str, ...]:
        inherited = set(self.inherited)
        if parent is not None:
            inherited |= set(parent.resolved())
        inherited -= set(self.overridden)
        inherited -= set(self.prohibited)
        return tuple(sorted((inherited | set(self.local)) - set(self.prohibited)))


@dataclass(frozen=True)
class RoutingContract:
    compatible_sectors: tuple[str, ...]
    propagation_depth: int = 1
    invalidation_path: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.propagation_depth < 0:
            raise GraphViolation("PROPAGATION_DEPTH_NEGATIVE")


@dataclass
class TheoremObject:
    theorem_id: str
    canonical_name: str
    version: str
    canonical_definition: str
    invariant: str
    domain: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    admissibility_constraints: tuple[str, ...]
    operators: OperatorSet
    routing: RoutingContract
    claim_state: ClaimState = ClaimState.DECLARED
    proofs: list[EvidenceRef] = field(default_factory=list)
    tests: list[EvidenceRef] = field(default_factory=list)
    counterexamples: list[EvidenceRef] = field(default_factory=list)
    receipts: list[EvidenceRef] = field(default_factory=list)
    aliases: tuple[str, ...] = ()
    eliminated_restatements: list[str] = field(default_factory=list)
    retained_context_deltas: list[str] = field(default_factory=list)

    @property
    def canonical_statement(self) -> str:
        return self.invariant.strip()

    @property
    def object_root(self) -> str:
        payload = asdict(self)
        for key in ("proofs", "tests", "counterexamples", "receipts", "eliminated_restatements", "retained_context_deltas"):
            payload.pop(key, None)
        payload["claim_state"] = self.claim_state.value
        return digest(payload)


@dataclass(frozen=True)
class GraphRelation:
    source_id: str
    target_id: str
    relation: RelationType
    transform_id: str | None = None


@dataclass(frozen=True)
class SectorTransform:
    transform_id: str
    sector: str
    accepted_input_types: tuple[str, ...]
    emitted_output_types: tuple[str, ...]
    apply: Callable[[TheoremObject], Mapping[str, Any]] = field(compare=False, repr=False)


@dataclass(frozen=True)
class SectorApplication:
    application_id: str
    theorem_id: str
    sector: str
    transform_id: str
    source_root: str
    claim_state: ClaimState
    output_types: tuple[str, ...]
    payload: Mapping[str, Any]
    application_root: str


@dataclass(frozen=True)
class PropagationEvent:
    source_id: str
    target_id: str
    relation: RelationType
    outcome: PropagationOutcome
    prior_state: ClaimState
    next_state: ClaimState
    reason: str


@dataclass(frozen=True)
class ProjectionState:
    sector: str
    object_ids: tuple[str, ...]
    application_ids: tuple[str, ...]
    proof_states: Mapping[str, str]
    projection_root: str


class TheoremRegistry:
    """Typed theorem-object graph with proof-aware symmetric propagation.

    Authority lives in stable theorem objects. Pages, diagrams and sector views are
    computed projections. Positive propagation and invalidation use the same graph.
    """

    def __init__(self) -> None:
        self.objects: dict[str, TheoremObject] = {}
        self.relations: list[GraphRelation] = []
        self.transforms: dict[str, SectorTransform] = {}
        self.applications: dict[str, SectorApplication] = {}
        self._incoming: dict[str, list[GraphRelation]] = defaultdict(list)
        self._outgoing: dict[str, list[GraphRelation]] = defaultdict(list)
        self.event_log: list[PropagationEvent] = []

    def register(self, theorem: TheoremObject) -> None:
        if not theorem.theorem_id or theorem.theorem_id in self.objects:
            raise GraphViolation("THEOREM_ID_COLLISION")
        if not theorem.input_types or not theorem.output_types:
            raise GraphViolation("THEOREM_TYPES_REQUIRED")
        if not theorem.canonical_definition.strip() or not theorem.invariant.strip():
            raise GraphViolation("THEOREM_DEFINITION_REQUIRED")
        self.objects[theorem.theorem_id] = theorem

    def register_transform(self, transform: SectorTransform) -> None:
        if transform.transform_id in self.transforms:
            raise GraphViolation("TRANSFORM_ID_COLLISION")
        self.transforms[transform.transform_id] = transform

    def connect(self, relation: GraphRelation) -> None:
        if relation.source_id not in self.objects or relation.target_id not in self.objects:
            raise GraphViolation("RELATION_ENDPOINT_UNKNOWN")
        if relation.source_id == relation.target_id:
            raise GraphViolation("SELF_RELATION_REJECTED")
        if relation in self.relations:
            return
        source = self.objects[relation.source_id]
        target = self.objects[relation.target_id]
        if relation.relation in {RelationType.DEPENDS_ON, RelationType.IMPLIES, RelationType.REFINES, RelationType.CONSTRAINS}:
            if not (set(source.output_types) & set(target.input_types)):
                raise GraphViolation("RELATION_TYPE_MISMATCH")
        if relation.relation == RelationType.EQUIVALENT_TO:
            if set(source.output_types) != set(target.output_types):
                raise GraphViolation("EQUIVALENCE_TYPE_MISMATCH")
        if relation.transform_id is not None and relation.transform_id not in self.transforms:
            raise GraphViolation("RELATION_TRANSFORM_UNKNOWN")
        self.relations.append(relation)
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def _proof_strength(self, state: ClaimState) -> int:
        ordering = {
            ClaimState.DECLARED: 0,
            ClaimState.SPECIFIED: 1,
            ClaimState.IMPLEMENTED: 2,
            ClaimState.EXECUTED: 3,
            ClaimState.OBSERVED: 4,
            ClaimState.VERIFIED: 5,
        }
        return ordering.get(state, -1)

    def _positive_propagation_state(self, source: TheoremObject, target: TheoremObject, relation: RelationType) -> tuple[ClaimState, PropagationOutcome, str]:
        if source.claim_state == ClaimState.FALSIFIED:
            return ClaimState.REVIEW_REQUIRED, PropagationOutcome.INVALIDATED, "UPSTREAM_FALSIFIED"
        if source.claim_state in {ClaimState.CONTESTED, ClaimState.REVIEW_REQUIRED}:
            return ClaimState.REVIEW_REQUIRED, PropagationOutcome.REVIEW_REQUIRED, "UPSTREAM_NOT_STABLE"
        if relation == RelationType.CONTRADICTS:
            if source.claim_state == ClaimState.VERIFIED:
                return ClaimState.CONTESTED, PropagationOutcome.CONTRADICTED, "VERIFIED_CONTRADICTION"
            return target.claim_state, PropagationOutcome.COMPATIBLE, "UNVERIFIED_CONTRADICTION_RECORDED"
        if source.claim_state == ClaimState.VERIFIED and self._proof_strength(target.claim_state) < self._proof_strength(ClaimState.OBSERVED):
            return ClaimState.OBSERVED, PropagationOutcome.STRENGTHENED, "VERIFIED_UPSTREAM_SUPPORT"
        return target.claim_state, PropagationOutcome.COMPATIBLE, "TYPE_SAFE_RELATION_NO_STATE_PROMOTION"

    def propagate(self, source_id: str, *, max_depth: int | None = None) -> tuple[PropagationEvent, ...]:
        if source_id not in self.objects:
            raise GraphViolation("THEOREM_UNKNOWN")
        source_contract = self.objects[source_id].routing
        depth_limit = source_contract.propagation_depth if max_depth is None else max_depth
        queue = deque([(source_id, 0)])
        visited_edges: set[tuple[str, str, str]] = set()
        events: list[PropagationEvent] = []
        while queue:
            current_id, depth = queue.popleft()
            if depth >= depth_limit:
                continue
            current = self.objects[current_id]
            for rel in self._outgoing[current_id]:
                key = (rel.source_id, rel.target_id, rel.relation.value)
                if key in visited_edges:
                    continue
                visited_edges.add(key)
                target = self.objects[rel.target_id]
                prior = target.claim_state
                next_state, outcome, reason = self._positive_propagation_state(current, target, rel.relation)
                target.claim_state = next_state
                event = PropagationEvent(rel.source_id, rel.target_id, rel.relation, outcome, prior, next_state, reason)
                self.event_log.append(event)
                events.append(event)
                queue.append((rel.target_id, depth + 1))
        return tuple(events)

    def set_claim_state(self, theorem_id: str, state: ClaimState, *, evidence: EvidenceRef | None = None) -> tuple[PropagationEvent, ...]:
        theorem = self.objects[theorem_id]
        theorem.claim_state = state
        if evidence is not None:
            if evidence.kind == "counterexample":
                theorem.counterexamples.append(evidence)
            elif evidence.kind == "test":
                theorem.tests.append(evidence)
            elif evidence.kind == "receipt":
                theorem.receipts.append(evidence)
            else:
                theorem.proofs.append(evidence)
        return self.propagate(theorem_id)

    def route(self, theorem_id: str) -> tuple[SectorApplication, ...]:
        theorem = self.objects[theorem_id]
        out: list[SectorApplication] = []
        for transform in self.transforms.values():
            if transform.sector not in theorem.routing.compatible_sectors:
                continue
            if not (set(theorem.output_types) & set(transform.accepted_input_types)):
                continue
            payload = dict(transform.apply(theorem))
            application_id = f"application:{theorem_id}:{transform.sector}:{transform.transform_id}"
            body = {
                "application_id": application_id,
                "theorem_id": theorem_id,
                "sector": transform.sector,
                "transform_id": transform.transform_id,
                "source_root": theorem.object_root,
                "claim_state": theorem.claim_state.value,
                "output_types": transform.emitted_output_types,
                "payload": payload,
            }
            app = SectorApplication(
                application_id=application_id,
                theorem_id=theorem_id,
                sector=transform.sector,
                transform_id=transform.transform_id,
                source_root=theorem.object_root,
                claim_state=theorem.claim_state,
                output_types=transform.emitted_output_types,
                payload=payload,
                application_root=digest(body),
            )
            self.applications[application_id] = app
            out.append(app)
        return tuple(sorted(out, key=lambda a: (a.sector, a.transform_id)))

    def render_sector(self, sector: str) -> ProjectionState:
        apps = sorted((a for a in self.applications.values() if a.sector == sector), key=lambda a: a.application_id)
        object_ids = tuple(sorted({a.theorem_id for a in apps}))
        app_ids = tuple(a.application_id for a in apps)
        states = {oid: self.objects[oid].claim_state.value for oid in object_ids}
        body = {"sector": sector, "object_ids": object_ids, "application_ids": app_ids, "proof_states": states}
        return ProjectionState(sector, object_ids, app_ids, states, digest(body))

    def factor_restatements(self, theorem_id: str, fragments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        theorem = self.objects[theorem_id]
        canonical_norm = " ".join(theorem.canonical_statement.lower().split())
        eliminated: list[str] = []
        retained: list[dict[str, Any]] = []
        for fragment in fragments:
            text = str(fragment.get("text", ""))
            unique_evidence = tuple(fragment.get("unique_evidence", ()))
            norm = " ".join(text.lower().split())
            if norm == canonical_norm and not unique_evidence:
                eliminated.append(str(fragment.get("fragment_id", digest(fragment)[:12])))
            else:
                retained.append({"fragment_id": fragment.get("fragment_id"), "context_delta": fragment.get("context_delta"), "unique_evidence": unique_evidence})
        theorem.eliminated_restatements.extend(x for x in eliminated if x not in theorem.eliminated_restatements)
        theorem.retained_context_deltas.extend(str(x["context_delta"]) for x in retained if x.get("context_delta") and str(x["context_delta"]) not in theorem.retained_context_deltas)
        return {"theorem_id": theorem_id, "eliminated": tuple(eliminated), "retained": tuple(retained)}

    def resolved_operators(self, theorem_id: str) -> tuple[str, ...]:
        if theorem_id not in self.objects:
            raise GraphViolation("THEOREM_UNKNOWN")
        theorem = self.objects[theorem_id]
        inherited: set[str] = set(theorem.operators.inherited)
        # Operator inheritance is restricted to typed dependency/refinement ancestors.
        for rel in self._incoming[theorem_id]:
            if rel.relation not in {RelationType.DEPENDS_ON, RelationType.REFINES}:
                continue
            parent = self.objects[rel.source_id]
            inherited.update(self.resolved_operators(parent.theorem_id))
        inherited -= set(theorem.operators.overridden)
        inherited -= set(theorem.operators.prohibited)
        return tuple(sorted((inherited | set(theorem.operators.local)) - set(theorem.operators.prohibited)))

    def marginal_value(self, theorem_id: str, duplicate_cost: int = 0) -> int:
        if theorem_id not in self.objects:
            raise GraphViolation("THEOREM_UNKNOWN")
        if duplicate_cost < 0:
            raise GraphViolation("DUPLICATE_COST_NEGATIVE")
        routed = sum(1 for a in self.applications.values() if a.theorem_id == theorem_id)
        dependents = len(self._outgoing[theorem_id])
        reuse = sum(1 for r in self.relations if r.source_id == theorem_id or r.target_id == theorem_id)
        return routed + dependents + reuse - duplicate_cost

    def recursive_density(self, redundant_narrative_mass: int) -> float:
        if redundant_narrative_mass < 0:
            raise GraphViolation("REDUNDANT_MASS_NEGATIVE")
        routed_reuse = len(self.applications)
        valid_edges = len(self.relations)
        computable_operations = len(self.transforms)
        proof_bearing = sum(len(x.proofs) + len(x.tests) + len(x.receipts) + len(x.counterexamples) for x in self.objects.values())
        cross_sector = len({(a.theorem_id, a.sector) for a in self.applications.values()})
        denominator = len(self.objects) + redundant_narrative_mass
        if denominator == 0:
            return 0.0
        return (routed_reuse + valid_edges + computable_operations + proof_bearing + cross_sector) / denominator

    def snapshot(self) -> dict[str, Any]:
        return {
            "objects": {k: {**asdict(v), "claim_state": v.claim_state.value, "object_root": v.object_root} for k, v in sorted(self.objects.items())},
            "relations": [asdict(r) for r in self.relations],
            "applications": {k: {**asdict(v), "claim_state": v.claim_state.value} for k, v in sorted(self.applications.items())},
            "events": [{**asdict(e), "relation": e.relation.value, "outcome": e.outcome.value, "prior_state": e.prior_state.value, "next_state": e.next_state.value} for e in self.event_log],
        }
