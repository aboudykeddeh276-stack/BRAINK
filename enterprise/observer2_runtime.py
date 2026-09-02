from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import hashlib,json,os,sys,time


def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def _root(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

@dataclass(frozen=True)
class ObserverFrame:
    observer_identity:str; observer_class:str; scope:Mapping[str,Any]; environment:Mapping[str,Any]; phase:str; observed_state:Mapping[str,Any]; frame_root:str

class Observer2Runtime:
    OBSERVER_CLASS='SITUATED_ENVIRONMENT_OBSERVER'
    def __init__(self,observer_identity,scope,environment_root=None,federation=None):
        if federation is None and environment_root is None: raise ValueError('ENVIRONMENT_REQUIRED')
        self.observer_identity=observer_identity; self.scope=dict(scope); self.environment_root=Path(environment_root).resolve() if environment_root is not None else None; self.federation=federation; self.prior_frame=None; self.continuation='UNSET'
    def _filesystem_sample(self):
        targets=self.scope.get('paths') or []; out={}; base=self.environment_root
        for rel in targets:
            p=(base/rel).resolve()
            if base not in p.parents and p!=base: out[rel]={'exists':False,'error':'OUT_OF_SCOPE'}; continue
            if not p.exists(): out[rel]={'exists':False}; continue
            data=p.read_bytes() if p.is_file() else b''
            out[rel]={'exists':True,'kind':'file' if p.is_file() else 'directory','sha256':hashlib.sha256(data).hexdigest() if p.is_file() else None,'bytes':len(data) if p.is_file() else None}
        return out
    def sample(self,phase):
        if self.federation is not None:
            fed=self.federation.sample(); observed={'federation':fed,'sampled_at_ns':time.time_ns()}; environment={'kind':'FEDERATED','environment_root':fed['environment_root']}
        else:
            observed={'filesystem':self._filesystem_sample(),'process':{'pid':os.getpid(),'python':sys.version.split()[0],'cwd':str(Path.cwd().resolve())},'sampled_at_ns':time.time_ns()}; environment={'kind':'FILESYSTEM_PROCESS','root':str(self.environment_root)}
        base={'observer_identity':self.observer_identity,'observer_class':self.OBSERVER_CLASS,'scope':self.scope,'environment':environment,'phase':phase,'observed_state':observed}
        frame=ObserverFrame(**base,frame_root=_root(base)); self.prior_frame=frame; return frame
    def discrepancy(self,frame,expected):
        missing=[]; mismatched=[]
        if 'filesystem' in frame.observed_state:
            files=frame.observed_state['filesystem']
            for rel,rule in expected.get('paths',{}).items():
                actual=files.get(rel,{'exists':False})
                if rule.get('exists') is True and not actual.get('exists'): missing.append(rel)
                if rule.get('exists') is False and actual.get('exists'): mismatched.append(rel)
                if rule.get('sha256') and actual.get('sha256')!=rule['sha256']: mismatched.append(rel)
        for env_name,rule in expected.get('environments',{}).items():
            actual=frame.observed_state.get('federation',{}).get('environments',{}).get(env_name)
            if rule.get('present') is True and actual is None: missing.append('environment:'+env_name)
            if rule.get('root') and actual is not None and _root(actual)!=rule['root']: mismatched.append('environment:'+env_name)
        return {'missing':missing,'mismatched':sorted(set(mismatched)),'resolved':not missing and not mismatched,'frame_root':frame.frame_root}
    @staticmethod
    def compare(pre,post):
        changed=pre.observed_state!=post.observed_state
        return {'pre_frame_root':pre.frame_root,'post_frame_root':post.frame_root,'changed':changed,'pre_environment':pre.environment,'post_environment':post.environment}
    def update_continuation(self,*,discrepancy_post,comparison,invariants_survived):
        if not invariants_survived:self.continuation='REJECT_CANDIDATE'
        elif discrepancy_post.get('resolved') and comparison.get('changed'):self.continuation='FOLLOW_SUCCESSOR_STATE'
        elif discrepancy_post.get('resolved'):self.continuation='ACTION_NOT_EFFECTIVE'
        else:self.continuation='RECONCILE'
        return self.continuation
    def descriptor(self):
        return {'IDENTITY':{'observer_identity':self.observer_identity,'class':self.OBSERVER_CLASS,'role':'environmental interrogation'},'STATE':{'bound':True,'last_environmental_frame':asdict(self.prior_frame) if self.prior_frame else None},'CAPABILITY':['environment.sample','state.compare','discrepancy.emit','continuation.update'],'ADDRESS':str(self.environment_root) if self.environment_root else 'FEDERATED://ENVIRONMENTS','AUTHORITY':{'may_observe':True,'may_mutate':False},'PROCESS':'fresh environmental interrogation','CONTINUATION':'sample -> compare -> discrepancy -> think -> mirror -> learn -> resample -> continue'}
