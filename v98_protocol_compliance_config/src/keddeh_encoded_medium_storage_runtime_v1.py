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
        if object_id in self.objects:
            raise ValueError(f"object identity already resident: {object_id}")
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
    """Machine boots from a BRAINK root encoded inside the medium and may construct descendants by reference to the same resident controller/medium."""
    def __init__(self, identity:MachineIdentity, medium:EncodedMedium, controller:KEXStorageController, vfs:VFSProjection, parent_machine_id:str|None=None):
        self.identity=identity; self.medium=medium; self.controller=controller; self.vfs=vfs
        self.parent_machine_id=parent_machine_id
        self.boot_receipt=None
        self.children:dict[str,BRAINKMachine]={}
        self.child_receipts:list[dict[str,Any]]=[]

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
            "parent_machine_id":self.parent_machine_id,
            "root_object":braink_root_object_id,
            "root_address":root["metadata"]["address"],
            "medium_genesis":self.medium.genesis,
            "vfs_path":"/braink",
            "root_verified":True
        }
        receipt["proof"]=h(receipt); self.boot_receipt=receipt; return receipt

    def instantiate_child(self,row:int,col:int,identity:MachineIdentity,root_object_id:str,payload:bytes|None=None)->tuple["BRAINKMachine",dict[str,Any]]:
        """Construct a descendant without cloning the backing medium/controller.

        The child receives a distinct identity, lineage, VFS projection and BRAINK_ROOT,
        while inheriting the resident EncodedMedium and KEXStorageController by reference.
        The returned child is itself constructor-bearing and can recursively instantiate
        another descendant.
        """
        if self.boot_receipt is None:
            raise RuntimeError("parent machine must be booted before child construction")
        if identity.machine_id in self.children:
            raise ValueError(f"child identity already instantiated: {identity.machine_id}")
        if payload is None:
            payload=canonical({
                "identity":identity.braink_id,
                "mode":"resident-descendant",
                "constructor":"BRAINKMachine.instantiate_child",
                "parent_machine_id":self.identity.machine_id,
                "medium_genesis":self.medium.genesis,
            }).encode("utf-8")
        obj=self.controller.allocate(row,col,root_object_id,"BRAINK_ROOT",identity.lineage,payload)
        child_vfs=VFSProjection(self.controller)
        child=BRAINKMachine(identity,self.medium,self.controller,child_vfs,parent_machine_id=self.identity.machine_id)
        boot=child.boot(root_object_id)
        receipt={
            "constructor_machine_id":self.identity.machine_id,
            "constructor_boot_proof":self.boot_receipt["proof"],
            "child_machine_id":identity.machine_id,
            "child_braink_id":identity.braink_id,
            "child_lineage":identity.lineage,
            "child_root_object":root_object_id,
            "child_root_address":obj.address,
            "child_boot_proof":boot["proof"],
            "medium_genesis":self.medium.genesis,
            "medium_inherited_by_reference":child.medium is self.medium and child.controller is self.controller,
            "child_constructor_bearing":hasattr(child,"instantiate_child"),
        }
        receipt["proof"]=h(receipt)
        self.children[identity.machine_id]=child
        self.child_receipts.append(receipt)
        return child,receipt

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

def write_json(path:Path,obj:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

def activate(root:Path)->dict[str,Any]:
    medium=EncodedMedium(32,32)
    controller=KEXStorageController(medium)
    vfs=VFSProjection(controller)
    ident=MachineIdentity('MACHINE-KEX-20260822','BRAINK-ROOT-20260822','LINEAGE-KEX-20260822')
    for i,state in enumerate([1,2,3,-2,-3],start=1):
        medium.program_cell(1,i,state,'AUTHORED-LINE-SET')
    controller.allocate(2,2,'BRAINK-GENESIS','BRAINK_ROOT',ident.lineage,b'{"identity":"BRAINK-ROOT-20260822","mode":"resident","medium":"encoded"}')
    controller.allocate(2,3,'DOMAIN-keddeh.systems','DOMAIN_OBJECT',ident.lineage,b'{"domain":"keddeh.systems","role":"carrier-projection"}')
    machine=BRAINKMachine(ident,medium,controller,vfs)
    boot=machine.boot('BRAINK-GENESIS')
    vfs.mount('/domains/keddeh.systems','DOMAIN-keddeh.systems')
    domain=vfs.read('/domains/keddeh.systems')

    child_b,receipt_ab=machine.instantiate_child(3,2,MachineIdentity('MACHINE-KEX-B','BRAINK-B','LINEAGE-KEX-B'),'BRAINK-B-ROOT')
    child_c,receipt_bc=child_b.instantiate_child(4,2,MachineIdentity('MACHINE-KEX-C','BRAINK-C','LINEAGE-KEX-C'),'BRAINK-C-ROOT')
    recursion={
        "path":[machine.identity.machine_id,child_b.identity.machine_id,child_c.identity.machine_id],
        "A_to_B":receipt_ab,
        "B_to_C":receipt_bc,
        "same_medium":machine.medium is child_b.medium is child_c.medium,
        "same_controller":machine.controller is child_b.controller is child_c.controller,
        "independent_vfs":len({id(machine.vfs),id(child_b.vfs),id(child_c.vfs)})==3,
        "C_root_verified":child_c.boot_receipt["root_verified"],
    }
    recursion["proof"]=h(recursion)

    snapshot=medium.snapshot()
    receipt={
        'status':'VERIFIED',
        'architecture':authoritative_architecture(),
        'boot':boot,
        'recursive_instantiation':recursion,
        'domain_readback':domain,
        'medium_snapshot_proof':snapshot['proof'],
        'legacy_reconciliation':[reconcile_legacy_claim(x) for x in ['L#','volume_registry','sheet_rows','VFS','100TB_rows','IP_endpoint']]
    }
    receipt['proof']=h(receipt)
    write_json(root/'runtime_volume/encoded_medium/current.json',snapshot)
    write_json(root/'evidence/encoded_medium_reconciliation_receipt.json',receipt)
    write_json(root/'runtime_volume/outbox/encoded_medium_reconciliation/authoritative.handoff.json',{
        'kind':'ENCODED_MEDIUM_AUTHORITATIVE_HANDOFF','receipt_proof':receipt['proof'],'recursive_proof':recursion['proof'],'state':'VERIFIED'
    })
    return receipt

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',default='.')
    ap.add_argument('--activate',action='store_true')
    args=ap.parse_args()
    if args.activate:
        print(json.dumps(activate(Path(args.root)),indent=2))
