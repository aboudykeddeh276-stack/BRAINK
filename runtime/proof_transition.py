"""BRAINK Proof-Bearing Transition Contract v40."""
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import FrozenSet, Mapping, Optional, Tuple

class EvidenceClass(IntEnum):
    UNOBSERVED=0; INFERRED=10; UNTESTED=20; OBSERVED=30; SOURCE_VERIFIED=40; TESTED=50; BLOCKED=60; FAILED=70; SUPERSEDED=80
class Outcome(str,Enum):
    NONE="NONE"; BLOCKED="BLOCKED"; FAILED="FAILED"; SUPERSEDED="SUPERSEDED"
class TransitionDecision(str,Enum):
    RETRY_ALLOWED="RETRY_ALLOWED"; NO_RETRY_UNCHANGED_PRECONDITION="NO_RETRY_UNCHANGED_PRECONDITION"
    NO_RETRY_IRRELEVANT_DELTA="NO_RETRY_IRRELEVANT_DELTA"; NO_RETRY_OPERATION_MISMATCH="NO_RETRY_OPERATION_MISMATCH"
    NO_RETRY_FAILURE_MISMATCH="NO_RETRY_FAILURE_MISMATCH"; NO_RETRY_BUDGET_EXHAUSTED="NO_RETRY_BUDGET_EXHAUSTED"
    NO_RETRY_CAUSAL_LINK="NO_RETRY_CAUSAL_LINK"; NO_RETRY_TERMINAL_LATCH="NO_RETRY_TERMINAL_LATCH"
STAGE_ORDER={"CARRIER":0,"BITCOIN_CORE":1,"TEMPLATE":2,"MINER":3,"SUBMISSION":4}
LEGAL_TRANSITIONS={"UNOBSERVED":frozenset({"CANDIDATE","BLOCKED"}),"CANDIDATE":frozenset({"TESTED","BLOCKED","FAILED","SUPERSEDED"}),"TESTED":frozenset({"QUALIFIED","BLOCKED","FAILED","SUPERSEDED"}),"QUALIFIED":frozenset({"BLOCKED","SUPERSEDED"}),"BITCOIN_CORE_QUALIFIED":frozenset({"BLOCKED","TEMPLATE_ACQUIRED","SUPERSEDED"}),"TEMPLATE_ACQUIRED":frozenset({"MINING_ACTIVE","BLOCKED","FAILED","SUPERSEDED"}),"MINING_ACTIVE":frozenset({"CANDIDATE_FOUND","BLOCKED","FAILED","SUPERSEDED"}),"CANDIDATE_FOUND":frozenset({"SUBMISSION_ACCEPTED","SUBMISSION_REJECTED","BLOCKED"})}
MIN_EVIDENCE={"TESTED":EvidenceClass.TESTED,"QUALIFIED":EvidenceClass.TESTED,"TEMPLATE_ACQUIRED":EvidenceClass.OBSERVED,"MINING_ACTIVE":EvidenceClass.OBSERVED,"CANDIDATE_FOUND":EvidenceClass.TESTED,"SUBMISSION_ACCEPTED":EvidenceClass.OBSERVED}
@dataclass(frozen=True)
class EvidenceProvenance:
    producer:str; method:str; reference:str; scope:str; digest:Optional[str]=None; digest_algorithm:Optional[str]=None
@dataclass(frozen=True)
class RetryContext:
    operation_fingerprint:str; failure_fingerprint:str; prerequisites:Mapping[str,str]
    relevant_prerequisites:FrozenSet[str]=field(default_factory=frozenset); causal_prerequisites:Optional[FrozenSet[str]]=None
    retry_count:int=0; retry_budget:int=1; failure_epoch:str="epoch-1"; terminal_latched:bool=False
@dataclass(frozen=True)
class Transition:
    operation_id:str; operation_fingerprint:str; subject:str; subject_revision:str; evidence_revision:str
    environment_id:str; environment_revision:str; evidence_class:EvidenceClass; prior_state:str; resulting_state:str
    provenance:EvidenceProvenance; attempt_id:str; evidence_attempt_id:str; attempt_sequence:int; evidence_sequence:int
    stage:str="MINER"; prior_stage:Optional[str]=None; evidence_scope:Optional[str]=None; failure_scope:Optional[str]=None
    outcome:Outcome=Outcome.NONE; superseded_by:Optional[str]=None
@dataclass(frozen=True)
class Qualification:
    accepted:bool; reason:str; preserved_prior_state:str

def _changed(a,b):
    keys=set(a)|set(b); return {k for k in keys if a.get(k)!=b.get(k)}
def decide_retry(previous:RetryContext,current:RetryContext)->TransitionDecision:
    if previous.operation_fingerprint!=current.operation_fingerprint:return TransitionDecision.NO_RETRY_OPERATION_MISMATCH
    if previous.failure_fingerprint!=current.failure_fingerprint:return TransitionDecision.NO_RETRY_FAILURE_MISMATCH
    if previous.failure_epoch!=current.failure_epoch:return TransitionDecision.NO_RETRY_FAILURE_MISMATCH
    if previous.retry_count>=previous.retry_budget:return TransitionDecision.NO_RETRY_BUDGET_EXHAUSTED
    changed=_changed(previous.prerequisites,current.prerequisites)
    if not changed:return TransitionDecision.NO_RETRY_UNCHANGED_PRECONDITION
    relevant=changed & previous.relevant_prerequisites & current.relevant_prerequisites
    if not relevant:return TransitionDecision.NO_RETRY_IRRELEVANT_DELTA
    prev_causal=previous.relevant_prerequisites if previous.causal_prerequisites is None else previous.causal_prerequisites
    curr_causal=current.relevant_prerequisites if current.causal_prerequisites is None else current.causal_prerequisites
    causal=relevant & prev_causal & curr_causal
    if not causal:return TransitionDecision.NO_RETRY_CAUSAL_LINK
    if previous.terminal_latched and not causal:return TransitionDecision.NO_RETRY_TERMINAL_LATCH
    return TransitionDecision.RETRY_ALLOWED

def qualify_transition(t:Transition)->Qualification:
    p=t.prior_state
    required=(t.operation_id,t.operation_fingerprint,t.subject,t.subject_revision,t.evidence_revision,t.environment_id,t.environment_revision,t.attempt_id,t.evidence_attempt_id,t.provenance.producer,t.provenance.method,t.provenance.reference,t.provenance.scope,t.stage)
    if any(not x for x in required):return Qualification(False,"INCOMPLETE_PROVENANCE_ENVELOPE",p)
    if t.subject_revision!=t.evidence_revision:return Qualification(False,"SUBJECT_EVIDENCE_REVISION_MISMATCH",p)
    if t.attempt_id!=t.evidence_attempt_id:return Qualification(False,"EVIDENCE_ATTEMPT_REPLAY_OR_MISBIND",p)
    if t.attempt_sequence<1 or t.evidence_sequence<1 or t.evidence_sequence<t.attempt_sequence:return Qualification(False,"INVALID_TEMPORAL_SEQUENCE",p)
    if t.stage not in STAGE_ORDER:return Qualification(False,"UNKNOWN_STAGE",p)
    if t.prior_stage and STAGE_ORDER[t.stage]-STAGE_ORDER.get(t.prior_stage,-99)>1:return Qualification(False,"STAGE_SKIP",p)
    if t.evidence_scope and t.evidence_scope!=t.provenance.scope:return Qualification(False,"EVIDENCE_SCOPE_MISMATCH",p)
    if bool(t.provenance.digest)!=bool(t.provenance.digest_algorithm):return Qualification(False,"INCOMPLETE_EVIDENCE_DIGEST",p)
    legal=LEGAL_TRANSITIONS.get(p)
    if legal is not None and t.resulting_state not in legal:return Qualification(False,"ILLEGAL_STATE_TRANSITION",p)
    if (t.outcome is Outcome.BLOCKED or t.evidence_class is EvidenceClass.BLOCKED) and t.failure_scope=="CARRIER_BEFORE_EXECUTION" and t.resulting_state=="FAILED":return Qualification(False,"CARRIER_BLOCK_CANNOT_CLASSIFY_SOURCE_FAILED",p)
    if t.outcome is Outcome.SUPERSEDED and not t.superseded_by:return Qualification(False,"SUPERSESSION_TARGET_REQUIRED",p)
    floor=MIN_EVIDENCE.get(t.resulting_state)
    if floor is not None and t.evidence_class<floor:return Qualification(False,"INSUFFICIENT_EVIDENCE_STRENGTH",p)
    if t.outcome is Outcome.BLOCKED or t.evidence_class is EvidenceClass.BLOCKED:return Qualification(True,"BLOCK_RECORDED_PRIOR_STATE_PRESERVED",p)
    return Qualification(True,"TRANSITION_EVIDENCE_BOUND",p)
def idempotency_key(t:Transition)->Tuple[str,...]:
    return (t.subject,t.subject_revision,t.environment_revision,t.operation_fingerprint,t.attempt_id,t.resulting_state)
def audit_key(t:Transition)->Tuple[str,...]:
    return (t.subject,t.subject_revision,t.environment_id,t.environment_revision,t.operation_id,t.attempt_id,t.provenance.method,t.stage)
