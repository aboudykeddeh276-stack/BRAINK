from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import hashlib, json

def canonical(x:Any)->str:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def h(x:Any)->str:
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
    """Software-defined storage medium. Source provenance is not a storage address."""
    def __init__(self, rows:int=32, cols:int=32):
        self.rows=rows; self.cols=cols
        self.cells:dict[tuple[int,int],EncodedCell]={}
        self.objects:dict[str,LogicalObject]={}
        self.object_payloads:dict[str,bytes]={}
        self.genesis = h({"rows":rows,"cols":cols,"kind":"ENCODED_MEDIUM"})

    def geometry_address(self,row:int,col:int,lineage:str)->str:
        if row<1 or col<1 or row>self.rows or col>self.cols:
            raise IndexError("matrix coordinate outside encoded medium geometry")
        return h({"M":self.genesis,"row":row,"col":col,"lineage":lineage})

    def program_cell(self,row:int,col:int,state:int,provenance:str)->str:
        if state == 0:
            raise ValueError("zero is reserved as non-weighted/reference state in this medium")
        if state not in {-3,-2,1,2,3}:
            raise ValueError("invalid weighted state")
        addr=self.geometry_address(row,col,"cell")
        self.cells[(row,col)] = EncodedCell((row,col),state,provenance)
        return addr

    def write_object(self,row:int,col:int,object_id:str,object_type:str,lineage:str,payload:bytes)->LogicalObject:
        address=self.geometry_address(row,col,lineage)
        obj=LogicalObject(object_id,object_type,address,lineage,hashlib.sha256(payload).hexdigest())
        self.objects[object_id]=obj
        self.object_payloads[object_id]=payload
        return obj

    def read_object(self,object_id:str)->bytes:
        return self.object_payloads[object_id]

    def snapshot(self)->dict[str,Any]:
        snap={
            "genesis":self.genesis,
            "geometry":{"rows":self.rows,"cols":self.cols},
            "cells":[asdict(v) for _,v in sorted(self.cells.items())],
            "objects":{k:asdict(v) for k,v in sorted(self.objects.items())},
        }
        snap["proof"]=h(snap)
        return snap

class KEXStorageController:
    """Controller/translation layer over the encoded medium."""
    def __init__(self, medium:EncodedMedium):
        self.medium=medium

    def allocate(self,row:int,col:int,object_id:str,object_type:str,lineage:str,payload:bytes)->LogicalObject:
        return self.medium.write_object(row,col,object_id,object_type,lineage,payload)

    def decode(self,object_id:str)->dict[str,Any]:
        obj=self.medium.objects[object_id]
        payload=self.medium.read_object(object_id)
        return {"metadata":asdict(obj),"payload":payload.decode("utf-8"),"verified":hashlib.sha256(payload).hexdigest()==obj.payload_hash}

class VFSProjection:
    """Interpretation/navigation utility. It is not the storage medium."""
    def __init__(self, controller:KEXStorageController):
        self.controller=controller
        self.paths:dict[str,str]={}

    def mount(self,path:str,object_id:str):
        if object_id not in self.controller.medium.objects:
            raise KeyError(object_id)
        self.paths[path]=object_id

    def read(self,path:str)->dict[str,Any]:
        return self.controller.decode(self.paths[path])

@dataclass(frozen=True)
class MachineIdentity:
    machine_id:str
    braink_id:str
    lineage:str

class BRAINKMachine:
    """Machine boots from a BRAINK root already encoded inside the medium."""
    def __init__(self, identity:MachineIdentity, medium:EncodedMedium, controller:KEXStorageController, vfs:VFSProjection):
        self.identity=identity; self.medium=medium; self.controller=controller; self.vfs=vfs
        self.boot_receipt=None

    def boot(self, braink_root_object_id:str)->dict[str,Any]:
        root=self.controller.decode(braink_root_object_id)
        if not root["verified"]:
            raise ValueError("BRAINK root payload integrity failure")
        if root["metadata"]["object_type"]!="BRAINK_ROOT":
            raise TypeError("boot object is not BRAINK_ROOT")
        if root["metadata"]["lineage"]!=self.identity.lineage:
            raise ValueError("lineage mismatch")
        self.vfs.mount("/braink",braink_root_object_id)
        receipt={
            "machine_id":self.identity.machine_id,
            "braink_id":self.identity.braink_id,
            "root_object":braink_root_object_id,
            "root_address":root["metadata"]["address"],
            "medium_genesis":self.medium.genesis,
            "vfs_path":"/braink",
            "root_verified":True
        }
        receipt["proof"]=h(receipt); self.boot_receipt=receipt; return receipt

def reconcile_legacy_claim(label:str)->dict[str,str]:
    mapping={
        "L#":"SOURCE_PROVENANCE",
        "volume_registry":"OBSERVATION_PROOF_REGISTRY",
        "sheet_rows":"PROJECTION_READBACK",
        "VFS":"FILESYSTEM_RESOLVER_UTILITY",
        "100TB_rows":"ADDRESS_LAW_PROJECTION",
        "IP_endpoint":"CARRIER_PROJECTION",
    }
    return {"legacy":label,"authoritative":mapping.get(label,"UNRESOLVED"),"status":"RE-PARENTED" if label in mapping else "ATTENTION_FLAG"}

def authoritative_architecture()->dict[str,Any]:
    return {
        "primitive":"ENCODED_SCRIPT_RUNTIME_AS_SOFTWARE_DEFINED_STORAGE_MEDIUM",
        "chain":[
            "ENCODED_SCRIPT",
            "SOFTWARE_STORAGE_MEDIUM",
            "ZEROLESS_MATRIX_ADDRESS_GEOMETRY",
            "BRAINK_KEX_STORAGE_CONTROLLER",
            "VIRTUAL_BLOCK_OBJECT_SPACE",
            "VFS_INTERPRETATION",
            "FILES_BRAINK_DOMAINS_SERVERS_APPLICATIONS_STATE"
        ],
        "forbidden_reductions":[
            "source_line_is_storage_address",
            "sheet_row_is_volume",
            "VFS_is_storage_medium",
            "100TB_row_is_literal_partition",
            "IP_is_native_identity",
            "BRAINK_is_attached_after_machine_boot"
        ]
    }
