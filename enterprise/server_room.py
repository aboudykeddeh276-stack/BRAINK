from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any,Dict,List
import hashlib,json,time,uuid

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class ServerSpec:
    server_id:str
    family:str
    genes:tuple[str,...]
    replicas:int
    dependencies:tuple[str,...]
    services:tuple[str,...]
    config_root:str

@dataclass(frozen=True)
class ServerRoom:
    room_id:str
    undertaking:str
    servers:tuple[ServerSpec,...]
    room_root:str
    created_ns:int

DEPENDENCIES={
 "identity":(),
 "hr":("identity",),
 "agentic_ai":("identity","hr","research","vfs"),
 "mail":("identity",),
 "calendar":("identity",),
 "documents":("identity","vfs"),
 "vfs":("identity",),
 "research":("vfs","search"),
 "proof":("vfs","observer"),
 "payments":("identity","proof"),
 "billing":("identity","proof"),
 "search":("vfs",),
 "case":("documents","vfs","research","proof"),
 "crm":("identity","mail"),
 "runtime":("identity","observer"),
 "observer":("vfs",),
 "api":("identity","runtime"),
 "analytics":("observer","billing")
}

CRITICAL_REPLICATION={"identity":2,"hr":2,"agentic_ai":2,"vfs":2,"proof":2,"runtime":2,"observer":2,"api":2}

class ServerRoomComposer:
    def __init__(self,catalog):
        self.catalog=catalog

    def compose(self,genome,scale:str="SMALL")->ServerRoom:
        families={}
        scale_mul={"SMALL":1,"MEDIUM":2,"LARGE":3}[scale]
        for gid in genome.genes:
            fam=self.catalog["genes"][gid]["server_family"]
            families.setdefault(fam,[]).append(gid)

        specs=[]
        active=set(families)
        for fam,gids in sorted(families.items()):
            base=CRITICAL_REPLICATION.get(fam,1)
            replicas=max(1,base*scale_mul if fam in CRITICAL_REPLICATION else scale_mul)
            deps=tuple(d for d in DEPENDENCIES.get(fam,()) if d in active)
            services=tuple(sorted({cap for gid in gids for cap in self.catalog["genes"][gid]["provides"]}))
            cfg={"family":fam,"genes":sorted(gids),"replicas":replicas,"dependencies":deps,"services":services,"undertaking":genome.undertaking}
            specs.append(ServerSpec(
                server_id="SRV-"+fam.upper()+"-"+uuid.uuid4().hex[:8],
                family=fam,genes=tuple(sorted(gids)),replicas=replicas,
                dependencies=deps,services=services,config_root=root(cfg)))
        body={"undertaking":genome.undertaking,"servers":[asdict(s) for s in specs]}
        return ServerRoom("ROOM-"+uuid.uuid4().hex[:12],genome.undertaking,tuple(specs),root(body),time.time_ns())
