from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Mapping, Optional
import json

from observer2_federation_r29 import FederatedFrame, Observer2Runtime


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class EvidenceAction:
    action_id: str
    observer_id: str
    frame_root_sha256: str
    objective: str
    recommendation: str
    authority: str = "EVIDENCE_ONLY_NO_ACTUATION"


class EvidenceOnlyActionLane:
    """Produces candidate actions as evidence; deliberately has no mutation/actuation method."""

    def derive(self, frame: FederatedFrame, *, objective: str, recommendation: str) -> EvidenceAction:
        material = {
            "observer_id": frame.observer_id,
            "frame_root_sha256": frame.environment_root_sha256,
            "objective": objective,
            "recommendation": recommendation,
        }
        return EvidenceAction(
            action_id="action://evidence/" + sha256(_canon(material)).hexdigest()[:24],
            observer_id=frame.observer_id,
            frame_root_sha256=frame.environment_root_sha256,
            objective=objective,
            recommendation=recommendation,
        )


class RecursiveObserverOperator:
    """Observer² outer operator: observe → derive evidence → return continuation."""

    def __init__(self, observer: Observer2Runtime, lane: Optional[EvidenceOnlyActionLane] = None) -> None:
        self.observer = observer
        self.lane = lane or EvidenceOnlyActionLane()

    def cycle(self, *, objective: str, recommendation: str,
              continuation: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
        frame = self.observer.observe(continuation=continuation)
        action = self.lane.derive(frame, objective=objective, recommendation=recommendation)
        return {
            "schema": "kex.observer2.operator-cycle.r29",
            "frame": frame.as_dict(),
            "evidence_action": asdict(action),
            "continuation": {
                **dict(continuation or {}),
                "observer_id": frame.observer_id,
                "last_environment_root_sha256": frame.environment_root_sha256,
                "next_route": "FOLLOW_SUCCESSOR_STATE",
            },
        }
