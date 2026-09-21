from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Sequence
from .tot_safety import CommitReceipt, Transition, SafetyViolation, ToTSafetyKernel

def _canon(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def _reject_zero(v, field):
    if str(v).strip().upper() in {'0','ZERO'}: raise SafetyViolation(f'ZERO_NOT_PERMITTED_AS_{field}')

@dataclass(frozen=True)
class Manifestation:
    manifestation_id: str; endpoint: str; generation: int; state: str

@dataclass
class CoordinateRecord:
    coordinate: str; generation: int; state_root: str; manifestations: dict[str, Manifestation]

class DistributedCoordinateDirectory:
    def __init__(self, members: Sequence[str] | None = None):
        self.members=tuple(sorted(set(members))) if members else (); self.records={}; self.applied_index=0
        self.receipt_hash_by_index={}; self.history=[]

    def apply(self,t:Transition,receipt:CommitReceipt):
        if self.members: ToTSafetyKernel.verify_receipt(t,receipt,self.members)
        elif t.index!=receipt.index or t.digest()!=receipt.transition_digest: raise SafetyViolation('UNCOMMITTED_OR_MISMATCHED_TRANSITION')
        if t.index!=self.applied_index+1: raise SafetyViolation('DIRECTORY_REPLAY_GAP')
        if self.history and receipt.previous_root!=self.history[-1][1].committed_root: raise SafetyViolation('DIRECTORY_COMMIT_CHAIN_DIVERGENCE')
        p=t.payload; cmd=t.command
        if cmd=='DIRECTORY_REGISTER':
            c=p['coordinate']; _reject_zero(c,'ADDRESS')
            if c in self.records: raise SafetyViolation('COORDINATE_ALREADY_REGISTERED')
            self.records[c]=CoordinateRecord(c,1,receipt.committed_root,{})
        elif cmd=='DIRECTORY_UPSERT_MANIFESTATION':
            c=p['coordinate']; _reject_zero(c,'ADDRESS')
            if c not in self.records: raise SafetyViolation('COORDINATE_NOT_REGISTERED')
            rec=self.records[c]; mid=p['manifestation_id']; _reject_zero(mid,'ADDRESS'); gen=int(p['generation'])
            if gen<=0: raise SafetyViolation('GENERATION_MUST_BE_POSITIVE')
            old=rec.manifestations.get(mid)
            if old and gen<=old.generation: raise SafetyViolation('STALE_GENERATION')
            state=p['state']; _reject_zero(state,'STATE'); endpoint=p['endpoint']
            if not endpoint: raise SafetyViolation('ENDPOINT_REQUIRED')
            rec.manifestations[mid]=Manifestation(mid,endpoint,gen,state); rec.generation=max(rec.generation,gen); rec.state_root=receipt.committed_root
        elif cmd=='DIRECTORY_DETACH_MANIFESTATION':
            c=p['coordinate']; _reject_zero(c,'ADDRESS')
            if c not in self.records: raise SafetyViolation('COORDINATE_NOT_REGISTERED')
            rec=self.records[c]; mid=p['manifestation_id']; _reject_zero(mid,'ADDRESS'); gen=int(p['generation']); old=rec.manifestations.get(mid)
            if gen<=0: raise SafetyViolation('GENERATION_MUST_BE_POSITIVE')
            if old and gen<=old.generation: raise SafetyViolation('STALE_GENERATION')
            rec.manifestations[mid]=Manifestation(mid,p.get('endpoint',old.endpoint if old else ''),gen,'DETACHED'); rec.generation=max(rec.generation,gen); rec.state_root=receipt.committed_root
        else: raise SafetyViolation('DIRECTORY_COMMAND_REQUIRED')
        self.applied_index=t.index; self.receipt_hash_by_index[t.index]=receipt.receipt_hash; self.history.append((t,receipt))

    def sync_from(self,source:'DistributedCoordinateDirectory')->int:
        common=min(self.applied_index,source.applied_index)
        for i in range(1,common+1):
            if self.receipt_hash_by_index.get(i)!=source.receipt_hash_by_index.get(i): raise SafetyViolation('DIRECTORY_REPLICA_DIVERGENCE')
        applied=0
        for t,r in source.history[self.applied_index:]: self.apply(t,r); applied+=1
        return applied

    def directory_root(self)->str:
        payload={k:{'coordinate':v.coordinate,'generation':v.generation,'state_root':v.state_root,'manifestations':{mk:asdict(mv) for mk,mv in sorted(v.manifestations.items())}} for k,v in sorted(self.records.items())}
        return sha256(_canon(payload)).hexdigest()

    def snapshot(self)->dict:
        return {'applied_index':self.applied_index,'directory_root':self.directory_root(),'records':{k:{'coordinate':v.coordinate,'generation':v.generation,'state_root':v.state_root,'manifestations':{mk:asdict(mv) for mk,mv in sorted(v.manifestations.items())}} for k,v in sorted(self.records.items())}}

    @classmethod
    def from_snapshot(cls, snapshot:dict, members:Sequence[str]|None=None)->'DistributedCoordinateDirectory':
        d=cls(members); d.applied_index=int(snapshot['applied_index'])
        for c,obj in snapshot['records'].items():
            _reject_zero(c,'ADDRESS'); manifestations={}
            for mid,m in obj['manifestations'].items():
                _reject_zero(mid,'ADDRESS'); _reject_zero(m['state'],'STATE')
                manifestations[mid]=Manifestation(**m)
            d.records[c]=CoordinateRecord(obj['coordinate'],int(obj['generation']),obj['state_root'],manifestations)
        if d.directory_root()!=snapshot['directory_root']: raise SafetyViolation('DIRECTORY_SNAPSHOT_ROOT_MISMATCH')
        return d
