#!/usr/bin/env python3
from __future__ import annotations
import json,hashlib,hmac,os
from dataclasses import dataclass,asdict

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def sha(x): return hashlib.sha256(x if isinstance(x,bytes) else canonical(x)).hexdigest()
class PeerFault(RuntimeError): pass

@dataclass(frozen=True)
class Entry:
    index:int;term:int;coordinate:str;generation:int;value_hash:str;previous_hash:str|None;proposer:str
@dataclass(frozen=True)
class Envelope:
    sender:str;payload:dict;signature:str

class PeerIdentity:
    """Authenticated message envelope. HMAC is a local engineering baseline, not hardware attestation."""
    def __init__(self,node_id,key): self.node_id=node_id;self.key=key
    def sign(self,payload): return Envelope(self.node_id,payload,hmac.new(self.key,canonical(payload),hashlib.sha256).hexdigest())
    @staticmethod
    def verify(envelope,keys):
        key=keys.get(envelope.sender)
        expected=hmac.new(key,canonical(envelope.payload),hashlib.sha256).hexdigest() if key else ''
        if not key or not hmac.compare_digest(envelope.signature,expected): raise PeerFault('AUTHENTICATION_FAILURE')
        return True

class DurableWAL:
    def __init__(self,path): self.path=path;os.makedirs(os.path.dirname(path),exist_ok=True)
    def append(self,entry):
        with open(self.path,'a',encoding='utf-8') as f:
            f.write(json.dumps(asdict(entry),sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    def recover(self):
        if not os.path.exists(self.path): return []
        out=[]
        with open(self.path,encoding='utf-8') as f:
            for line in f:
                try: out.append(Entry(**json.loads(line)))
                except Exception as exc: raise PeerFault('WAL_CORRUPTION') from exc
        return out

class DurablePeer:
    def __init__(self,node_id,key,wal_path):
        self.node_id=node_id;self.identity=PeerIdentity(node_id,key);self.wal=DurableWAL(wal_path);self.log=self.wal.recover();self.online=True
    def accept(self,envelope,keys):
        if not self.online:return False
        PeerIdentity.verify(envelope,keys);entry=Entry(**envelope.payload)
        expected=(self.log[-1].index+1) if self.log else 1
        if entry.index!=expected:raise PeerFault('INDEX_GAP_OR_DUPLICATE')
        self.wal.append(entry);self.log.append(entry);return True

class DurablePeerCluster:
    """Authenticated fsync-backed crash-fault baseline. It intentionally does not claim Raft/Paxos/BFT semantics."""
    def __init__(self,base_dir,node_ids=('n1','n2','n3')):
        self.keys={n:hashlib.sha256(('KEX-PEER:'+n).encode()).digest() for n in node_ids}
        self.nodes={n:DurablePeer(n,self.keys[n],os.path.join(base_dir,n,'wal.jsonl')) for n in node_ids};self.term=1
    @property
    def quorum(self):return len(self.nodes)//2+1
    def set_online(self,node_id,value):self.nodes[node_id].online=bool(value)
    def commit(self,coordinate,value,leader='n1'):
        if leader not in self.nodes:raise PeerFault('UNKNOWN_LEADER')
        live=[n for n in self.nodes.values() if n.online]
        histories=[n.log for n in live];best=max((h for h in histories if h),key=len,default=[])
        index=len(best)+1;generation=1+max((e.generation for h in histories for e in h if e.coordinate==coordinate),default=0)
        previous=next((e.value_hash for e in reversed(best) if e.coordinate==coordinate),None)
        entry=Entry(index,self.term,coordinate,generation,sha(value if isinstance(value,bytes) else canonical(value)),previous,leader)
        envelope=self.nodes[leader].identity.sign(asdict(entry));acks=[]
        for node in self.nodes.values():
            try:
                if node.accept(envelope,self.keys):acks.append(node.node_id)
            except PeerFault:pass
        if len(acks)<self.quorum:raise PeerFault('QUORUM_LOST')
        return entry,tuple(acks)
    def restart(self,node_id):
        path=self.nodes[node_id].wal.path;self.nodes[node_id]=DurablePeer(node_id,self.keys[node_id],path);return self.nodes[node_id]
