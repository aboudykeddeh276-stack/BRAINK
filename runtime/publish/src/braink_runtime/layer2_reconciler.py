from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Protocol
from .tot_safety import SafetyViolation

def _hash(v): return sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()

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

@dataclass(frozen=True)
class ActionReceipt:
    idempotency_key: str
    action: Action
    status: str
    observed: ObservedManifestation | None
    error: str | None

@dataclass(frozen=True)
class ReconcileReceipt:
    reconcile_id: str
    desired_root: str
    observed_before_root: str
    observed_after_root: str
    action_receipts: tuple[ActionReceipt,...]
    converged: bool
    status: str
    receipt_hash: str

class Actuator(Protocol):
    def execute(self, action: Action, idempotency_key: str) -> ObservedManifestation: ...

class Layer2Reconciler:
    def plan(self, desired: dict[str,DesiredManifestation], observed: dict[str,ObservedManifestation]) -> tuple[Action,...]:
        actions=[]
        for mid,d in sorted(desired.items()):
            if str(mid).strip().upper() in {'0','ZERO'}: raise SafetyViolation('ZERO_NOT_PERMITTED_AS_ADDRESS')
            if d.generation<=0: raise SafetyViolation('GENERATION_MUST_BE_POSITIVE')
            if not d.endpoint: raise SafetyViolation('ENDPOINT_REQUIRED')
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

    @staticmethod
    def _root(mapping) -> str:
        return _hash({k:asdict(v) for k,v in sorted(mapping.items())})

    def reconcile_once(self, desired: dict[str,DesiredManifestation], observed: dict[str,ObservedManifestation], actuator: Actuator) -> tuple[dict[str,ObservedManifestation], ReconcileReceipt]:
        before=dict(observed); plan=self.plan(desired,before); after=dict(before); receipts=[]
        desired_root=self._root(desired); before_root=self._root(before)
        reconcile_id=_hash({'desired_root':desired_root,'observed_before_root':before_root})
        status='PASS'
        for a in plan:
            key=_hash({'reconcile_id':reconcile_id,'action':asdict(a)})
            try:
                obs=actuator.execute(a,key)
                after[a.manifestation_id]=obs
                receipts.append(ActionReceipt(key,a,'APPLIED',obs,None))
            except Exception as exc:
                receipts.append(ActionReceipt(key,a,'FAILED',None,f'{type(exc).__name__}:{exc}'))
                status='PARTIAL_FAILURE'
                break
        conv=False
        if status=='PASS':
            conv=self.converged(desired,after)
            if not conv: status='NOT_CONVERGED'
        after_root=self._root(after)
        body={'reconcile_id':reconcile_id,'desired_root':desired_root,'observed_before_root':before_root,
              'observed_after_root':after_root,'action_receipts':[asdict(x) for x in receipts],
              'converged':conv,'status':status}
        return after, ReconcileReceipt(receipt_hash=_hash(body), **{**body,'action_receipts':tuple(receipts)})
