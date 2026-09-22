#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass,asdict
from typing import Dict,Tuple

def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def digest(v): return hashlib.sha256(canonical(v)).hexdigest()

class SafetyViolation(RuntimeError): pass
class CoordinateConflict(RuntimeError): pass
class ReconcileFailure(RuntimeError): pass

@dataclass(frozen=True)
class EvidenceReceipt:
    event_id:str
    event_type:str
    subject:str
    evidence_hash:str
    details:Tuple[Tuple[str,str],...]

class ToTSafetyKernel:
    """Fail-closed action gate with immutable evidence receipts."""
    ALLOWED={'REGISTER','PROPOSE','COMMIT','RECONCILE','INVALIDATE','REVALIDATE','OBSERVE'}
    def __init__(self): self._receipts=[]
    def authorize(self,event_type,subject,evidence,**details):
        if event_type not in self.ALLOWED: raise SafetyViolation('ACTION_NOT_DECLARED')
        if not subject: raise SafetyViolation('SUBJECT_REQUIRED')
        if evidence in (None,'',b''): raise SafetyViolation('EVIDENCE_REQUIRED')
        eh=hashlib.sha256(evidence if isinstance(evidence,bytes) else str(evidence).encode()).hexdigest()
        payload={'n':len(self._receipts)+1,'event_type':event_type,'subject':subject,'evidence_hash':eh,'details':sorted((str(k),str(v)) for k,v in details.items())}
        r=EvidenceReceipt(digest(payload),event_type,subject,eh,tuple(payload['details']))
        self._receipts.append(r); return r
    @property
    def receipts(self): return tuple(self._receipts)
    @property
    def root(self): return digest([asdict(r) for r in self._receipts])

@dataclass(frozen=True)
class CoordinateRecord:
    coordinate:str
    generation:int
    value_hash:str
    proposer:str
    previous_hash:str|None

class Replica:
    def __init__(self,node_id): self.node_id=node_id; self.log=[]; self.state={}; self.online=True
    def append(self,record):
        if not self.online: return False
        old=self.state.get(record.coordinate)
        if old and record.generation<=old.generation: raise CoordinateConflict('STALE_GENERATION')
        if old and record.previous_hash!=old.value_hash: raise CoordinateConflict('PREVIOUS_HASH_MISMATCH')
        if not old and record.generation!=1: raise CoordinateConflict('FIRST_GENERATION_MUST_BE_ONE')
        self.log.append(record); self.state[record.coordinate]=record; return True

class DistributedCoordinateDirectory:
    """Majority-commit replicated directory. Crash-fault model only; not Byzantine consensus."""
    def __init__(self,node_ids,kernel=None):
        if len(set(node_ids))<3: raise ValueError('AT_LEAST_THREE_REPLICAS_REQUIRED')
        self.replicas={n:Replica(n) for n in node_ids}; self.kernel=kernel or ToTSafetyKernel()
    @property
    def quorum(self): return len(self.replicas)//2+1
    def set_online(self,node_id,online): self.replicas[node_id].online=bool(online)
    def canonical(self,coordinate):
        votes={}
        for r in self.replicas.values():
            x=r.state.get(coordinate)
            if r.online and x: votes.setdefault(digest(asdict(x)),[]).append(x)
        winners=[xs[0] for xs in votes.values() if len(xs)>=self.quorum]
        if len(winners)!=1: raise CoordinateConflict('NO_UNIQUE_QUORUM_STATE')
        return winners[0]
    def commit(self,coordinate,value,proposer):
        if not coordinate or coordinate.strip().upper() in {'0','ZERO'}: raise CoordinateConflict('ZERO_NOT_PERMITTED_AS_ADDRESS')
        if proposer not in self.replicas: raise CoordinateConflict('UNKNOWN_PROPOSER')
        prior=[]
        for r in self.replicas.values():
            if r.online and coordinate in r.state: prior.append(r.state[coordinate])
        if prior:
            best=max(prior,key=lambda x:x.generation); generation=best.generation+1; prev=best.value_hash
        else: generation=1; prev=None
        vh=hashlib.sha256(value if isinstance(value,bytes) else canonical(value)).hexdigest()
        rec=CoordinateRecord(coordinate,generation,vh,proposer,prev)
        self.kernel.authorize('PROPOSE',coordinate,vh,generation=generation,proposer=proposer)
        accepted=[]
        for r in self.replicas.values():
            try:
                if r.append(rec): accepted.append(r.node_id)
            except CoordinateConflict: pass
        if len(accepted)<self.quorum: raise CoordinateConflict('QUORUM_NOT_REACHED')
        self.kernel.authorize('COMMIT',coordinate,digest(asdict(rec)),generation=generation,acks=','.join(sorted(accepted)))
        return rec
    def heal(self,node_id,coordinate):
        target=self.replicas[node_id]; source=self.canonical(coordinate)
        current=target.state.get(coordinate)
        if current and current.generation>=source.generation: return 'NOOP'
        # replay missing canonical records in generation order from a quorum-bearing peer
        peer=max((r for r in self.replicas.values() if r.online and coordinate in r.state),key=lambda r:r.state[coordinate].generation)
        for rec in peer.log:
            if rec.coordinate==coordinate and (not current or rec.generation>current.generation):
                target.online=True; target.append(rec); current=rec
        self.kernel.authorize('RECONCILE',coordinate,digest(asdict(source)),target=node_id,generation=source.generation)
        return 'REPAIRED'

class Layer2Reconciler:
    def reconcile(self,directory,coordinate):
        canonical=directory.canonical(coordinate); actions={}
        for node,r in directory.replicas.items():
            local=r.state.get(coordinate)
            if local is None or local.value_hash!=canonical.value_hash or local.generation!=canonical.generation:
                actions[node]=directory.heal(node,coordinate)
            else: actions[node]='NOOP'
        return {'coordinate':coordinate,'generation':canonical.generation,'value_hash':canonical.value_hash,'actions':actions,'consistent':all(r.state.get(coordinate)==canonical for r in directory.replicas.values())}
