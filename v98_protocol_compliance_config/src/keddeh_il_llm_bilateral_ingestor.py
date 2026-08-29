#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, time
from pathlib import Path
from typing import Any, Dict, Iterable, List


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle: handle.write(json.dumps(payload, sort_keys=True) + "\n")

def point(kind: str, source_id: str, payload: Any, parent: str | None=None) -> Dict[str, Any]:
    body={"kind":kind,"source_id":source_id,"parent":parent,"payload":payload,"complete":1,"preserved":True}
    body["point_id"]="point://il-llm/"+canonical_hash(body)
    return body

def iter_word_points(source_id: str, records: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for record in records:
        word = point("COMPLETE_WORD", source_id, record)
        yield word
        for context in record.get("contexts", []):
            yield point("WORD_CONTEXT", source_id, context, parent=word["point_id"])

def iter_module_points(source_id: str, records: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for record in records:
        module=point("IL_LLM_MODULE",source_id,record); yield module
        for field in ("input","output","state_transition","display_surface","test_condition","receipt_id","owner","failure_mode","status"):
            if field in record: yield point("MODULE_FIELD",source_id,{"field":field,"value":record[field]},parent=module["point_id"])

def ingest_source(path: Path, source_id: str) -> List[Dict[str, Any]]:
    suffix=path.suffix.lower()
    if suffix==".json":
        data=read_json(path)
        records=data if isinstance(data,list) else [data]
        if records and isinstance(records[0],dict) and "word_id" in records[0]: return list(iter_word_points(source_id,records))
        if records and isinstance(records[0],dict) and "name" in records[0] and "state_transition" in records[0]: return list(iter_module_points(source_id,records))
        points=[]
        def walk(value: Any, parent: str | None=None, key: str="root") -> None:
            p=point("JSON_DATUM",source_id,{"key":key,"value":value if not isinstance(value,(dict,list)) else None},parent); points.append(p)
            if isinstance(value,dict):
                for k,v in value.items(): walk(v,p["point_id"],str(k))
            elif isinstance(value,list):
                for i,v in enumerate(value): walk(v,p["point_id"],str(i))
        walk(data); return points
    if suffix==".csv":
        rows=list(csv.DictReader(path.open(encoding="utf-8",newline="")))
        return [point("CSV_ROW",source_id,row) for row in rows]
    text=path.read_text(encoding="utf-8",errors="replace")
    return [point("TEXT_LINE",source_id,{"line":i,"text":line}) for i,line in enumerate(text.splitlines(),1)]

def run(root: Path, source_paths: List[Path], emit_receipt: bool=False) -> Dict[str, Any]:
    root=root.resolve(); manifest=read_json(root/"config"/"il_llm_corpus_manifest.json")
    source_map={s["title"]:s for s in manifest["sources"]}
    all_points=[]; source_results=[]
    for path in source_paths:
        descriptor=source_map.get(path.name,{"sourceId":f"source://il-llm/{path.stem}","title":path.name})
        pts=ingest_source(path,descriptor["sourceId"]); all_points.extend(pts)
        source_results.append({"source_id":descriptor["sourceId"],"path":str(path),"points":len(pts),"status":"INGESTED"})
    forward: Dict[str,List[str]]={}; reverse: Dict[str,Dict[str,Any]]={}
    for p in all_points:
        forward.setdefault(p["source_id"],[]).append(p["point_id"])
        reverse[p["point_id"]]={"source_id":p["source_id"],"parent":p.get("parent"),"kind":p["kind"]}
        append_jsonl(root/"runtime_volume"/"il_llm"/"points.ledger",p)
    write_json(root/"runtime_volume"/"il_llm"/"forward_index.json",forward)
    write_json(root/"runtime_volume"/"il_llm"/"reverse_index.json",reverse)
    discovered={p.name for p in source_paths}
    missing=[]
    for src in manifest["sources"]:
        if src["title"] not in discovered:
            packet={"source_id":src["sourceId"],"title":src["title"],"state":"SOURCE_DISCOVERED_PENDING_MOUNT","required_action":"mount exact source bytes and rerun bilateral ingestion","preservation":"source identity retained","global_stop":False}
            missing.append(packet); write_json(root/"runtime_volume"/"workplans"/"il_llm_source_mount"/(canonical_hash(packet)+".json"),packet)
    receipt={"version":"V101-ILLLM-BILATERAL-1","sources_ingested":source_results,"points_preserved":len(all_points),"forward_index_entries":sum(len(v) for v in forward.values()),"reverse_index_entries":len(reverse),"pending_source_mounts":missing,"bilateral_readback":len(reverse)==len(all_points),"global_stop":False,"timestamp":time.time()}
    receipt["receipt_id"]=canonical_hash(receipt)
    if emit_receipt: write_json(root/"evidence"/"il_llm_bilateral_ingestion_receipt.json",receipt)
    return receipt

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--root",default="."); p.add_argument("--source",action="append",default=[]); p.add_argument("--emit-receipt",action="store_true"); a=p.parse_args()
    result=run(Path(a.root),[Path(x) for x in a.source],a.emit_receipt); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result["bilateral_readback"] else 1
if __name__=="__main__": raise SystemExit(main())
