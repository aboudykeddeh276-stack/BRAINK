from __future__ import annotations
import json, sys
from dataclasses import dataclass, asdict

AUTHORITATIVE_CHAIN = [
    "ENCODED_MEDIUM",
    "ZEROLESS_GEOMETRY",
    "KEX_STORAGE_CONTROLLER",
    "LOGICAL_OBJECTS",
    "VFS_RESOLVER",
]

FORBIDDEN = {
    "VFS_IS_STORAGE_MEDIUM",
    "SOURCE_LINE_IS_VOLUME",
    "SHEET_ROW_IS_CAPACITY",
    "REGISTRY_ROW_IS_ALLOCATION",
    "IP_IS_BRAINK_IDENTITY",
    "EXTERNAL_PROVIDER_IS_INTERNAL_AUTHORITY",
}

SECTORS = {
    "MACHINE_RUNTIME": {"requires": ["medium_root","controller_root","braink_root","lineage_root"],"effect": "machine boots controller-first; BRAINK resident/root object is decoded from machine medium"},
    "STORAGE": {"requires": ["encoded_medium","zeroless_geometry","controller"],"effect": "capacity/addressability derives from encoded geometry/controller contract, never source-line or sheet count"},
    "VFS": {"requires": ["role"],"effect": "VFS remains resolver/namespace only"},
    "MEMORY": {"requires": ["address_geometry","controller_binding"],"effect": "memory arrays are encoded/addressed state under controller semantics; workbook rows remain projections"},
    "NETWORK": {"requires": ["lexical_id","vector_id","carrier"],"effect": "BRAINK lexical/vector identity precedes IP/HTTP/QUIC carrier mapping"},
    "CLOUD": {"requires": ["canonical_object_id","replica_set","lineage"],"effect": "cloud is replicated machine-resident object state with stable canonical identity and distinct machine lineage"},
    "DOMAIN": {"requires": ["domain_object","lexical_id","server_root","storage_root"],"effect": "domain is a resident typed object; public DNS/registrar/TLS are adapter boundaries"},
    "DNS": {"requires": ["internal_root","authority_state"],"effect": "internal DNS state may mutate locally; public DNS promotion requires external authoritative readback/mutation"},
    "REGISTRAR": {"requires": ["internal_root","authority_state"],"effect": "registrar state is resident/internal; registry authority remains an external adapter boundary"},
    "TLS": {"requires": ["internal_root","authority_state"],"effect": "TLS intent/state is resident/internal; CA-issued state requires external certificate proof"},
    "AGENTS": {"requires": ["braink_id","machine_id","lineage_root"],"effect": "agents inherit machine/BRAINK identity and storage/controller roots rather than floating as unattached services"},
    "OBSERVER_PROOF": {"requires": ["observer_root","proof_root"],"effect": "workbook and receipts observe/project state; they do not manufacture substrate capacity or authority"},
    "DEPLOYMENT": {"requires": ["promotion_gate","readback"],"effect": "deployment status promotes only after runtime mutation and readback on the relevant authority boundary"},
}

@dataclass
class Result:
    sector: str
    status: str
    effect: str
    violations: list[str]

def validate(sector: str, contract: dict) -> Result:
    if sector not in SECTORS:
        return Result(sector,"FAIL","unknown sector",["UNKNOWN_SECTOR"])
    violations=[]
    semantics=set(contract.get("semantics",[]))
    violations.extend(sorted(semantics & FORBIDDEN))
    for key in SECTORS[sector]["requires"]:
        if key not in contract:
            violations.append("MISSING:"+key)
    if sector=="VFS" and contract.get("role")!="RESOLVER_ONLY":
        violations.append("VFS_ROLE_NOT_RESOLVER_ONLY")
    if sector in {"DNS","REGISTRAR","TLS"} and contract.get("authority_state")=="EXTERNAL_AUTHORITY_PROVEN" and not contract.get("external_readback"):
        violations.append("FALSE_EXTERNAL_PROMOTION")
    return Result(sector,"PASS" if not violations else "FAIL",SECTORS[sector]["effect"],violations)

def main():
    contracts = {
      "MACHINE_RUNTIME":{"medium_root":"DEVICE://M1/STORAGE","controller_root":"KEX_STORAGE_CONTROLLER://M1","braink_root":"BRAINK://M1","lineage_root":"LINEAGE://M1","semantics":[]},
      "STORAGE":{"encoded_medium":"SCRIPT_ENCODED_MEDIUM","zeroless_geometry":[-3,-2,1,2,3],"controller":"KEX_STORAGE_CONTROLLER","semantics":[]},
      "VFS":{"role":"RESOLVER_ONLY","semantics":[]},
      "MEMORY":{"address_geometry":"ZEROLESS_MATRIX","controller_binding":"KEX_STORAGE_CONTROLLER","semantics":[]},
      "NETWORK":{"lexical_id":"LEX://BRAINK/M1","vector_id":"VEC://M1/LOCAL","carrier":"HTTP/TCP/IPv4","semantics":[]},
      "CLOUD":{"canonical_object_id":"OBJ://GLOBAL/1","replica_set":["M1","M2"],"lineage":"DISTINCT_PER_MACHINE","semantics":[]},
      "DOMAIN":{"domain_object":"DOMAIN://keddeh.com","lexical_id":"LEX://DOMAIN/keddeh.com","server_root":"LEX://SERVER/GLOBAL","storage_root":"LEX://CLOUD/BRAINK/GLOBAL","semantics":[]},
      "DNS":{"internal_root":"LEX://DNS/keddeh.com","authority_state":"INTERNAL_RESIDENT_NOT_PUBLIC_AUTHORITY","semantics":[]},
      "REGISTRAR":{"internal_root":"LEX://REGISTRAR/keddeh.com","authority_state":"INTERNAL_RESIDENT_NOT_REGISTRY_AUTHORITY","semantics":[]},
      "TLS":{"internal_root":"LEX://TLS/keddeh.com","authority_state":"INTERNAL_RESIDENT_NOT_CA_ISSUED","semantics":[]},
      "AGENTS":{"braink_id":"BRAINK::M1","machine_id":"M1","lineage_root":"LINEAGE://M1","semantics":[]},
      "OBSERVER_PROOF":{"observer_root":"OBS://M1","proof_root":"PROOF://M1","semantics":[]},
      "DEPLOYMENT":{"promotion_gate":"READBACK_REQUIRED","readback":"PASS_OR_REMAIN_UNKNOWN","semantics":[]}
    }
    results=[asdict(validate(k,v)) for k,v in contracts.items()]
    negative = validate("VFS",{"role":"STORAGE_MEDIUM","semantics":["VFS_IS_STORAGE_MEDIUM"]})
    receipt={"schema":"braink.sector-impact.r22","authoritative_chain":AUTHORITATIVE_CHAIN,"sector_results":results,"negative_guard_test":asdict(negative),"all_sector_contracts_pass":all(x["status"]=="PASS" for x in results),"forbidden_semantics_rejected":negative.status=="FAIL" and "VFS_IS_STORAGE_MEDIUM" in negative.violations}
    receipt["status"]="PASS" if receipt["all_sector_contracts_pass"] and receipt["forbidden_semantics_rejected"] else "FAIL"
    print(json.dumps(receipt,indent=2)); return receipt

if __name__=="__main__":
    r=main(); out=sys.argv[1] if len(sys.argv)>1 else "/mnt/data/BRAINK_R22_SECTOR_IMPACT_RECEIPT.json"; open(out,"w").write(json.dumps(r,indent=2))
