from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any,Mapping,Optional
import hashlib,json,time
from enterprise.service_genome import ServiceGenomeEngine
from enterprise.server_room import ServerRoomComposer

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

FAMILY_OWNER={"identity":"GENERAL_GOVERNANCE","hr":"GENERAL_GOVERNANCE","agentic_ai":"ENTERPRISE_AUTOMATION","mail":"COMMERCE_CUSTOMER_OPERATIONS","calendar":"COMMERCE_CUSTOMER_OPERATIONS","documents":"DATA_INFORMATION_GOVERNANCE","vfs":"DATA_INFORMATION_GOVERNANCE","research":"AI_CLOUD_INFRA","proof":"CYBERSECURITY","payments":"FINTECH_PAYMENTS","billing":"FINTECH_PAYMENTS","search":"DATA_INFORMATION_GOVERNANCE","case":"LEGAL_REGTECH","crm":"COMMERCE_CUSTOMER_OPERATIONS","runtime":"AI_CLOUD_INFRA","observer":"CYBERSECURITY","api":"AI_CLOUD_INFRA","analytics":"ENTERPRISE_AUTOMATION"}

@dataclass(frozen=True)
class Capability:
    name:str;gene:str;server_family:str;owner_sector:str;state:str="DEFINED";implementation_ref:Optional[str]=None;evidence_ref:Optional[str]=None

class CapabilityDeploymentRuntime:
    def __init__(self,catalog:Mapping[str,Any],resident_bindings:Optional[Mapping[str,Any]]=None):
        self.catalog=dict(catalog);self.capabilities={}
        for gene,spec in self.catalog["genes"].items():
            for cap in spec["provides"]:
                self.capabilities[cap]=Capability(cap,gene,spec["server_family"],FAMILY_OWNER.get(spec["server_family"],"UNASSIGNED"))
        self.genomes=ServiceGenomeEngine(catalog);self.rooms=ServerRoomComposer(catalog)
        if resident_bindings:self.load_bindings(resident_bindings)
    def bind(self,capability,implementation_ref,evidence_ref=None,state="VERIFIED"):
        if capability not in self.capabilities:return None
        p=self.capabilities[capability];self.capabilities[capability]=Capability(p.name,p.gene,p.server_family,p.owner_sector,state,implementation_ref,evidence_ref);return self.capabilities[capability]
    def load_bindings(self,packet:Mapping[str,Any]):
        loaded=[]
        for capability,spec in packet.get("bindings",{}).items():
            node=self.bind(capability,spec["implementation_ref"],spec.get("evidence_ref") or spec.get("evidence_class"),spec.get("state","VERIFIED"))
            if node:loaded.append(capability)
        return tuple(sorted(loaded))
    def compile(self,undertaking:str,scale="SMALL"):
        genome=self.genomes.genome(undertaking);room=self.rooms.compose(genome,scale);required=[]
        genes=set(genome.genes)
        for cap in sorted(self.capabilities):
            n=self.capabilities[cap]
            if n.gene not in genes:continue
            if n.implementation_ref and n.state in {"BOUND","EXECUTABLE","VERIFIED"}:decision="REUSE"
            elif n.implementation_ref:decision="QUALIFY"
            else:decision="CREATE_OR_BIND"
            gap={"REUSE":"CAPABILITY_RESIDENT","QUALIFY":"QUALIFICATION_REQUIRED","CREATE_OR_BIND":"ADAPTER_OR_FUNCTION_REQUIRED"}[decision]
            group={"CAPABILITY_RESIDENT":"group://runtime-dispatch","QUALIFICATION_REQUIRED":"group://verification-qualification","ADAPTER_OR_FUNCTION_REQUIRED":"group://engineering-synthesis"}[gap]
            required.append({**asdict(n),"decision":decision,"gap_class":gap,"work_group":group,"work_module":f"WM://{n.owner_sector}/{n.name}"})
        body={"schema":"braink.capability-deployment.r18/v3","undertaking":undertaking,"generated_ns":time.time_ns(),"genome":{"id":genome.genome_id,"genes":list(genome.genes),"capability_root":genome.capability_root},"room_root":room.room_root,"server_sets":[{"family":s.family,"replicas":s.replicas,"services":list(s.services),"dependencies":list(s.dependencies),"config_root":s.config_root} for s in room.servers],"requirements":required,"resident_count":sum(1 for r in required if r["gap_class"]=="CAPABILITY_RESIDENT"),"gap_count":sum(1 for r in required if r["gap_class"]!="CAPABILITY_RESIDENT")}
        body["deployment_root"]=root(body);return body
