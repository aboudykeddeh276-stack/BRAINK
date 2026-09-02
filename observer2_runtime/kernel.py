from __future__ import annotations

import abc
import copy
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Mapping, Tuple


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(data).hexdigest()


class ToroidalCoordinate:
    __slots__ = ("_x", "_y", "_z")

    def __init__(self, x: int, y: int, z: int):
        if x == 0 or y == 0 or z == 0:
            raise ValueError("Zeroless addressing invariant violation")
        object.__setattr__(self, "_x", x)
        object.__setattr__(self, "_y", y)
        object.__setattr__(self, "_z", z)

    @property
    def vector(self) -> Tuple[int, int, int]:
        return self._x, self._y, self._z

    def serialize(self) -> str:
        return f"{self._x},{self._y},{self._z}"

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Immutable Spatial Vector")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Immutable Spatial Vector")


@dataclass(frozen=True)
class SignalPacket:
    source: str
    destination: str
    signal_type: str
    payload: Mapping[str, Any]
    sequence: int

    @classmethod
    def build(cls, source: str, destination: str, signal_type: str, payload: Dict[str, Any], sequence: int) -> "SignalPacket":
        return cls(source, destination, signal_type, copy.deepcopy(payload), sequence)

    def digest(self) -> str:
        return sha256_hex({
            "source": self.source,
            "destination": self.destination,
            "signal_type": self.signal_type,
            "payload": self.payload,
            "sequence": self.sequence,
        })


@dataclass(frozen=True)
class ObserverFrame:
    plane_id: str
    state_hash: str
    observed_state: Mapping[str, Any]
    evidence_digest: str


@dataclass(frozen=True)
class CandidateState:
    candidate_hash: str
    proposed_state: Mapping[str, Any]
    derived_from: str
    mirror_only: bool = True


@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason: str
    policy_digest: str


@dataclass(frozen=True)
class ActuationReceipt:
    actuator_id: str
    attempted: bool
    accepted: bool
    receipt_digest: str
    result: Mapping[str, Any]


@dataclass(frozen=True)
class EnvironmentalDelta:
    before_hash: str
    after_hash: str
    changed: bool
    delta: Mapping[str, Any]


@dataclass(frozen=True)
class Continuation:
    action: str
    reason: str
    derived_from_delta: str


class VirtualExecutionPlane(abc.ABC):
    @abc.abstractmethod
    def observe_state(self) -> Dict[str, Any]: ...

    @abc.abstractmethod
    def derive_candidate(self, pre_frame: ObserverFrame, signal: SignalPacket) -> CandidateState: ...

    @abc.abstractmethod
    def actuate(self, candidate: CandidateState) -> ActuationReceipt: ...


class StatefulExecutionPlane(VirtualExecutionPlane):
    plane_label: Final[str] = "GENERIC"

    def __init__(self, initial_state: Dict[str, Any]):
        self._state = copy.deepcopy(initial_state)

    def observe_state(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)

    def _candidate(self, pre_frame: ObserverFrame, proposed: Dict[str, Any]) -> CandidateState:
        proposed_copy = copy.deepcopy(proposed)
        return CandidateState(sha256_hex(proposed_copy), proposed_copy, pre_frame.state_hash, True)

    def _commit(self, candidate: CandidateState, result: Dict[str, Any]) -> ActuationReceipt:
        self._state = copy.deepcopy(dict(candidate.proposed_state))
        receipt_body = {"actuator_id": self.plane_label, "candidate_hash": candidate.candidate_hash, "result": result}
        return ActuationReceipt(self.plane_label, True, True, sha256_hex(receipt_body), copy.deepcopy(result))


class WebExecutionPlane(StatefulExecutionPlane):
    plane_label = "WEB_ACTUATOR"

    def __init__(self):
        super().__init__({"target_uri": "about:blank", "action": "IDLE", "status_code": 200})

    def derive_candidate(self, pre_frame: ObserverFrame, signal: SignalPacket) -> CandidateState:
        proposed = dict(pre_frame.observed_state)
        proposed["target_uri"] = signal.payload.get("URL", "about:blank")
        proposed["action"] = signal.payload.get("ACTION", signal.signal_type)
        return self._candidate(pre_frame, proposed)

    def actuate(self, candidate: CandidateState) -> ActuationReceipt:
        return self._commit(candidate, {"plane": "WEB_PLANE", "target_uri": candidate.proposed_state["target_uri"]})


class AndroidExecutionPlane(StatefulExecutionPlane):
    plane_label = "ANDROID_ACTUATOR"

    def __init__(self):
        super().__init__({"package_id": None, "intent": "android.intent.action.MAIN", "status": "IDLE"})

    def derive_candidate(self, pre_frame: ObserverFrame, signal: SignalPacket) -> CandidateState:
        proposed = dict(pre_frame.observed_state)
        proposed.update({
            "package_id": signal.payload.get("PACKAGE_ID"),
            "intent": signal.payload.get("INTENT", "android.intent.action.MAIN"),
            "status": "REQUESTED",
        })
        return self._candidate(pre_frame, proposed)

    def actuate(self, candidate: CandidateState) -> ActuationReceipt:
        if not candidate.proposed_state.get("package_id"):
            body = {"actuator_id": self.plane_label, "candidate_hash": candidate.candidate_hash, "error": "MISSING_PACKAGE_ID"}
            return ActuationReceipt(self.plane_label, True, False, sha256_hex(body), {"error": "MISSING_PACKAGE_ID"})
        result = {
            "plane": "APK_PLANE",
            "package_id": candidate.proposed_state["package_id"],
            "intent": candidate.proposed_state["intent"],
        }
        return self._commit(candidate, result)


class DarwinExecutionPlane(StatefulExecutionPlane):
    plane_label = "DARWIN_ACTUATOR"

    def __init__(self):
        super().__init__({"bundle_id": None, "symbol": "main", "status": "IDLE"})

    def derive_candidate(self, pre_frame: ObserverFrame, signal: SignalPacket) -> CandidateState:
        proposed = dict(pre_frame.observed_state)
        proposed.update({
            "bundle_id": signal.payload.get("BUNDLE_ID", "au.com.keddeh.native"),
            "symbol": signal.payload.get("SYMBOL", "main"),
            "status": "REQUESTED",
        })
        return self._candidate(pre_frame, proposed)

    def actuate(self, candidate: CandidateState) -> ActuationReceipt:
        result = {
            "plane": "APPLE_PLANE",
            "bundle_id": candidate.proposed_state["bundle_id"],
            "magic_header": "0xFEEDFACF",
        }
        return self._commit(candidate, result)


class Observer2:
    def observe(self, plane_id: str, plane: VirtualExecutionPlane) -> ObserverFrame:
        observed = plane.observe_state()
        digest = sha256_hex(observed)
        return ObserverFrame(plane_id, digest, observed, digest)


class LearningAdmissionGate:
    POLICY = {"candidate_must_be_mirror_only": True, "resident_capability_required": True}

    def evaluate(self, signal: SignalPacket, candidate: CandidateState, capabilities: Mapping[str, Any]) -> AdmissionDecision:
        policy_digest = sha256_hex(self.POLICY)
        if not candidate.mirror_only:
            return AdmissionDecision(False, "CANDIDATE_NOT_MIRROR_ONLY", policy_digest)
        capability = capabilities.get(signal.destination)
        if not capability or not capability.get("actuator"):
            return AdmissionDecision(False, "NO_RESIDENT_ACTUATOR", policy_digest)
        return AdmissionDecision(True, "ADMITTED", policy_digest)


class KexMicroKernelCore:
    def __init__(self, cryptographic_anchor: str):
        self._anchor = cryptographic_anchor.encode("utf-8")
        self.k_drive_origin = ToroidalCoordinate(1, 1, 1)
        self.semantic_volume_ratio = 297 / 1000
        self._address_space: Dict[str, Dict[str, Any]] = {}
        self._execution_planes: Dict[str, VirtualExecutionPlane] = {
            "WEB_PLANE": WebExecutionPlane(),
            "APK_PLANE": AndroidExecutionPlane(),
            "APPLE_PLANE": DarwinExecutionPlane(),
        }
        self._resident_capabilities: Dict[str, Dict[str, Any]] = {}
        self._signal_sequence = 0
        self._signal_lineage_ledger: List[Dict[str, Any]] = []
        self._observer = Observer2()
        self._admission_gate = LearningAdmissionGate()
        self._initialize_subsystem_matrix()

    def _initialize_subsystem_matrix(self) -> None:
        bindings = [
            (ToroidalCoordinate(1, 1, 2), "WEB_PLANE"),
            (ToroidalCoordinate(1, 2, 1), "APK_PLANE"),
            (ToroidalCoordinate(2, 1, 1), "APPLE_PLANE"),
        ]
        for coord, plane_id in bindings:
            self.bind_subsystem_coordinate(coord, plane_id)
            plane = self._execution_planes[plane_id]
            self._resident_capabilities[plane_id] = {
                "observer": plane.observe_state,
                "candidate": plane.derive_candidate,
                "actuator": plane.actuate,
            }

    def bind_subsystem_coordinate(self, coord: ToroidalCoordinate, plane_id: str) -> None:
        spatial_key = coord.serialize()
        if spatial_key in self._address_space:
            raise KeyError(f"Spatial collision: {spatial_key}")
        identity = {"coordinate": spatial_key, "plane_identity": plane_id, "allocation_state": "ACTIVE"}
        token = hmac.new(self._anchor, canonical_bytes(identity), hashlib.sha256).hexdigest()
        self._address_space[spatial_key] = {**identity, "integrity_token": token}

    def generate_deterministic_proof(self) -> str:
        return sha256_hex({
            "address_space": self._address_space,
            "signal_sequence": self._signal_sequence,
            "signal_lineage_ledger": self._signal_lineage_ledger,
        })

    def _derive_delta(self, pre: ObserverFrame, post: ObserverFrame) -> EnvironmentalDelta:
        keys = set(pre.observed_state) | set(post.observed_state)
        delta: Dict[str, Any] = {}
        for key in sorted(keys):
            before = pre.observed_state.get(key)
            after = post.observed_state.get(key)
            if before != after:
                delta[key] = {"before": before, "after": after}
        return EnvironmentalDelta(pre.state_hash, post.state_hash, bool(delta), delta)

    def _derive_continuation(self, receipt: ActuationReceipt, delta: EnvironmentalDelta) -> Continuation:
        if not receipt.accepted:
            return Continuation("RESOLVE_ACTUATOR_FAILURE", "ACTUATOR_REJECTED", delta.after_hash)
        if not delta.changed:
            return Continuation("RESOLVE_NO_OBSERVED_MUTATION", "ACTUATION_WITHOUT_ENVIRONMENTAL_DELTA", delta.after_hash)
        return Continuation("FOLLOW_CREATED_DESCENDANTS", "OBSERVED_MUTATION_CONFIRMED", delta.after_hash)

    def orchestrate_signal(self, source_plane: str, destination_plane: str, signal_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if source_plane not in self._execution_planes:
            return {"STATUS": "PROPAGATION_REJECTED", "REASON": "UNKNOWN_SOURCE_PLANE"}
        if destination_plane not in self._execution_planes:
            return {"STATUS": "PROPAGATION_REJECTED", "REASON": "UNKNOWN_DESTINATION_PLANE"}

        self._signal_sequence += 1
        signal = SignalPacket.build(source_plane, destination_plane, signal_type, payload, self._signal_sequence)
        plane = self._execution_planes[destination_plane]
        pre = self._observer.observe(destination_plane, plane)
        candidate = plane.derive_candidate(pre, signal)
        admission = self._admission_gate.evaluate(signal, candidate, self._resident_capabilities)

        if not admission.admitted:
            record = {
                "SEQUENCE": signal.sequence,
                "SIGNAL_DIGEST": signal.digest(),
                "OBSERVER_PRE": {"STATE_HASH": pre.state_hash},
                "MIRROR_CANDIDATE": {"HASH": candidate.candidate_hash, "AUTHORITATIVE": False},
                "ADMISSION": {"ADMITTED": False, "REASON": admission.reason, "POLICY_DIGEST": admission.policy_digest},
                "CONTINUATION": {"ACTION": "RESOLVE_ADMISSION_FAILURE", "REASON": admission.reason},
            }
            self._signal_lineage_ledger.append(record)
            return {"STATUS": "ADMISSION_REJECTED", "LINEAGE_RECORD": record, "COMPOSITE_STATE_PROOF": self.generate_deterministic_proof()}

        receipt = plane.actuate(candidate)
        post = self._observer.observe(destination_plane, plane)
        delta = self._derive_delta(pre, post)
        continuation = self._derive_continuation(receipt, delta)
        source_state = self._observer.observe(source_plane, self._execution_planes[source_plane]).state_hash
        transition_proof_body = {
            "sequence": signal.sequence,
            "source_state": source_state,
            "destination_state_before": pre.state_hash,
            "signal_digest": signal.digest(),
            "destination_state_after": post.state_hash,
            "actuator_receipt": receipt.receipt_digest,
            "admission_policy": admission.policy_digest,
            "continuation": continuation.action,
        }
        transition_hmac = hmac.new(self._anchor, canonical_bytes(transition_proof_body), hashlib.sha256).hexdigest()

        record = {
            "SEQUENCE": signal.sequence,
            "SIGNAL": {"SOURCE": source_plane, "DESTINATION": destination_plane, "TYPE": signal_type, "DIGEST": signal.digest()},
            "OBSERVER_PRE": {"STATE_HASH": pre.state_hash, "EVIDENCE_DIGEST": pre.evidence_digest},
            "MIRROR_CANDIDATE": {"HASH": candidate.candidate_hash, "DERIVED_FROM": candidate.derived_from, "AUTHORITATIVE": False},
            "ADMISSION": {"ADMITTED": True, "REASON": admission.reason, "POLICY_DIGEST": admission.policy_digest},
            "ACTUATION": {"ACTUATOR_ID": receipt.actuator_id, "ATTEMPTED": receipt.attempted, "ACCEPTED": receipt.accepted, "RECEIPT_DIGEST": receipt.receipt_digest},
            "OBSERVER_POST": {"STATE_HASH": post.state_hash, "EVIDENCE_DIGEST": post.evidence_digest},
            "ENVIRONMENT_DELTA": {"CHANGED": delta.changed, "DELTA": dict(delta.delta)},
            "CONTINUATION": {"ACTION": continuation.action, "REASON": continuation.reason, "DERIVED_FROM_DELTA": continuation.derived_from_delta},
            "TRANSITION_HMAC": transition_hmac,
        }
        self._signal_lineage_ledger.append(record)
        return {"STATUS": "SIGNAL_PROCESSED", "LINEAGE_RECORD": record, "COMPOSITE_STATE_PROOF": self.generate_deterministic_proof()}

    def status(self) -> Dict[str, Any]:
        return {
            "KERNEL_FABRIC": "ONLINE",
            "SEMANTIC_VOLUME_CONSTRAINT": self.semantic_volume_ratio,
            "RESIDENT_CAPABILITIES": sorted(self._resident_capabilities.keys()),
            "SIGNAL_SEQUENCE": self._signal_sequence,
            "STATE_INTEGRITY_PROVING_HASH": self.generate_deterministic_proof(),
        }


class SovereignConsoleInterface:
    def __init__(self):
        anchor = os.environ.get("KEX_OBSERVER2_ANCHOR", "DEV_NONSECRET_ANCHOR")
        self.kernel = KexMicroKernelCore(anchor)

    def dispatch_input_stream(self, command_string: str) -> str:
        tokens = command_string.strip().split()
        if not tokens:
            return json.dumps({"STATUS": "EMPTY_STREAM_VECTOR"}, indent=2)
        instruction = tokens[0].upper()
        if instruction == "SYS_STATUS":
            return json.dumps(self.kernel.status(), indent=2)
        if instruction == "SIGNAL":
            if len(tokens) < 5:
                return json.dumps({"STATUS": "ERROR", "MESSAGE": "Usage: SIGNAL <source> <destination> <type> <payload_arg>"}, indent=2)
            source, destination, signal_type, arg = tokens[1:5]
            if destination == "APK_PLANE":
                payload = {"PACKAGE_ID": arg, "INTENT": "android.intent.action.VIEW"}
            elif destination == "WEB_PLANE":
                payload = {"URL": arg, "ACTION": "RENDER_ISOLATED"}
            elif destination == "APPLE_PLANE":
                payload = {"BUNDLE_ID": arg, "SYMBOL": "start_execution_loop"}
            else:
                payload = {"VALUE": arg}
            return json.dumps(self.kernel.orchestrate_signal(source, destination, signal_type, payload), indent=2)
        return json.dumps({"STATUS": "RESOLVED_FAIL_STATE", "CODE": "0x0FF", "INPUT_DUMP": command_string}, indent=2)


def main() -> None:
    console = SovereignConsoleInterface()
    print("KEX/BRAINK Observer² Microkernel v1.9")
    while True:
        try:
            user_input = input("KEX_v1.9_CORE> ")
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            print(console.dispatch_input_stream(user_input))
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == "__main__":
    main()
