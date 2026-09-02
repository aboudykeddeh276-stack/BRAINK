from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Callable, Mapping, Optional
import json

from observer2_federation_r29 import Observer2Runtime
from observer2_resident_state_r29 import compare_federated_frames, derive_continuation


def _root(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Admission:
    decision: str
    reason: str
    evidence: Mapping[str, Any]

    @property
    def admitted(self) -> bool:
        return self.decision == "ADMIT"


class Observer2FederatedControlLoop:
    """Execute the resident Observer² environmental loop without merging observer and actuator authority.

    observer -> pre sample -> thinking -> mirror -> learning admission -> external actuator
    -> post sample -> compare -> continuation
    """

    def __init__(self, observer: Observer2Runtime) -> None:
        self.observer = observer

    def cycle(self, *,
              objective: str,
              think: Callable[[Mapping[str, Any]], Mapping[str, Any]],
              mirror: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
              learn: Callable[[Mapping[str, Any]], Admission],
              actuator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
              target: Callable[[Mapping[str, Any], Mapping[str, Any]], bool],
              continuation: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
        pre = self.observer.observe(continuation=continuation)
        pre_dict = pre.as_dict()
        candidate = dict(think(pre_dict))
        mirror_result = dict(mirror(candidate, pre_dict))
        admission = learn(mirror_result)

        execution: Mapping[str, Any]
        if admission.admitted:
            try:
                execution = {"status": "EXECUTED", "result": dict(actuator(candidate))}
            except Exception as exc:
                execution = {"status": "EXECUTION_ERROR", "error_type": type(exc).__name__, "error": str(exc)}
        else:
            execution = {"status": "NOT_EXECUTED", "reason": admission.reason}

        post = self.observer.observe(continuation=continuation)
        comparison = compare_federated_frames(pre, post)
        satisfied = bool(target(execution, comparison))
        successor = derive_continuation(pre, post, comparison, target_satisfied=satisfied, prior=continuation)

        core = {
            "schema": "kex.observer2.federated-control-cycle.r29",
            "objective": objective,
            "observer_id": pre.observer_id,
            "pre": pre_dict,
            "candidate": candidate,
            "mirror": mirror_result,
            "admission": asdict(admission),
            "execution": execution,
            "post": post.as_dict(),
            "comparison": comparison,
            "continuation": successor,
        }
        return {**core, "cycle_root": _root(core)}
