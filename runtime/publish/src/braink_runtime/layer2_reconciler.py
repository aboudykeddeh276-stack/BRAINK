from __future__ import annotations
from dataclasses import dataclass
from .tot_safety import SafetyViolation

@dataclass(frozen=True)
class DesiredManifestation:
    manifestation_id: str
    endpoint: str
    generation: int
    state: str='ATTACHED'

@dataclass(frozen=True)
class ObservedManifestation:
    manifestation_id: str
    endpoint: str
    generation: int
    state: str

@dataclass(frozen=True)
class Action:
    kind: str
    manifestation_id: str
    endpoint: str
    generation: int

class Layer2Reconciler:
    def plan(self, desired: dict[str,DesiredManifestation], observed: dict[str,ObservedManifestation]) -> tuple[Action,...]:
        actions=[]
        for mid,d in sorted(desired.items()):
            if str(mid).strip().upper() in {'0','ZERO'}: raise SafetyViolation('ZERO_NOT_PERMITTED_AS_ADDRESS')
            if d.generation<=0: raise SafetyViolation('GENERATION_MUST_BE_POSITIVE')
            o=observed.get(mid)
            if o is None:
                actions.append(Action('MATERIALISE',mid,d.endpoint,d.generation)); continue
            if o.generation>d.generation:
                raise SafetyViolation('OBSERVED_GENERATION_AHEAD_OF_DESIRED')
            if o.generation<d.generation or o.endpoint!=d.endpoint or o.state!=d.state:
                actions.append(Action('REPLACE',mid,d.endpoint,d.generation))
        for mid,o in sorted(observed.items()):
            if mid not in desired and o.state!='DETACHED':
                actions.append(Action('DETACH',mid,o.endpoint,o.generation+1))
        return tuple(actions)

    def converged(self, desired, observed) -> bool:
        return self.plan(desired,observed)==()
