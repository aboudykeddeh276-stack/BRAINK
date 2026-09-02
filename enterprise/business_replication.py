from __future__ import annotations
from dataclasses import asdict
from typing import Any,Dict,List
import hashlib,json

def root(v:Any)->str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class BusinessReplicator:
    """Turns a canonical server-room template into business-specific deployment intents. This emits configuration/identity, not fake external deployment receipts."""
    def replicate(self,room,business_id:str,domains:List[str],region:str)->Dict[str,Any]:
        servers=[]
        for s in room.servers:
            servers.append({
              "family":s.family,
              "instance_set":f"{business_id}:{s.family}",
              "replicas":s.replicas,
              "dependencies":list(s.dependencies),
              "services":list(s.services),
              "source_config_root":s.config_root,
              "environment":{"business_id":business_id,"region":region,"domains":domains}
            })
        packet={"business_id":business_id,"undertaking":room.undertaking,"room_root":room.room_root,
                "domains":domains,"region":region,"server_sets":servers}
        packet["replication_root"]=root(packet)
        return packet
