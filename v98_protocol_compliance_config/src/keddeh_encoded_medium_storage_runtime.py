from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import hashlib, json

def canonical(x:Any)->str:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def root_hash(x:Any)->str:
    return hashlib.sha256(canonical(x).encode()).hexdigest()

@dataclass(frozen=True)
class EncodedCell:
    coordinate: tuple[int,int]
    state: int
    provenance: str

@dataclass(frozen=True)
class LogicalObject:
    object_id: str
    object_type: str
    address: str
    lineage: str
    payload_hash: str

class EncodedMedium:
    """Authoritative primitive: encoded runtime structure is the software-defined storage medium."""
    def __init__(self, rows:int=32, cols:int=32):
        self.rows=rows; self.cols=cols
        self.cells={}; self.objects={}; self.payloads={}
        self.genesis=root_hash({"rows":rows,"cols":cols,"kind":"ENCODED_MEDIUM"})

    def geometry_address(self,row:int,col:int,lineage:str)->str:
        if row<1 or col<1 or row>self.rows or col>self.cols:
            raise IndexError("outside encoded-medium geometry")
        return root_hash({"M":self.genesis,"row":row,"col":col,"lineage":lineage})

    def program_cell(self,row:int,col:int,state:int,provenance:str)->str:
        if state==0: raise ValueError("zero is reference/non-weighted state")
        if state not in {-3,-2,1,2,3}: raise ValueError("invalid weighted state")
        addr=self.geometry_address(row,col,"cell")
        self.cells[(row,col)]=EncodedCell((row,col),state,provenance)
        return addr

    def write_object(self,row:int,col:int,object_id:str,object_type:str,lineage:str,payload:bytes)->LogicalObject:
        address=self.geometry_address(row,col,lineage)
        obj=LogicalObject(object_id,object_type,address,lineage,hashlib.sha256(payload).hexdigest())
        self.objects[object_id]=obj; self.payloads[object_id]=payload
        return obj

class KEXStorageController:
    """Controller/translation layer over EncodedMedium."""
    def __init__(self, medium:EncodedMedium): self.medium=medium
    def allocate(self,*args,**kwargs): return self.medium.write_object(*args,**kwargs)
    def decode(self,object_id:str):
        obj=self.medium.objects[object_id]; payload=self.medium.payloads[object_id]
        return {"metadata":asdict(obj),"payload":payload.decode(),"verified":hashlib.sha256(payload).hexdigest()==obj.payload_hash}

class VFSProjection:
    """Downstream logical interpretation; never the storage substrate."""
    def __init__(self,controller:KEXStorageController): self.controller=controller; self.paths={}
    def mount(self,path:str,object_id:str):
        if object_id not in self.controller.medium.objects: raise KeyError(object_id)
        self.paths[path]=object_id
    def read(self,path:str): return self.controller.decode(self.paths[path])

@dataclass(frozen=True)
class MachineIdentity:
    machine_id:str
    braink_id:str
    lineage:str

class BRAINKMachine:
    def __init__(self,identity:MachineIdentity,medium:EncodedMedium,controller:KEXStorageController,vfs:VFSProjection):
        self.identity=identity; self.medium=medium; self.controller=controller; self.vfs=vfs
    def boot(self,root_object_id:str):
        root=self.controller.decode(root_object_id)
        if not root["verified"]: raise ValueError("root integrity failure")
        if root["metadata"]["object_type"]!="BRAINK_ROOT": raise TypeError("not BRAINK_ROOT")
        if root["metadata"]["lineage"]!=self.identity.lineage: raise ValueError("lineage mismatch")
        self.vfs.mount("/braink",root_object_id)
        receipt={"machine_id":self.identity.machine_id,"braink_id":self.identity.braink_id,"root_object":root_object_id,"root_address":root["metadata"]["address"],"medium_genesis":self.medium.genesis,"root_verified":True}
        receipt["proof"]=root_hash(receipt)
        return receipt

def reconcile_legacy_claim(label:str):
    mapping={"L#":"SOURCE_PROVENANCE","volume_registry":"OBSERVATION_PROOF_REGISTRY","sheet_rows":"PROJECTION_READBACK","VFS":"FILESYSTEM_RESOLVER_UTILITY","100TB_rows":"ADDRESS_LAW_PROJECTION","IP_endpoint":"CARRIER_PROJECTION"}
    return {"legacy":label,"authoritative":mapping.get(label,"UNRESOLVED"),"status":"RE-PARENTED" if label in mapping else "ATTENTION_FLAG"}
