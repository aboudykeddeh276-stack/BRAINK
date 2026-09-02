from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any,Mapping,Optional
import hashlib,json,os,time

def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def root(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()

@dataclass(frozen=True)
class TransitionReceipt:
    subsystem:str;operation:str;subject:str;status:str;effect:Mapping[str,Any];produced_ns:int
    @property
    def receipt_root(self):return root(asdict(self))

class DurableStore:
    def __init__(self,path:str|Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {"generation":0,"leases":{},"customer_files":{},"research":{},"publications":{},"domain_intents":{},"frontage_releases":{},"receipts":[]}
        self.state.setdefault("frontage_releases",{})
    def commit(self,mutator):
        nxt=json.loads(json.dumps(self.state));effect=mutator(nxt);nxt["generation"]+=1;nxt["state_root"]=root({k:v for k,v in nxt.items() if k!="state_root"})
        tmp=self.path.with_suffix(".tmp");tmp.write_bytes(canonical(nxt));os.replace(tmp,self.path);self.state=nxt;return effect
    def record(self,r:TransitionReceipt):
        self.commit(lambda s:s["receipts"].append({**asdict(r),"receipt_root":r.receipt_root}) or {"receipt_root":r.receipt_root});return r

class HRSupervisionRuntime:
    def __init__(self,store:DurableStore):self.store=store
    def acquire(self,lease_id,supervisor_id,subject_id,ttl_ns,now_ns=None):
        now=now_ns or time.time_ns();current=self.store.state["leases"].get(subject_id)
        if current and current["expires_ns"]>now and current["lease_id"]!=lease_id:
            return self.store.record(TransitionReceipt("HR","LEASE_ACQUIRE",subject_id,"REJECTED_ACTIVE_LEASE",{"current":current},now))
        epoch=(current or {}).get("epoch",0)+1
        lease={"lease_id":lease_id,"supervisor_id":supervisor_id,"subject_id":subject_id,"epoch":epoch,"acquired_ns":now,"expires_ns":now+ttl_ns,"status":"ACTIVE"}
        self.store.commit(lambda s:s["leases"].__setitem__(subject_id,lease) or lease)
        return self.store.record(TransitionReceipt("HR","LEASE_ACQUIRE",subject_id,"EXECUTED",lease,now))
    def expire_and_replace(self,subject_id,new_lease_id,new_supervisor_id,ttl_ns,now_ns):
        current=self.store.state["leases"].get(subject_id)
        if not current or current["expires_ns"]>now_ns:raise RuntimeError("LEASE_NOT_EXPIRED")
        replacement={"lease_id":new_lease_id,"supervisor_id":new_supervisor_id,"subject_id":subject_id,"epoch":current["epoch"]+1,"acquired_ns":now_ns,"expires_ns":now_ns+ttl_ns,"status":"REHYDRATED","predecessor_lease_id":current["lease_id"]}
        self.store.commit(lambda s:s["leases"].__setitem__(subject_id,replacement) or replacement)
        return self.store.record(TransitionReceipt("HR","LEASE_REPLACE_REHYDRATE",subject_id,"EXECUTED",replacement,now_ns))

class CustomerFileLifecycle:
    VALID={"INTAKE":{"ACTIVE","CLOSED"},"ACTIVE":{"SUSPENDED","CLOSED","ARCHIVED"},"SUSPENDED":{"ACTIVE","CLOSED"},"CLOSED":{"ARCHIVED"},"ARCHIVED":set()}
    def __init__(self,store):self.store=store
    def create(self,file_id,customer_id,consent):
        obj={"customer_id":customer_id,"state":"INTAKE","consent":consent,"communications":[],"billing":[],"exports":[],"retention":None,"version":1}
        self.store.commit(lambda s:s["customer_files"].__setitem__(file_id,obj) or obj);return self.store.record(TransitionReceipt("CUSTOMER_FILE","CREATE",file_id,"EXECUTED",obj,time.time_ns()))
    def transition(self,file_id,target,reason):
        obj=json.loads(json.dumps(self.store.state["customer_files"][file_id]));src=obj["state"]
        if target not in self.VALID[src]:raise RuntimeError(f"INVALID_TRANSITION:{src}->{target}")
        obj["state"]=target;obj["version"]+=1;obj["last_reason"]=reason
        self.store.commit(lambda s:s["customer_files"].__setitem__(file_id,obj) or obj);return self.store.record(TransitionReceipt("CUSTOMER_FILE","TRANSITION",file_id,"EXECUTED",{"from":src,"to":target,"version":obj["version"]},time.time_ns()))
    def append_event(self,file_id,kind,payload):
        obj=json.loads(json.dumps(self.store.state["customer_files"][file_id]));bucket={"COMMUNICATION":"communications","BILLING":"billing","EXPORT":"exports"}[kind];obj[bucket].append(payload);obj["version"]+=1
        self.store.commit(lambda s:s["customer_files"].__setitem__(file_id,obj) or obj);return self.store.record(TransitionReceipt("CUSTOMER_FILE",kind,file_id,"EXECUTED",{"bucket":bucket,"count":len(obj[bucket])},time.time_ns()))

class ResearchPromotionGate:
    def __init__(self,store):self.store=store
    def evaluate(self,research_id,claims,sources,replays,independent_verifier):
        criteria={"has_claims":bool(claims),"has_sources":bool(sources),"replay_pass":bool(replays) and all(r.get("status")=="PASS" for r in replays),"independent_verifier":bool(independent_verifier)}
        state="PROMOTED" if all(criteria.values()) else "REVIEW_REQUIRED";obj={"claims":claims,"sources":sources,"replays":replays,"verifier":independent_verifier,"criteria":criteria,"state":state};obj["evidence_root"]=root(obj)
        self.store.commit(lambda s:s["research"].__setitem__(research_id,obj) or obj);return self.store.record(TransitionReceipt("RESEARCH","PROMOTION_GATE",research_id,"EXECUTED",{"state":state,"criteria":criteria,"evidence_root":obj["evidence_root"]},time.time_ns()))

class PublicationRuntime:
    def __init__(self,store):self.store=store
    def stage(self,release_id,artifacts,frontage_id,approval):
        obj={"artifacts":artifacts,"frontage_id":frontage_id,"approval":approval,"state":"STAGED_INTERNAL"};obj["release_root"]=root(obj)
        self.store.commit(lambda s:s["publications"].__setitem__(release_id,obj) or obj);return self.store.record(TransitionReceipt("PUBLISHING","STAGE",release_id,"EXECUTED",obj,time.time_ns()))
    def publish_internal(self,release_id,projection_ref):
        obj=json.loads(json.dumps(self.store.state["publications"][release_id]));obj["state"]="INTERNAL_PROJECTED";obj["projection_ref"]=projection_ref
        self.store.commit(lambda s:s["publications"].__setitem__(release_id,obj) or obj);return self.store.record(TransitionReceipt("PUBLISHING","PROJECT_INTERNAL",release_id,"EXECUTED",obj,time.time_ns()))
    def bind_frontage_release(self,release_id,frontage,landing_page,route_path="/"):
        pub=json.loads(json.dumps(self.store.state["publications"].get(release_id) or {}))
        if pub.get("state")!="INTERNAL_PROJECTED":raise RuntimeError("PUBLICATION_NOT_INTERNAL_PROJECTED")
        frontage_id=frontage.get("frontage_id")
        if not frontage_id or pub.get("frontage_id")!=frontage_id:raise RuntimeError("FRONTAGE_ID_MISMATCH")
        if landing_page.get("frontage_id")!=frontage_id:raise RuntimeError("LANDING_FRONTAGE_MISMATCH")
        routes=dict(frontage.get("routes") or {})
        if route_path not in routes:raise RuntimeError("FRONTAGE_ROUTE_NOT_REGISTERED")
        page_id=landing_page.get("page_id")
        route_target=routes[route_path]
        if route_target not in {page_id,f"landing://{page_id}",landing_page.get("artifact_ref")}:
            raise RuntimeError("FRONTAGE_ROUTE_TARGET_MISMATCH")
        effect={"release_id":release_id,"frontage_id":frontage_id,"hostname":frontage.get("hostname"),"route_path":route_path,"route_target":route_target,"page_id":page_id,"projection_ref":pub["projection_ref"],"publication_state":"INTERNAL_PROJECTED","activation_state":"READY_FOR_EXTERNAL_ACTUATOR"}
        effect["frontage_release_root"]=root(effect)
        self.store.commit(lambda s:s["frontage_releases"].__setitem__(release_id,effect) or effect)
        return self.store.record(TransitionReceipt("FRONTAGE","BIND_INTERNAL_RELEASE",release_id,"EXECUTED",effect,time.time_ns()))
    def request_public_activation(self,release_id,domain,dns_changes,tls_required=True,actuator=None):
        intent={"release_id":release_id,"domain":domain,"dns_changes":dns_changes,"tls_required":tls_required}
        intent["intent_root"]=root(intent)
        if actuator is None:
            self.store.commit(lambda s:s["domain_intents"].__setitem__(domain,{**intent,"state":"DEFERRED_EXTERNAL_ACTUATOR"}) or intent)
            return self.store.record(TransitionReceipt("DOMAIN","PUBLIC_ACTIVATION",domain,"DEFERRED_EXTERNAL_ACTUATOR",{"intent_root":intent["intent_root"],"missing":"registrar/DNS/TLS/owner-host actuator handle"},time.time_ns()))
        effect=dict(actuator(intent));status=effect.pop("status","EXECUTED")
        self.store.commit(lambda s:s["domain_intents"].__setitem__(domain,{**intent,"state":status,"effect":effect}) or effect)
        return self.store.record(TransitionReceipt("DOMAIN","PUBLIC_ACTIVATION",domain,status,effect,time.time_ns()))
