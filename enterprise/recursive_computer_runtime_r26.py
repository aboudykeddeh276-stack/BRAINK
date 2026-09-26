from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping
import json
import threading
import hashlib
import os
import fcntl
import re
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
    ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')

    @classmethod
    def _validate_id(cls, value, *, field='computer_id'):
        value = str(value)
        if value in {'.', '..'} or not cls.ID_RE.fullmatch(value):
            raise ValueError(f'INVALID_{field.upper()}')
        return value
    def __init__(self, *, computer_id: str, state_root: str|Path, parent_id=None, generation=0, lineage=None, state=None, memory=None, bootstrap=True):
        computer_id = self._validate_id(computer_id)
        lineage = tuple(lineage or (computer_id,))
        if not lineage or lineage[-1] != computer_id:
            raise ValueError('LINEAGE_IDENTITY_MISMATCH')
        for component in lineage:
            self._validate_id(component, field='lineage_component')
        self.identity = ComputerIdentity(computer_id, parent_id, generation, tuple(lineage), self.CONSTRUCTOR_ID)
        self.state_root = Path(state_root); self.state_root.mkdir(parents=True, exist_ok=True)
        self.runtime = SelfAddressingRuntime(self.state_root/'runtime-checkpoint.json')
        self.ledger = AppendOnlyLedger(); self.state = _copy(dict(state or {})); self.memory = _copy(dict(memory or {})); self.children = {}; self._committed_child_ids = set(); self._lock = threading.RLock(); self._expected_state_hash = None; self._expected_ledger_hash = None; self.runtime.register_reconciler(self._reconcile_runtime)
        if bootstrap: self._persist('BOOTSTRAP')
    @property
    def state_backing(self): return f"file://{self.state_root/'computer.json'}"
    @property
    def ledger_backing(self): return f"file://{self.state_root/'ledger.json'}"
    def _snapshot(self):
        return _copy({'identity':asdict(self.identity),'state':self.state,'memory':self.memory,'children':sorted(set(self.children)|self._committed_child_ids),'constructor':self.CONSTRUCTOR_ID})
    def _reconcile_runtime(self, payload):
        signal = payload.get("signal", {}) if isinstance(payload, dict) else {}
        subject = payload.get("subject") if isinstance(payload, dict) else None
        rb = self.runtime.route(f"computer://{self.identity.computer_id}/state", self.state_backing, "READ")
        if rb.get("status") != "READ":
            return {"status": "BLOCKED", "reason": "COMMITTED_STATE_UNREADABLE", "subject": subject, "readback": rb}
        snap = rb["value"]
        if snap.get("constructor") != self.CONSTRUCTOR_ID or snap.get("identity", {}).get("computer_id") != self.identity.computer_id:
            return {"status": "BLOCKED", "reason": "IDENTITY_OR_CONSTRUCTOR_MISMATCH", "subject": subject}
        self.state = _copy(snap.get("state", {})); self.memory = _copy(snap.get("memory", {})); self._committed_child_ids = set(snap.get("children", [])); self._expected_state_hash = rb["value_hash"]
        self.children = {k:v for k,v in self.children.items() if k in self._committed_child_ids}
        self.ledger, self._expected_ledger_hash = self._load_committed_ledger()
        return {"status": "COMMITTED", "repair": "REFRESH_FROM_COMMITTED_STATE", "subject": subject, "state_root": rb["value_hash"], "signal_kind": signal.get("kind")}
    def reconcile_once(self):
        return self.runtime.continuation_tick()
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
    def restore(cls, state_root, *, recursive=False, record_restore=True):
        state_root=Path(state_root); sp=state_root/'computer.json'; lp=state_root/'ledger.json'
        if not sp.exists(): raise FileNotFoundError(sp)
        snap=json.loads(sp.read_text()); ident=snap['identity']
        if snap.get('constructor')!=cls.CONSTRUCTOR_ID: raise RuntimeError('CONSTRUCTOR_ID_MISMATCH')
        c=cls(computer_id=ident['computer_id'],state_root=state_root,parent_id=ident.get('parent_id'),generation=int(ident['generation']),lineage=tuple(ident['lineage']),state=snap.get('state',{}),memory=snap.get('memory',{}),bootstrap=False)
        if lp.exists(): c.ledger,c._expected_ledger_hash=c._load_committed_ledger()
        rb=c.runtime.route(f'computer://{c.identity.computer_id}/state',c.state_backing,'READ')
        if rb.get('status')!='READ' or rb.get('value')!=snap: raise RuntimeError('RESTORE_STATE_READBACK_MISMATCH')
        c._expected_state_hash=rb['value_hash']; c._committed_child_ids=set(snap.get('children',[]))
        if recursive:
            for child_id in snap.get('children',[]):
                cls._validate_id(child_id, field='child_id')
                child=cls.restore(state_root/'descendants'/child_id,recursive=True,record_restore=False)
                if child.identity.parent_id!=c.identity.computer_id: raise RuntimeError('DESCENDANT_PARENT_ID_MISMATCH')
                if child.identity.generation!=c.identity.generation+1: raise RuntimeError('DESCENDANT_GENERATION_MISMATCH')
                if child.identity.lineage[:-1]!=c.identity.lineage: raise RuntimeError('DESCENDANT_LINEAGE_MISMATCH')
                c.children[child_id]=child
            if sorted(c.children)!=sorted(snap.get('children',[])): raise RuntimeError('DESCENDANT_TOPOLOGY_READBACK_MISMATCH')
        if record_restore:
            c._record_event(operation='WARM_BOOT_TREE_RESTORE' if recursive else 'WARM_BOOT_RESTORE',input_state=snap,output_state=rb['value'],proof={'readback_equal':True,'restored':True,'recursive':recursive,'descendants':sorted(c.children),'descendant_restore_events_suppressed':bool(recursive)},rollback={'checkpoint':c.runtime.checkpoint()})
        return c
    @classmethod
    def restore_tree(cls,state_root): return cls.restore(state_root,recursive=True,record_restore=True)
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
        committed_ids=set(snap.get('children',[]))
        for child_id in committed_ids:
            child_root=self.state_root/'descendants'/child_id
            child_state=child_root/'computer.json'
            if not child_state.exists(): raise RuntimeError('COMMITTED_DESCENDANT_MISSING')
            child_snap=json.loads(child_state.read_text()); ident=child_snap.get('identity',{})
            if ident.get('parent_id')!=self.identity.computer_id: raise RuntimeError('DESCENDANT_PARENT_ID_MISMATCH')
            if int(ident.get('generation',-1))!=self.identity.generation+1: raise RuntimeError('DESCENDANT_GENERATION_MISMATCH')
            if tuple(ident.get('lineage',[]))[:-1]!=self.identity.lineage: raise RuntimeError('DESCENDANT_LINEAGE_MISMATCH')
        self._committed_child_ids=committed_ids
        self.children={k:v for k,v in self.children.items() if k in committed_ids}
        self.ledger,self._expected_ledger_hash=self._load_committed_ledger(); return snap
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
        child_id=self._validate_id(child_id, field='child_id')
        with self._lock:
            with self._constructor_lock() as lock_fh:
                fcntl.flock(lock_fh.fileno(),fcntl.LOCK_EX)
                try:
                    self._refresh_constructor_view()
                    if child_id in self._committed_child_ids or child_id in self.children: raise ValueError('CHILD_ALREADY_EXISTS')
                    c=RecursiveComputer(computer_id=child_id,state_root=self.state_root/'descendants'/child_id,parent_id=self.identity.computer_id,generation=self.identity.generation+1,lineage=self.identity.lineage+(child_id,),state=self.state,memory=self.memory)
                    self.children[child_id]=c; self._committed_child_ids.add(child_id)
                    try: self._persist('SUCCESSOR_CREATED')
                    except Exception as exc:
                        self.children.pop(child_id,None); self._committed_child_ids.discard(child_id); self._quarantine_uncommitted_child(c,exc); raise
                    return c
                finally: fcntl.flock(lock_fh.fileno(),fcntl.LOCK_UN)
    def inspect_committed(self):
        adapter=self.runtime.registry.adapters['adapter://file/json']
        state_result=adapter.apply(self.state_backing,f'computer://{self.identity.computer_id}/state','READ')
        if state_result.get('status')!='READ': raise RuntimeError(f'INSPECT_STATE_FAILED:{state_result}')
        ledger_result=adapter.apply(self.ledger_backing,f'computer://{self.identity.computer_id}/ledger','READ')
        ledger=AppendOnlyLedger()
        if ledger_result.get('status')=='READ':
            ledger._events=[TransactionReceipt(**e) for e in ledger_result['value']]
            if not ledger.verify(): raise RuntimeError('INSPECT_LEDGER_INVALID')
        elif ledger_result.get('status')!='HOLE': raise RuntimeError(f'INSPECT_LEDGER_FAILED:{ledger_result}')
        return {'value':state_result['value'],'value_hash':state_result['value_hash'],'ledger_verified':ledger.verify(),'ledger_events':len(ledger.events)}
    def readback(self):
        r=self.runtime.route(f'computer://{self.identity.computer_id}/state',self.state_backing,'READ')
        if r.get('status')!='READ': raise RuntimeError(f'READBACK_FAILED:{r}')
        return r['value']


def execute_recursive_proof(root_dir: str | Path) -> dict[str, Any]:
    root_dir = Path(root_dir)
    root = RecursiveComputer(computer_id='A', state_root=root_dir/'A')
    root.write_memory('seed', 297)
    root.write_state('phase', 'ROOT_READY')

    b = root.instantiate('B')
    b.write_memory('child', 88)
    b.write_state('phase', 'CHILD_READY')
    c = b.instantiate('C')
    c.write_state('phase', 'GRANDCHILD_READY')

    restored = RecursiveComputer.restore_tree(root_dir/'A')
    d_parent = restored.children['B'].children['C']
    d = d_parent.instantiate('D')
    d.write_state('phase', 'POST_RESTORE_DESCENDANT_READY')

    restored_again = RecursiveComputer.restore_tree(root_dir/'A')
    d2 = restored_again.children['B'].children['C'].children['D']
    e = d2.instantiate('E')
    e.write_state('phase', 'SECOND_RESTORE_DESCENDANT_READY')

    nodes = {
        'A': restored_again,
        'B': restored_again.children['B'],
        'C': restored_again.children['B'].children['C'],
        'D': d2,
        'E': e,
    }
    readbacks = {name: node.readback() for name,node in nodes.items()}
    proof = {
        'status':'VERIFIED',
        'lineage':{name:list(node.identity.lineage) for name,node in nodes.items()},
        'memory':{name:rb['memory'] for name,rb in readbacks.items()},
        'tree':{name:rb['children'] for name,rb in readbacks.items()},
        'constructor_ids':{name:node.identity.constructor_id for name,node in nodes.items()},
        'state_roots':{name:sha256_json(rb) for name,rb in readbacks.items()},
        'ledger_verified':{name:node.ledger.verify() for name,node in nodes.items()},
        'warm_boot':{
            'root_restored':restored_again.identity.computer_id,
            'rehydrated_path':['A','B','C','D'],
            'post_tree_restore_descendant':'E',
        },
    }
    if readbacks['B']['memory'].get('seed') != 297: raise RuntimeError('B_DID_NOT_INHERIT_ROOT_MEMORY')
    if readbacks['E']['memory'] != {'child':88,'seed':297}: raise RuntimeError('E_DID_NOT_INHERIT_TRANSITIVE_MEMORY')
    if proof['lineage']['E'] != ['A','B','C','D','E']: raise RuntimeError('LINEAGE_CONTINUITY_FAILED')
    if len(set(proof['constructor_ids'].values())) != 1: raise RuntimeError('CONSTRUCTOR_CONTINUITY_FAILED')
    if not all(proof['ledger_verified'].values()): raise RuntimeError('LEDGER_VERIFICATION_FAILED')
    return proof
