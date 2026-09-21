
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import hmac,json,os,socket,socketserver,subprocess,shutil
from pathlib import Path
from typing import Sequence, Iterable

class SafetyViolation(RuntimeError): pass
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v): return sha256(canon(v).encode()).hexdigest()
def reject_zero(v,field):
    if str(v).strip().upper() in {"0","ZERO"}: raise SafetyViolation(f"ZERO_NOT_PERMITTED_AS_{field}")

@dataclass(frozen=True)
class Transition:
    index:int; epoch:int; ballot:int; actor:str; command:str; payload:dict; previous_root:str; config_hash:str
    def value_identity(self): return digest({"actor":self.actor,"command":self.command,"payload":self.payload,"previous_root":self.previous_root,"config_hash":self.config_hash,"epoch":self.epoch,"index":self.index})
    def digest(self): return digest(asdict(self))

@dataclass(frozen=True)
class Accepted:
    voter:str; index:int; epoch:int; ballot:int; transition:Transition; config_hash:str

@dataclass(frozen=True)
class Certificate:
    transition_digest:str; value_identity:str; index:int; epoch:int; ballot:int; config_hash:str
    voters:tuple[str,...]; old_members:tuple[str,...]; new_members:tuple[str,...]|None; certificate_hash:str

@dataclass(frozen=True)
class Receipt:
    transition:Transition; certificate:Certificate; committed_root:str; receipt_hash:str

class JsonlWal:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.path.touch(exist_ok=True)
    def append(self,obj):
        with open(self.path,"a",encoding="utf-8") as f:
            f.write(canon(obj)+"\n");f.flush();os.fsync(f.fileno())
    def records(self):
        out=[]
        with open(self.path,encoding="utf-8") as f:
            for n,line in enumerate(f,1):
                if not line.strip():continue
                try:out.append(json.loads(line))
                except json.JSONDecodeError as e:raise SafetyViolation(f"WAL_CORRUPT_LINE_{n}") from e
        return out

def transition_from_dict(d): return Transition(**d)
def accepted_from_dict(d):
    d=dict(d);d["transition"]=transition_from_dict(d["transition"]);return Accepted(**d)
def cert_from_dict(d):
    d=dict(d);d["voters"]=tuple(d["voters"]);d["old_members"]=tuple(d["old_members"]);d["new_members"]=tuple(d["new_members"]) if d["new_members"] else None;return Certificate(**d)
def receipt_from_dict(d):return Receipt(transition_from_dict(d["transition"]),cert_from_dict(d["certificate"]),d["committed_root"],d["receipt_hash"])

class DurablePaxosToT:
    GENESIS=sha256(b"KEX-TOT-PAXOS-GENESIS").hexdigest()
    def __init__(self,node_id:str,members:Sequence[str],wal_path,secret:str,epoch=1):
        reject_zero(node_id,"ADDRESS")
        members=tuple(sorted(set(members)))
        if len(members)<3:raise SafetyViolation("AT_LEAST_THREE_MEMBERS_REQUIRED")
        self.node_id=node_id;self.members=members;self.new_members=None;self.epoch=epoch;self.secret=secret.encode()
        self.wal=JsonlWal(wal_path);self.root=self.GENESIS;self.log=[];self.receipts=[];self.promised={};self.accepted={};self.directory={};self.applied_index=0
        self._recover()
    @staticmethod
    def quorum(m): return len(tuple(m))//2+1
    @property
    def config_hash(self): return digest({"epoch":self.epoch,"members":self.members,"new_members":self.new_members})
    def _wal(self,k,d):self.wal.append({"kind":k,"data":d})
    def _recover(self):
        for r in self.wal.records():
            k,d=r["kind"],r["data"]
            if k=="PROMISE":self.promised[(d["epoch"],d["index"])]=d["ballot"]
            elif k=="ACCEPT":
                a=accepted_from_dict(d);self.accepted[(a.epoch,a.index)]=a
            elif k=="COMMIT":
                rr=receipt_from_dict(d);t=rr.transition;c=rr.certificate
                cb={"transition_digest":c.transition_digest,"value_identity":c.value_identity,"index":c.index,"epoch":c.epoch,"ballot":c.ballot,"config_hash":c.config_hash,"voters":c.voters,"old_members":c.old_members,"new_members":c.new_members}
                if digest(cb)!=c.certificate_hash:raise SafetyViolation("CERTIFICATE_HASH_MISMATCH")
                if digest({"transition":asdict(t),"certificate":asdict(c),"committed_root":rr.committed_root})!=rr.receipt_hash:raise SafetyViolation("RECEIPT_HASH_MISMATCH")
                if t.index!=len(self.log)+1 or t.previous_root!=self.root:raise SafetyViolation("RECOVERY_POSITION_MISMATCH")
                if len(set(c.voters)&set(c.old_members))<self.quorum(c.old_members):raise SafetyViolation("OLD_QUORUM_NOT_REACHED")
                if c.new_members and len(set(c.voters)&set(c.new_members))<self.quorum(c.new_members):raise SafetyViolation("NEW_QUORUM_NOT_REACHED")
                expected=sha256((self.root+t.digest()+c.certificate_hash).encode()).hexdigest()
                if expected!=rr.committed_root:raise SafetyViolation("COMMITTED_ROOT_MISMATCH")
                self.log.append(t);self.receipts.append(rr);self.root=rr.committed_root;self._apply(t,rr,persist_config=False)
                self.accepted.pop((t.epoch,t.index),None);self.promised.pop((t.epoch,t.index),None)
            elif k=="CONFIG":
                self.members=tuple(d["members"]);self.new_members=tuple(d["new_members"]) if d["new_members"] else None;self.epoch=d["epoch"]
    def allowed(self):return set(self.members)|set(self.new_members or ())
    def prepare(self,index,epoch,ballot,previous_root,config_hash):
        if self.node_id not in self.allowed():raise SafetyViolation("VOTER_NOT_MEMBER")
        if index!=len(self.log)+1:raise SafetyViolation("NON_CONTIGUOUS_INDEX")
        if previous_root!=self.root:raise SafetyViolation("PREVIOUS_ROOT_MISMATCH")
        if epoch!=self.epoch or config_hash!=self.config_hash:raise SafetyViolation("CONFIG_MISMATCH")
        key=(epoch,index);prior=self.promised.get(key,0)
        if ballot<prior:raise SafetyViolation("BALLOT_BELOW_PROMISE")
        if ballot>prior:
            self._wal("PROMISE",{"epoch":epoch,"index":index,"ballot":ballot});self.promised[key]=ballot
        a=self.accepted.get(key)
        return {"voter":self.node_id,"promised_ballot":self.promised[key],"accepted":asdict(a) if a else None}
    def accept(self,t:Transition):
        if self.node_id not in self.allowed():raise SafetyViolation("VOTER_NOT_MEMBER")
        if t.index!=len(self.log)+1 or t.previous_root!=self.root:raise SafetyViolation("POSITION_MISMATCH")
        if t.epoch!=self.epoch or t.config_hash!=self.config_hash:raise SafetyViolation("CONFIG_MISMATCH")
        key=(t.epoch,t.index);prom=self.promised.get(key,0)
        if t.ballot<prom:raise SafetyViolation("BALLOT_BELOW_PROMISE")
        a=self.accepted.get(key)
        if a and a.ballot==t.ballot and a.transition.value_identity()!=t.value_identity():raise SafetyViolation("SAME_BALLOT_EQUIVOCATION")
        self._wal("PROMISE",{"epoch":t.epoch,"index":t.index,"ballot":t.ballot});self.promised[key]=t.ballot
        aa=Accepted(self.node_id,t.index,t.epoch,t.ballot,t,t.config_hash)
        self._wal("ACCEPT",asdict(aa));self.accepted[key]=aa;return aa
    def certificate(self,t,accepts:Iterable[Accepted]):
        voters=tuple(sorted({a.voter for a in accepts if a.transition.digest()==t.digest() and a.ballot==t.ballot and a.config_hash==t.config_hash}))
        old=self.members;new=self.new_members
        if len(set(voters)&set(old))<self.quorum(old):raise SafetyViolation("OLD_QUORUM_NOT_REACHED")
        if new and len(set(voters)&set(new))<self.quorum(new):raise SafetyViolation("NEW_QUORUM_NOT_REACHED")
        b={"transition_digest":t.digest(),"value_identity":t.value_identity(),"index":t.index,"epoch":t.epoch,"ballot":t.ballot,"config_hash":t.config_hash,"voters":voters,"old_members":old,"new_members":new}
        return Certificate(**b,certificate_hash=digest(b))
    def make_receipt(self,t,accepts):
        c=self.certificate(t,accepts);root=sha256((self.root+t.digest()+c.certificate_hash).encode()).hexdigest()
        b={"transition":asdict(t),"certificate":asdict(c),"committed_root":root};return Receipt(t,c,root,digest(b))
    def install(self,r:Receipt):
        t,c=r.transition,r.certificate
        # evidence validation first
        cb={"transition_digest":c.transition_digest,"value_identity":c.value_identity,"index":c.index,"epoch":c.epoch,"ballot":c.ballot,"config_hash":c.config_hash,"voters":c.voters,"old_members":c.old_members,"new_members":c.new_members}
        if digest(cb)!=c.certificate_hash:raise SafetyViolation("CERTIFICATE_HASH_MISMATCH")
        if digest({"transition":asdict(t),"certificate":asdict(c),"committed_root":r.committed_root})!=r.receipt_hash:raise SafetyViolation("RECEIPT_HASH_MISMATCH")
        if t.index<=len(self.log):
            if self.receipts[t.index-1].receipt_hash!=r.receipt_hash:raise SafetyViolation("COMMITTED_PREFIX_DIVERGENCE")
            return False
        if t.index!=len(self.log)+1 or t.previous_root!=self.root:raise SafetyViolation("CATCHUP_POSITION_MISMATCH")
        if len(set(c.voters)&set(c.old_members))<self.quorum(c.old_members):raise SafetyViolation("OLD_QUORUM_NOT_REACHED")
        if c.new_members and len(set(c.voters)&set(c.new_members))<self.quorum(c.new_members):raise SafetyViolation("NEW_QUORUM_NOT_REACHED")
        if c.transition_digest!=t.digest() or c.value_identity!=t.value_identity():raise SafetyViolation("CERTIFICATE_TRANSITION_MISMATCH")
        expected=sha256((self.root+t.digest()+c.certificate_hash).encode()).hexdigest()
        if expected!=r.committed_root:raise SafetyViolation("COMMITTED_ROOT_MISMATCH")
        self._wal("COMMIT",{"transition":asdict(t),"certificate":asdict(c),"committed_root":r.committed_root,"receipt_hash":r.receipt_hash})
        self.log.append(t);self.receipts.append(r);self.root=r.committed_root;self._apply(t,r)
        self.accepted.pop((t.epoch,t.index),None);self.promised.pop((t.epoch,t.index),None)
        return True
    def _apply(self,t,r,persist_config=True):
        p=t.payload
        if t.command=="DIRECTORY_REGISTER":
            c=p["coordinate"];reject_zero(c,"ADDRESS")
            if c in self.directory:raise SafetyViolation("COORDINATE_ALREADY_REGISTERED")
            self.directory[c]={"generation":1,"state_root":r.committed_root,"manifestations":{}}
        elif t.command=="DIRECTORY_UPSERT":
            c=p["coordinate"];m=p["manifestation_id"];reject_zero(c,"ADDRESS");reject_zero(m,"ADDRESS")
            if c not in self.directory:raise SafetyViolation("COORDINATE_NOT_REGISTERED")
            gen=int(p["generation"]);old=self.directory[c]["manifestations"].get(m)
            if gen<=0 or (old and gen<=old["generation"]):raise SafetyViolation("STALE_GENERATION")
            self.directory[c]["manifestations"][m]={"endpoint":p["endpoint"],"generation":gen,"state":p.get("state","ATTACHED")}
            self.directory[c]["generation"]=max(self.directory[c]["generation"],gen);self.directory[c]["state_root"]=r.committed_root
        elif t.command=="BEGIN_RECONFIG":
            nm=tuple(sorted(set(p["new_members"])))
            if len(nm)<3:raise SafetyViolation("AT_LEAST_THREE_MEMBERS_REQUIRED")
            self.new_members=nm
            if persist_config:self._wal("CONFIG",{"members":self.members,"new_members":self.new_members,"epoch":self.epoch})
        elif t.command=="FINALIZE_RECONFIG":
            if not self.new_members:raise SafetyViolation("NO_JOINT_CONFIGURATION")
            self.members=self.new_members;self.new_members=None;self.epoch+=1;self.promised={};self.accepted={}
            if persist_config:self._wal("CONFIG",{"members":self.members,"new_members":None,"epoch":self.epoch})
        elif t.command=="BARRIER":pass
        self.applied_index=t.index
    def snapshot(self):return {"index":self.applied_index,"root":digest(self.directory),"records":self.directory}
    def sign(self,m):return hmac.new(self.secret,canon(m).encode(),sha256).hexdigest()
    def verify_env(self,e):
        if not hmac.compare_digest(self.sign(e["message"]),e["signature"]):raise SafetyViolation("AUTHENTICATION_FAILED")
        return e["message"]

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            env=json.loads(self.rfile.readline());m=self.server.state.verify_env(env);op=m["op"];s=self.server.state
            if op=="STATE":
                out={"ok":True,"node":s.node_id,"index":len(s.log),"root":s.root,"epoch":s.epoch,"config_hash":s.config_hash,"members":s.members,"new_members":s.new_members,"max_promised":max(s.promised.values(),default=0),"directory":s.snapshot()}
            elif op=="PREPARE":out={"ok":True,"promise":s.prepare(m["index"],m["epoch"],m["ballot"],m["previous_root"],m["config_hash"])}
            elif op=="ACCEPT":out={"ok":True,"accepted":asdict(s.accept(transition_from_dict(m["transition"])))}
            elif op=="COMMIT":out={"ok":True,"changed":s.install(receipt_from_dict(m["receipt"]))}
            elif op=="RECEIPTS_FROM":out={"ok":True,"receipts":[asdict(x) for x in s.receipts[int(m["start"]):]]}
            else:raise SafetyViolation("UNKNOWN_OPERATION")
        except Exception as e:out={"ok":False,"error":f"{type(e).__name__}:{e}"}
        self.wfile.write((canon(out)+"\n").encode())

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True
    def __init__(self,addr,state):self.state=state;super().__init__(addr,Handler)

class Client:
    def __init__(self,secret,timeout=1):self.secret=secret.encode();self.timeout=timeout
    def call(self,ep,m):
        sig=hmac.new(self.secret,canon(m).encode(),sha256).hexdigest();host,port=ep.split(":")
        with socket.create_connection((host,int(port)),timeout=self.timeout) as s:
            s.sendall((canon({"message":m,"signature":sig})+"\n").encode());line=s.makefile("r").readline()
            if not line:raise ConnectionError("EMPTY_RESPONSE")
            return json.loads(line)

class Coordinator:
    def __init__(self,endpoints,secret):self.endpoints=dict(endpoints);self.c=Client(secret)
    def live_states(self):
        out={}
        for n,e in self.endpoints.items():
            try:
                r=self.c.call(e,{"op":"STATE"})
                if r.get("ok"):out[n]=r
            except OSError:pass
        return out
    @staticmethod
    def _quorum_count(ids,m):return len(set(ids)&set(m))>=DurablePaxosToT.quorum(tuple(m))
    def propose_commit(self,actor,command,payload):
        while True:
            states=self.live_states()
            if not states:raise SafetyViolation("NO_LIVE_NODES")
            maxidx=max(s["index"] for s in states.values());top=[s for s in states.values() if s["index"]==maxidx]
            roots={s["root"] for s in top}
            if len(roots)!=1:raise SafetyViolation("LIVE_ROOT_DIVERGENCE")
            base=top[0];old=tuple(base["members"]);new=tuple(base["new_members"]) if base["new_members"] else None
            ballot=max(s["max_promised"] for s in top)+1
            pre={"op":"PREPARE","index":maxidx+1,"epoch":base["epoch"],"ballot":ballot,"previous_root":base["root"],"config_hash":base["config_hash"]}
            promises=[]
            for n,e in self.endpoints.items():
                try:
                    r=self.c.call(e,pre)
                    if r.get("ok"):promises.append((n,r["promise"]))
                except OSError:pass
            ids=[n for n,_ in promises]
            if not self._quorum_count(ids,old):raise SafetyViolation("PREPARE_OLD_QUORUM_NOT_REACHED")
            if new and not self._quorum_count(ids,new):raise SafetyViolation("PREPARE_NEW_QUORUM_NOT_REACHED")
            prior=[accepted_from_dict(p["accepted"]) for _,p in promises if p["accepted"]]
            if prior:
                highest=max(prior,key=lambda a:a.ballot).transition
                chosen=(highest.actor,highest.command,highest.payload)
                orphan=True
            else:
                chosen=(actor,command,payload);orphan=False
            t=Transition(maxidx+1,base["epoch"],ballot,chosen[0],chosen[1],chosen[2],base["root"],base["config_hash"])
            accepts=[]
            for n,e in self.endpoints.items():
                try:
                    r=self.c.call(e,{"op":"ACCEPT","transition":asdict(t)})
                    if r.get("ok"):accepts.append(accepted_from_dict(r["accepted"]))
                except OSError:pass
            ids=[a.voter for a in accepts]
            if not self._quorum_count(ids,old):raise SafetyViolation("ACCEPT_OLD_QUORUM_NOT_REACHED")
            if new and not self._quorum_count(ids,new):raise SafetyViolation("ACCEPT_NEW_QUORUM_NOT_REACHED")
            # Build receipt from exact current config.
            cb={"transition_digest":t.digest(),"value_identity":t.value_identity(),"index":t.index,"epoch":t.epoch,"ballot":t.ballot,"config_hash":t.config_hash,"voters":tuple(sorted(set(ids))),"old_members":old,"new_members":new}
            cert=Certificate(**cb,certificate_hash=digest(cb));root=sha256((t.previous_root+t.digest()+cert.certificate_hash).encode()).hexdigest()
            rb={"transition":asdict(t),"certificate":asdict(cert),"committed_root":root};receipt=Receipt(t,cert,root,digest(rb))
            committed=[]
            for n,e in self.endpoints.items():
                try:
                    r=self.c.call(e,{"op":"COMMIT","receipt":asdict(receipt)})
                    if r.get("ok"):committed.append(n)
                except OSError:pass
            if not self._quorum_count(committed,old):raise SafetyViolation("COMMIT_OLD_QUORUM_NOT_REACHED")
            if new and not self._quorum_count(committed,new):raise SafetyViolation("COMMIT_NEW_QUORUM_NOT_REACHED")
            if orphan and chosen!=(actor,command,payload):
                # Complete previously accepted value, then retry caller's value at next index.
                continue
            return receipt,committed
    def catch_up(self,source,target):
        ss=self.c.call(self.endpoints[source],{"op":"STATE"});ts=self.c.call(self.endpoints[target],{"op":"STATE"})
        r=self.c.call(self.endpoints[source],{"op":"RECEIPTS_FROM","start":ts["index"]});n=0
        for x in r["receipts"]:
            rr=self.c.call(self.endpoints[target],{"op":"COMMIT","receipt":x})

            if not rr.get("ok"):raise SafetyViolation(rr.get("error","CATCHUP_FAILED"))
            n+=1
        return n
    def barrier_read(self,actor,coord):
        r,_=self.propose_commit(actor,"BARRIER",{"coordinate":coord})
        st=self.live_states(); top=max(x["index"] for x in st.values());cand=[x for x in st.values() if x["index"]==top]
        roots={x["root"] for x in cand}
        if len(roots)!=1:raise SafetyViolation("READ_ROOT_DIVERGENCE")
        return cand[0]["directory"]["records"].get(coord),{"index":top,"root":next(iter(roots)),"responders":len(st)}

class LinuxBridgeActuator:
    def capability(self):
        ip=shutil.which("ip");euid=getattr(os,"geteuid",lambda:-1)()
        return {"iproute2":bool(ip),"euid":euid,"ready":bool(ip) and euid==0}
    def execute(self,kind,bridge,interface=None):
        cap=self.capability()
        if not cap["ready"]:raise SafetyViolation("LINUX_BRIDGE_ACTUATOR_UNAVAILABLE")
        if kind=="ENSURE_BRIDGE":
            p=subprocess.run(["ip","link","show",bridge],capture_output=True,text=True)
            if p.returncode!=0:
                p=subprocess.run(["ip","link","add","name",bridge,"type","bridge"],capture_output=True,text=True)
                if p.returncode!=0:raise SafetyViolation("BRIDGE_CREATE_FAILED:"+p.stderr.strip())
            p=subprocess.run(["ip","link","set",bridge,"up"],capture_output=True,text=True)
            if p.returncode!=0:raise SafetyViolation("BRIDGE_UP_FAILED:"+p.stderr.strip())
        elif kind=="ATTACH_INTERFACE":
            if not interface:raise SafetyViolation("INTERFACE_REQUIRED")
            p=subprocess.run(["ip","link","set",interface,"master",bridge],capture_output=True,text=True)
            if p.returncode!=0:raise SafetyViolation("INTERFACE_ATTACH_FAILED:"+p.stderr.strip())
        else:raise SafetyViolation("UNKNOWN_L2_ACTION")
        return {"status":"APPLIED","capability":cap}