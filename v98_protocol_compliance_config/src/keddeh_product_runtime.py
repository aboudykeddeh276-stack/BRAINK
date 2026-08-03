#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List
from keddeh_k_cloud_adapter import integrity_readback
REQUIRED={"applicationId","kind","entrypoint","runtime","route","vfsNamespace","suppliedCapabilities","modules","criticality","fallbackAdapter","launchCommand","testCommand","deploymentTarget","maturity"}
@dataclass(frozen=True)
class ProductReceipt:
    application_id:str; kind:str; module_count:int; modules_present:bool; entrypoint_present:bool; manifest_integrity_readback:bool; test_command_executed:bool; test_exit_code:int; receipt_written:bool; ledger_readback:bool; outbox_handoff:str; promotion_state:str; timestamp:float
def read_json(p:Path)->Dict[str,Any]: return json.loads(p.read_text(encoding="utf-8"))
def canonical_bytes(p:Dict[str,Any])->bytes: return (json.dumps(p,sort_keys=True,separators=(",",":"))+"\n").encode()
def append_ledger(p:Path,x:Dict[str,Any])->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as h:h.write(json.dumps(x,sort_keys=True)+"\n")
def ledger_contains(p:Path,hsh:str)->bool:
    return p.exists() and any(json.loads(l).get("entry_hash")==hsh for l in p.read_text().splitlines() if l.strip())
def load_product(root:Path,pid:str)->Dict[str,Any]:
    for p in read_json(root/"config"/"kapp_product_registry.json").get("products",[]):
        if p.get("applicationId")==pid:
            missing=REQUIRED-set(p)
            if missing: raise ValueError("product_missing_fields:"+",".join(sorted(missing)))
            return p
    raise KeyError("unknown_product:"+pid)
def build_manifest(root:Path,p:Dict[str,Any])->tuple[Path,str]:
    d=root/"runtime_volume"/"kapps"/p["applicationId"]; d.mkdir(parents=True,exist_ok=True)
    m={k:p[k] for k in ["applicationId","kind","entrypoint","runtime","route","vfsNamespace","suppliedCapabilities","criticality","fallbackAdapter","deploymentTarget"]}; m["version"]="1.0.0"
    mp=d/"k-app.manifest.json"; raw=canonical_bytes(m); mp.write_bytes(raw); h=hashlib.sha256(raw).hexdigest(); (d/"integrity.sha256").write_text(h+"  k-app.manifest.json\n")
    return mp,h
def run_product(root:Path,pid:str,emit_receipt:bool=False)->Dict[str,Any]:
    root=root.expanduser().resolve(); p=load_product(root,pid); modules=all((root/x).is_file() for x in p["modules"]); entry=(root/p["entrypoint"]).is_file(); mp,h=build_manifest(root,p)
    try: integrity=integrity_readback(mp,root/"runtime_volume"/"kapps"/pid/"integrity.sha256"); integrity_ok=bool(integrity.get("valid"))
    except Exception: integrity={"valid":False}; integrity_ok=False
    test=subprocess.run(p["testCommand"],shell=True,cwd=root,text=True,capture_output=True,check=False); ts=time.time(); ev=root/"evidence"/"products"; led=root/"runtime_volume"/"proof_bundles.ledger"; out=root/"runtime_volume"/"outbox"/"products"; ev.mkdir(parents=True,exist_ok=True); out.mkdir(parents=True,exist_ok=True)
    seed={"application_id":pid,"integrity":integrity,"modules_present":modules,"entrypoint_present":entry,"test_exit_code":test.returncode,"timestamp":ts}; eh=hashlib.sha256(canonical_bytes(seed)).hexdigest(); rp=ev/f"{pid}.receipt.json"; op=out/f"{pid}.{eh}.handoff.json"; promotion="LOCAL_PASS" if modules and entry and integrity_ok and test.returncode==0 else "LOCAL_FAIL"
    op.write_text(json.dumps({"handoff_id":eh,"application_id":pid,"receipt_path":str(rp),"next_target":p["deploymentTarget"],"status":"READY_FOR_TARGET_DEPLOYMENT" if promotion=="LOCAL_PASS" else "FAILED_CLOSED","created_at":ts},indent=2,sort_keys=True)+"\n")
    append_ledger(led,{"type":"kapp_product_receipt","entry_hash":eh,"application_id":pid,"promotion_state":promotion,"outbox_manifest":str(op)}); lr=ledger_contains(led,eh)
    r=ProductReceipt(pid,p["kind"],len(p["modules"]),modules,entry,integrity_ok,True,test.returncode,emit_receipt,lr,str(op),promotion if lr else "LOCAL_FAIL",ts); payload={"receipt":asdict(r),"stdout":test.stdout,"stderr":test.stderr,"integrity_readback":integrity,"target_host_deployed_here":False,"provider_execution_proven":False}
    if emit_receipt: rp.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return payload
def main(argv:List[str]|None=None)->int:
    a=argparse.ArgumentParser();a.add_argument("--root",default=".");a.add_argument("--product",required=True);a.add_argument("--emit-receipt",action="store_true");x=a.parse_args(argv);r=run_product(Path(x.root),x.product,x.emit_receipt);print(json.dumps(r["receipt"],indent=2,sort_keys=True));return 0 if r["receipt"]["promotion_state"]=="LOCAL_PASS" else 1
if __name__=="__main__":raise SystemExit(main())
