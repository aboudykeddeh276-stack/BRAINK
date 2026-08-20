"""BRAINK IL-LLM recursive semantic fabric with governed KEX representation.

This module is additive. It does not replace existing BTC or NativeChatBot runtimes.
Semantic identity is authoritative; KEX is a compact governed representation;
materialisations/projections are views and never redefine semantic truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


class FabricError(RuntimeError):
    pass


class SemanticConflict(FabricError):
    pass


class UnknownSemanticIdentity(FabricError):
    pass


class UnknownKEXIdentity(FabricError):
    pass


class ProjectionDepthError(FabricError):
    pass


class EvidenceClass(str, Enum):
    OBSERVED = "OBSERVED"
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNOBSERVED = "UNOBSERVED"
    SYNTHETIC = "SYNTHETIC"


@dataclass(frozen=True)
class SemanticObject:
    identity: str
    kind: str
    names: Tuple[str, ...] = ()
    definition: Optional[str] = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "identity": self.identity,
            "kind": self.kind,
            "names": sorted(set(self.names)),
            "definition": self.definition,
            "attributes": dict(sorted(self.attributes.items())),
        }


@dataclass(frozen=True)
class Relation:
    source: str
    predicate: str
    target: str
    scope: str = "global"
    observer: Optional[str] = None
    evidence: Optional[str] = None
    epoch: Optional[str] = None

    @property
    def identity(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return "relation://sha256/" + sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ObserverFrame:
    identity: str
    space: str
    observer: str
    interpretation: Mapping[str, Any]
    evidence: Tuple[str, ...] = ()
    epoch: Optional[str] = None


@dataclass(frozen=True)
class Continuation:
    identity: str
    coordinate: str
    observer: str
    logical_time: int = 0
    route: Tuple[str, ...] = ()
    return_route: Tuple[str, ...] = ()
    evidence_cursor: Optional[str] = None
    governance_scope: str = "default"
    state: Mapping[str, Any] = field(default_factory=dict)

    def advance(self, coordinate: str, *, via: Optional[str] = None,
                return_to: Optional[str] = None, evidence_cursor: Optional[str] = None,
                state_patch: Optional[Mapping[str, Any]] = None) -> "Continuation":
        route = self.route + ((via,) if via else ())
        returns = self.return_route + ((return_to,) if return_to else ())
        state = dict(self.state)
        if state_patch:
            state.update(state_patch)
        return replace(
            self,
            coordinate=coordinate,
            logical_time=self.logical_time + 1,
            route=route,
            return_route=returns,
            evidence_cursor=evidence_cursor or self.evidence_cursor,
            state=state,
        )


@dataclass(frozen=True)
class EvidenceRecord:
    identity: str
    subject: str
    producer: str
    classification: EvidenceClass
    payload_digest: str
    epoch: Optional[str] = None
    session: Optional[str] = None
    previous: Optional[str] = None


@dataclass(frozen=True)
class KEXBinding:
    kex_id: str
    semantic_id: str
    semantic_digest: str
    version: int = 1


class KEXRegistry:
    """Governed reversible mapping; deterministic digest is not treated as meaning."""

    def __init__(self) -> None:
        self._by_semantic: Dict[str, KEXBinding] = {}
        self._by_kex: Dict[str, KEXBinding] = {}

    @staticmethod
    def _digest(obj: SemanticObject) -> str:
        raw = json.dumps(obj.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return sha256(raw.encode()).hexdigest()

    def bind(self, obj: SemanticObject) -> KEXBinding:
        digest = self._digest(obj)
        existing = self._by_semantic.get(obj.identity)
        if existing:
            if existing.semantic_digest != digest:
                raise SemanticConflict(f"semantic object mutated after KEX binding: {obj.identity}")
            return existing
        # KEX code is compact but reversible only through this governed registry.
        code = "KEX:" + sha256(("BRAINK|" + obj.identity + "|" + digest).encode()).hexdigest()[:32].upper()
        binding = KEXBinding(code, obj.identity, digest)
        if code in self._by_kex and self._by_kex[code].semantic_id != obj.identity:
            raise SemanticConflict(f"KEX collision: {code}")
        self._by_semantic[obj.identity] = binding
        self._by_kex[code] = binding
        return binding

    def resolve(self, kex_id: str) -> KEXBinding:
        try:
            return self._by_kex[kex_id]
        except KeyError as exc:
            raise UnknownKEXIdentity(kex_id) from exc


class ILFabric:
    """One semantic graph supporting many spaces, observers and continuations."""

    def __init__(self) -> None:
        self.objects: Dict[str, SemanticObject] = {}
        self.aliases: Dict[str, str] = {}
        self.relations: Dict[str, Relation] = {}
        self.frames: Dict[str, ObserverFrame] = {}
        self.continuations: Dict[str, Continuation] = {}
        self.evidence: Dict[str, EvidenceRecord] = {}
        self.kex = KEXRegistry()

    def register(self, obj: SemanticObject) -> SemanticObject:
        existing = self.objects.get(obj.identity)
        if existing and existing != obj:
            raise SemanticConflict(f"identity already has different semantics: {obj.identity}")
        self.objects[obj.identity] = obj
        for name in obj.names:
            current = self.aliases.get(name)
            if current and current != obj.identity:
                raise SemanticConflict(f"alias collision: {name}")
            self.aliases[name] = obj.identity
        return obj

    def resolve(self, identity_or_alias: str) -> SemanticObject:
        semantic_id = self.aliases.get(identity_or_alias, identity_or_alias)
        try:
            return self.objects[semantic_id]
        except KeyError as exc:
            raise UnknownSemanticIdentity(identity_or_alias) from exc

    def relate(self, relation: Relation) -> Relation:
        self.resolve(relation.source)
        self.resolve(relation.predicate)
        self.resolve(relation.target)
        self.relations.setdefault(relation.identity, relation)
        return relation

    def observe(self, frame: ObserverFrame) -> ObserverFrame:
        self.resolve(frame.identity)
        self.resolve(frame.space)
        self.resolve(frame.observer)
        self.frames[f"{frame.identity}|{frame.space}|{frame.observer}|{frame.epoch or ''}"] = frame
        return frame

    def put_continuation(self, continuation: Continuation) -> Continuation:
        self.resolve(continuation.coordinate)
        self.resolve(continuation.observer)
        self.continuations[continuation.identity] = continuation
        return continuation

    def append_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        self.resolve(record.subject)
        if record.previous and record.previous not in self.evidence:
            raise FabricError(f"unknown previous evidence: {record.previous}")
        self.evidence[record.identity] = record
        return record

    def encode(self, semantic_id: str) -> KEXBinding:
        return self.kex.bind(self.resolve(semantic_id))

    def decode(self, kex_id: str, *, depth: int = 1) -> Mapping[str, Any]:
        if depth < 1:
            raise ProjectionDepthError("depth must be >= 1")
        binding = self.kex.resolve(kex_id)
        root = self.resolve(binding.semantic_id)
        result: Dict[str, Any] = {"kex": kex_id, "semantic": root.canonical_payload(), "relations": []}
        if depth == 1:
            return result
        frontier = {root.identity}
        visited = {root.identity}
        for _ in range(depth - 1):
            nxt = set()
            for rel in self.relations.values():
                if rel.source in frontier:
                    result["relations"].append(rel.__dict__)
                    if rel.target not in visited:
                        visited.add(rel.target)
                        nxt.add(rel.target)
            frontier = nxt
            if not frontier:
                break
        result["expanded"] = [self.resolve(x).canonical_payload() for x in sorted(visited) if x != root.identity]
        return result

    def traverse(self, source: str, *, predicate: Optional[str] = None,
                 observer: Optional[str] = None, epoch: Optional[str] = None) -> Tuple[Relation, ...]:
        sid = self.resolve(source).identity
        matches = []
        for rel in self.relations.values():
            if rel.source != sid:
                continue
            if predicate and rel.predicate != self.resolve(predicate).identity:
                continue
            if observer and rel.observer not in (None, observer):
                continue
            if epoch and rel.epoch not in (None, epoch):
                continue
            matches.append(rel)
        return tuple(matches)

    def verify_evidence_scope(self, evidence_id: str, *, subject: str,
                              epoch: Optional[str] = None,
                              session: Optional[str] = None,
                              allow_synthetic: bool = False) -> bool:
        record = self.evidence[evidence_id]
        if record.subject != self.resolve(subject).identity:
            return False
        if epoch is not None and record.epoch != epoch:
            return False
        if session is not None and record.session != session:
            return False
        if not allow_synthetic and record.classification == EvidenceClass.SYNTHETIC:
            return False
        return record.classification not in {EvidenceClass.FAILED, EvidenceClass.BLOCKED, EvidenceClass.UNOBSERVED}


def build_btc_semantic_seed() -> ILFabric:
    """Minimal BTC qualification graph proving the architecture without replacing BTC runtime."""
    f = ILFabric()
    objects = [
        SemanticObject("il-llm://braink/root", "space", ("BRAINK",)),
        SemanticObject("il-llm://btc", "space", ("BTC",)),
        SemanticObject("il-llm://authority", "space", ("Authority",)),
        SemanticObject("il-llm://proof", "space", ("Proof",)),
        SemanticObject("il-llm://temporal", "space", ("Temporal",)),
        SemanticObject("il-llm://planning", "space", ("Planning",)),
        SemanticObject("il-llm://execution", "space", ("Execution",)),
        SemanticObject("il-llm://carrier", "space", ("Carrier",)),
        SemanticObject("il-llm://memory", "space", ("Memory",)),
        SemanticObject("il-llm://projection/hci", "space", ("HCI",)),
        SemanticObject("il-llm://governance", "space", ("Governance",)),
        SemanticObject("il-llm://observer/bitcoin-core", "observer", ("Bitcoin Core observer",)),
        SemanticObject("il-llm://observer/verifier", "observer", ("Verifier",)),
        SemanticObject("il-llm://predicate/produces", "predicate", ("PRODUCES",)),
        SemanticObject("il-llm://predicate/requires-authority", "predicate", ("REQUIRES_AUTHORITY",)),
        SemanticObject("il-llm://predicate/instance-of", "predicate", ("INSTANCE_OF",)),
        SemanticObject("il-llm://predicate/proven-by", "predicate", ("PROVEN_BY",)),
        SemanticObject("il-llm://predicate/supersedes", "predicate", ("SUPERSEDES",)),
        SemanticObject("il-llm://predicate/enables", "predicate", ("ENABLES",)),
        SemanticObject("il-llm://btc/core/bitcoin-core", "software", ("Bitcoin Core",)),
        SemanticObject("il-llm://btc/work/getblocktemplate", "property", ("Core GBT",)),
        SemanticObject("il-llm://authority/class/bitcoin-core", "authority-class", ("Bitcoin Core authority",)),
        SemanticObject("il-llm://authority/instance/bitcoin-core-mainnet", "authority-instance", ("Bitcoin Core mainnet",)),
    ]
    for obj in objects:
        f.register(obj)
    f.relate(Relation("il-llm://btc/core/bitcoin-core", "il-llm://predicate/produces", "il-llm://btc/work/getblocktemplate"))
    f.relate(Relation("il-llm://btc/work/getblocktemplate", "il-llm://predicate/requires-authority", "il-llm://authority/class/bitcoin-core"))
    f.relate(Relation("il-llm://authority/instance/bitcoin-core-mainnet", "il-llm://predicate/instance-of", "il-llm://authority/class/bitcoin-core"))
    return f
