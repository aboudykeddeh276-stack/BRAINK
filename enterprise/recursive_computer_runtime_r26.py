from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import json
import threading
import hashlib
import os
import fcntl
from enterprise.self_addressing_runtime import SelfAddressingRuntime
from runtime.R25.system_evolution_runtime import AppendOnlyLedger, TransactionReceipt, canonical_json, sha256_json

def _copy(v: Any) -> Any:
    return json.loads(canonical_json(v))

@dataclass(frozen=True)
class ComputerIdentity:
    computer_id: str
    parent_id: str | None
    generation: int
    lineage: tuple[str, ...]
    constructor_id: str

class RecursiveComputer:
    CONSTRUCTOR_ID = 'constructor://kex/recursive-computer/r26'
    def __init__(self, *, computer_id: str, state_root: str|Path, parent_id=None, generation=0, lineage=None, state=None, memory=None, bootstrap=True):
        lineage = lineage or (computer_id,)
        self.identity = ComputerIdentity(computer_id, parent_id, generation, tuple(lineage), self.CONSTRUCTOR_ID)
        self.state_root = Path(state_root); self.state_root.mkdir(parents=True, exist_ok=True)
        self.runtime = SelfAddressingRuntime(self.state_root/'runtime-checkpoint.json')
        self.ledger = AppendOnlyLedger(); self.state = _copy(dict(state or {})); self.memory = _copy(dict(memory or {})); self.children = {}; self._lock = threading.RLock(); self._expected_state_hash = None; self._expected_ledger_hash = None
        if bootstrap: self._persist('BOOTSTRAP')
    @property
    def state_backing(self): return f"file://{self.state_root/'computer.json'}"
    @property
    def ledger_backing(self): return f"file://{self.state_root/'ledger.json'}"
    def _snapshot(self):
        return _copy({'identity':asdict(self.identity),'state':self.state,'memory':self.memory,'children':sorted(self.children),'constructor':self.CONSTRUCTOR_ID})
    def _load_committed_ledger(self):
        rb=self.runtime.route(f'computer://{self.identity.computer_id}/ledger',self.ledger_backing,'READ')
        ledger=AppendOnlyLedger(); expected=None
        if rb.get('status')=='READ':
            ledger._events=[TransactionReceipt(**e) for e in rb['value']]; expected=rb['value_hash']
            if not ledger.verify(): raise RuntimeError('COMMITTED_LEDGER_INVALID')
        elif rb.get('status')!='HOLE': raise RuntimeError(f'LEDGER_READ_FAILED:{rb}')
        return ledger,expected
    def _record_event(self, *, operation, input_state, output_state, proof, rollback, max_attempts=8):
        for _ in range(max_attempts):
            ledger,expected=self._load_committed_ledger()
            ledger.append(operation=operation,actor=self.identity.computer_id,owner='A.KEDDEH / KEDDEH_SYSTEMS',input_state=input_state,output_state=output_state,proof=proof,rollback=rollback,lineage=self.identity.lineage)
            events=[asdict(e) for e in ledger.events]
            wr=self.runtime.route(f'computer://{self.identity.computer_id}/ledger',self.ledger_backing,'CAS_WRITE',{'expected_hash':expected,'value':events})
            if wr.get('status')=='CONFLICT': continue
            if wr.get('status')!='COMMITTED': raise RuntimeError(f'LEDGER_PERSIST_FAILED:{wr}')
            self.ledger=ledger; self._expected_ledger_hash=wr['value_hash']
            verify=self.runtime.route(f'computer://{self.identity.computer_id}/ledger',self.ledger_backing,'READ')
            if verify.get('status')!='READ' or verify.get('value')!=events: raise RuntimeError('LEDGER_READBACK_MISMATCH')
            return verify
        raise RuntimeError('LEDGER_CAS_RETRY_EXHAUSTED')
    def _persist(self, operation):
        snap=self._snapshot(); r=self.runtime.route(f'computer://{self.identity.computer_id}/state',self.state_backing,'CAS_WRITE',{'expected_hash':self._expected_state_hash,'value':snap})
        if r.get('status')=='CONFLICT':
            self.runtime.observe('runtime://computer',f'computer://{self.identity.computer_id}/state','CONTRADICTION',r); raise RuntimeError('STALE_STATE_CONFLICT')
        if r.get('status')!='COMMITTED': raise RuntimeError(f'PERSIST_FAILED:{r}')
        self._expected_state_hash=r['value_hash']
        rb=self.runtime.route(f'computer://{self.identity.computer_id}/state',self.state_backing,'READ')
        if rb.get('status')!='READ' or rb.get('value')!=snap: raise RuntimeError('READBACK_MISMATCH')
        self._record_event(operation=operation,input_state=snap,output_state=rb['value'],proof={'readback_equal':True,'value_hash':rb['value_hash']},rollback={'checkpoint':self.runtime.checkpoint()})
        return rb
    @classmethod
    def restore(cls, state_root, *, recursive=False):
        state_root=Path(state_root); sp=state_root/'computer.json'; lp=state_root/'ledger.json'
        if not sp.exists(): raise FileNotFoundError(sp)
        snap=json.loads(sp.read_text()); ident=snap['identity']
        if snap.get('constructor')!=cls.CONSTRUCTOR_ID: raise RuntimeError('CONSTRUCTOR_ID_MISMATCH')
        c=cls(computer_id=ident['computer_id'],state_root=state_root,parent_id=ident.get('parent_id'),generation=int(ident['generation']),lineage=tuple(ident['lineage']),state=snap.get('state',{}),memory=snap.get('memory',{}),bootstrap=False)
        if lp.exists(): c.ledger,c._expected_ledger_hash=c._load_committed_ledger()
        rb=c.runtime.route(f'computer://{c.identity.computer_id}/state',c.state_backing,'READ')
        if rb.get('status')!='READ' or rb.get('value')!=snap: raise RuntimeError('RESTORE_STATE_READBACK_MISMATCH')
        c._expected_state_hash=rb['value_hash']
        if recursive:
            for child_id in snap.get('children',[]):
                child=cls.restore(state_root/'descendants'/child_id,recursive=True)
                if child.identity.parent_id!=c.identity.computer_id: raise RuntimeError('DESCENDANT_PARENT_ID_MISMATCH')
                if child.identity.generation!=c.identity.generation+1: raise RuntimeError('DESCENDANT_GENERATION_MISMATCH')
                if child.identity.lineage[:-1]!=c.identity.lineage: raise RuntimeError('DESCENDANT_LINEAGE_MISMATCH')
                c.children[child_id]=child
            if sorted(c.children)!=sorted(snap.get('children',[])): raise RuntimeError('DESCENDANT_TOPOLOGY_READBACK_MISMATCH')
        c._record_event(operation='WARM_BOOT_TREE_RESTORE' if recursive else 'WARM_BOOT_RESTORE',input_state=snap,output_state=rb['value'],proof={'readback_equal':True,'restored':True,'recursive':recursive,'descendants':sorted(c.children)},rollback={'checkpoint':c.runtime.checkpoint()})
        return c
    @classmethod
    def restore_tree(cls,state_root): return cls.restore(state_root,recursive=True)
    def write_state(self,k,v):
        with self._lock:
            before=_copy(self.state)
            try: self.state[k]=_copy(v); return self._persist('STATE_WRITE')
            except Exception: self.state=before; raise
    def write_memory(self,k,v):
        with self._lock:
            before=_copy(self.memory)
            try: self.memory[k]=_copy(v); return self._persist('MEMORY_WRITE')
            except Exception: self.memory=before; raise
    def _refresh_constructor_view(self):
        rb=self.runtime.route(f'computer://{self.identity.computer_id}/state',self.state_backing,'READ')
        if rb.get('status')!='READ': raise RuntimeError(f'CONSTRUCTOR_REFRESH_FAILED:{rb}')
        snap=rb['value']
        if snap.get('constructor')!=self.CONSTRUCTOR_ID or snap['identity']['computer_id']!=self.identity.computer_id: raise RuntimeError('CONSTRUCTOR_REFRESH_IDENTITY_MISMATCH')
        self.state=_copy(snap.get('state',{})); self.memory=_copy(snap.get('memory',{})); self._expected_state_hash=rb['value_hash']
        committed_children={}
        for child_id in snap.get('children',[]):
            child_root=self.state_root/'descendants'/child_id
            if not child_root.exists(): raise RuntimeError('COMMITTED_DESCENDANT_MISSING')
            committed_children[child_id]=RecursiveComputer.restore(child_root)
        self.children=committed_children; self.ledger,self._expected_ledger_hash=self._load_committed_ledger(); return snap
    def _constructor_lock(self):
        lock_path=self.state_root/'.constructor.lock'; lock_path.touch(exist_ok=True); return lock_path.open('r+')
    def _quarantine_uncommitted_child(self, child, reason):
        child_state=child.readback(); child_root=hashlib.sha256(canonical_json(child_state).encode()).hexdigest(); quarantine_dir=self.state_root/'.orphaned'; quarantine_dir.mkdir(parents=True,exist_ok=True); target=quarantine_dir/f'{child.identity.computer_id}.{child_root}'
        if target.exists():
            existing=json.loads((target/'computer.json').read_text())
            if existing!=child_state: raise RuntimeError('ORPHAN_QUARANTINE_HASH_COLLISION')
        else:
            os.replace(child.state_root,target)
            for d in (quarantine_dir,self.state_root/'descendants'):
                fd=os.open(d,os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
        receipt={'classification':'UNCOMMITTED_DESCENDANT_QUARANTINE','parent_id':self.identity.computer_id,'child_id':child.identity.computer_id,'child_state_root':child_root,'reason':str(reason),'parent_lineage':list(self.identity.lineage),'child_lineage':list(child.identity.lineage),'authority':'A.KEDDEH / KEDDEH_SYSTEMS'}
        adapter=self.runtime.registry.adapters['adapter://file/json']; rr=adapter.apply('file://'+str(target/'orphan-receipt.json'),'orphan://receipt','WRITE',receipt)
        if rr.get('status')!='COMMITTED': raise RuntimeError(f'ORPHAN_RECEIPT_PERSIST_FAILED:{rr}')
        self.runtime.observe('runtime://computer',f'computer://{self.identity.computer_id}/descendants/{child.identity.computer_id}','CONTRADICTION',receipt)
        return {'status':'QUARANTINED','path':str(target),'child_state_root':child_root,'receipt_hash':rr['value_hash']}
    def instantiate(self,child_id):
        with self._lock:
            with self._constructor_lock() as lock_fh:
                fcntl.flock(lock_fh.fileno(),fcntl.LOCK_EX)
                try:
                    self._refresh_constructor_view()
                    if child_id in self.children: raise ValueError('CHILD_ALREADY_EXISTS')
                    c=RecursiveComputer(computer_id=child_id,state_root=self.state_root/'descendants'/child_id,parent_id=self.identity.computer_id,generation=self.identity.generation+1,lineage=self.identity.lineage+(child_id,),state=self.state,memory=self.memory)
                    self.children[child_id]=c
                    try: self._persist('SUCCESSOR_CREATED')
                    except Exception as exc:
                        self.children.pop(child_id,None); self._quarantine_uncommitted_child(c,exc); raise
                    return c
                finally: fcntl.flock(lock_fh.fileno(),fcntl.LOCK_UN)
    def readback(self):
        r=self.runtime.route(f'computer://{self.identity.computer_id}/state',self.state_backing,'READ')
        if r.get('status')!='READ': raise RuntimeError(f'READBACK_FAILED:{r}')
        return r['value']

def execute_recursive_proof(root_dir):
    rd=Path(root_dir); a=RecursiveComputer(computer_id='A',state_root=rd/'A'); a.write_memory('seed',297); a.write_state('phase','ROOT_READY')
    b=a.instantiate('B'); b.write_memory('child',88); b.write_state('phase','CHILD_READY')
    c=b.instantiate('C'); c.write_state('phase','GRANDCHILD_READY')
    c2=RecursiveComputer.restore(rd/'A'/'descendants'/'B'/'descendants'/'C'); d=c2.instantiate('D'); d.write_state('phase','POST_RESTORE_DESCENDANT_READY')
    a2=RecursiveComputer.restore_tree(rd/'A'); b2=a2.children['B']; c3=b2.children['C']; d2=c3.children['D']; e=d2.instantiate('E'); e.write_state('phase','POST_TREE_RESTORE_DESCENDANT_READY')
    nodes={'A':a2,'B':b2,'C':c3,'D':d2,'E':e}; readbacks={n:o.readback() for n,o in nodes.items()}
    p={'status':'VERIFIED','lineage':{n:list(o.identity.lineage) for n,o in nodes.items()},'memory':{n:readbacks[n]['memory'] for n in nodes},'constructor_ids':{n:o.identity.constructor_id for n,o in nodes.items()},'state_roots':{n:sha256_json(readbacks[n]) for n in nodes},'ledger_verified':{n:o.ledger.verify() for n,o in nodes.items()},'tree':{'A':sorted(a2.children),'B':sorted(b2.children),'C':sorted(c3.children),'D':sorted(d2.children),'E':sorted(e.children)},'warm_boot':{'root_restored':a2.identity.computer_id,'rehydrated_path':['A','B','C','D'],'post_tree_restore_descendant':e.identity.computer_id}}
    if p['lineage']['E']!=['A','B','C','D','E']: raise RuntimeError('POST_TREE_RESTORE_LINEAGE_FAILED')
    if p['memory']['E']!={'child':88,'seed':297}: raise RuntimeError('E_DID_NOT_INHERIT_REHYDRATED_MEMORY')
    if p['tree']!={'A':['B'],'B':['C'],'C':['D'],'D':['E'],'E':[]}: raise RuntimeError('TREE_REHYDRATION_FAILED')
    if len(set(p['constructor_ids'].values()))!=1: raise RuntimeError('CONSTRUCTOR_CONTINUITY_FAILED')
    if not all(p['ledger_verified'].values()): raise RuntimeError('LEDGER_VERIFICATION_FAILED')
    return p
