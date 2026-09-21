from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from .tot_safety import CommitReceipt, Transition, SafetyViolation

def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':')).encode()

def _reject_zero(v, field):
    if str(v).strip().upper() in {'0','ZERO'}:
        raise SafetyViolation(f'ZERO_NOT_PERMITTED_AS_{field}')

@dataclass(frozen=True)
class Manifestation:
    manifestation_id: str
    endpoint: str
    generation: int
    state: str

@dataclass
class CoordinateRecord:
    coordinate: str
    generation: int
    state_root: str
    manifestations: dict[str, Manifestation]

class DistributedCoordinateDirectory:
    def __init__(self):
        self.records: dict[str, CoordinateRecord] = {}
        self.applied_index=0

    def apply(self, t: Transition, receipt: CommitReceipt):
        if t.index != receipt.index or t.digest()!=receipt.transition_digest:
            raise SafetyViolation('UNCOMMITTED_OR_MISMATCHED_TRANSITION')
        if t.index != self.applied_index+1:
            raise SafetyViolation('DIRECTORY_REPLAY_GAP')
        p=t.payload
        cmd=t.command
        if cmd=='DIRECTORY_REGISTER':
            c=p['coordinate']; _reject_zero(c,'ADDRESS')
            if c in self.records: raise SafetyViolation('COORDINATE_ALREADY_REGISTERED')
            self.records[c]=CoordinateRecord(c,1,receipt.committed_root,{})
        elif cmd=='DIRECTORY_UPSERT_MANIFESTATION':
            c=p['coordinate']; _reject_zero(c,'ADDRESS')
            rec=self.records[c]
            mid=p['manifestation_id']; _reject_zero(mid,'ADDRESS')
            gen=int(p['generation'])
            if gen<=0: raise SafetyViolation('GENERATION_MUST_BE_POSITIVE')
            old=rec.manifestations.get(mid)
            if old and gen < old.generation: raise SafetyViolation('STALE_GENERATION')
            state=p['state']; _reject_zero(state,'STATE')
            rec.manifestations[mid]=Manifestation(mid,p['endpoint'],gen,state)
            rec.generation=max(rec.generation,gen)
            rec.state_root=receipt.committed_root
        elif cmd=='DIRECTORY_DETACH_MANIFESTATION':
            c=p['coordinate']; rec=self.records[c]
            mid=p['manifestation_id']; gen=int(p['generation'])
            old=rec.manifestations.get(mid)
            if old and gen < old.generation: raise SafetyViolation('STALE_GENERATION')
            rec.manifestations[mid]=Manifestation(mid,p.get('endpoint',old.endpoint if old else ''),gen,'DETACHED')
            rec.generation=max(rec.generation,gen); rec.state_root=receipt.committed_root
        else:
            raise SafetyViolation('DIRECTORY_COMMAND_REQUIRED')
        self.applied_index=t.index

    def directory_root(self) -> str:
        payload={k:{'coordinate':v.coordinate,'generation':v.generation,'state_root':v.state_root,'manifestations':{mk:asdict(mv) for mk,mv in sorted(v.manifestations.items())}} for k,v in sorted(self.records.items())}
        return sha256(_canon(payload)).hexdigest()
