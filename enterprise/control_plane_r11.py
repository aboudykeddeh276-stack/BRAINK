from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable,Optional
from .runtime_state_machine import AuthorityState,execution_eligible
from .orc_runtime import Obligation

@dataclass(frozen=True)
class ControlDecision:
    obligation_id:str
    selected:bool
    reason:str
    score:float

def score(o:Obligation)->float:
    return 0.24*o.evidence_gap+0.22*o.risk+0.24*o.information_gain+0.20*o.unlock_value-0.18*o.effort

def select(obligations:Iterable[Obligation])->Optional[Obligation]:
    frontier=[o for o in obligations if o.executable and o.dependency_ready]
    if not frontier:return None
    return max(frontier,key=lambda o:(score(o),o.obligation_id))

def qualify_execution(*,mechanism_present:bool,binding_present:bool,state_target_present:bool,actuator_present:bool,receipt_path_present:bool,authority:AuthorityState):
    return execution_eligible(mechanism_present=mechanism_present,binding_present=binding_present,state_target_present=state_target_present,actuator_present=actuator_present,receipt_path_present=receipt_path_present,authority=authority)

# Public observer state is intentionally absent from execution eligibility.
