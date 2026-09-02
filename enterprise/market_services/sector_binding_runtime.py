from __future__ import annotations
from pathlib import Path
import argparse, json, hashlib
from .service_broker import MarketServiceBroker
from .capability_registry import CapabilityRegistry
from .sector_router import SectorFunctionRouter

DEFAULT_BOUND={
 "vfs":"braink://vfs","database":"braink://sqlite","identity":"braink://agent-control",
 "documents":"braink://document-surface","calendar":"connector://google-calendar",
 "email":"connector://gmail","metrics":"braink://observer-memory","billing":"braink://ai-finops",
 "search":"braink://illlm/search"
}

def scan(state_dir:Path):
    state_dir.mkdir(parents=True,exist_ok=True)
    registry=CapabilityRegistry(state_dir/"sector_capabilities.sqlite3")
    for adapter,binding in DEFAULT_BOUND.items():
        registry.register_adapter(adapter,binding=binding,evidence={"state":"BOUND","source":"BRAINK_R2"})
    broker=MarketServiceBroker(state_dir/"market_service_broker.sqlite3")
    contracts=Path(__file__).resolve().parents[1]/"sector_products"/"SECTOR_PRODUCT_CONTRACTS_R1.json"
    router=SectorFunctionRouter(broker,registry,contracts)
    products=json.loads(contracts.read_text())["products"]
    classified=[]
    for sector,cfg in products.items():
        for fn in cfg["functions"]:
            c=router.classify(sector,fn);classified.append(c)
            if c["state"]=="CAPABILITY_GAP":
                for a in c["missing_adapters"]: registry.ensure_obligation(sector,fn,a)
    counts={}
    for c in classified: counts[c["state"]]=counts.get(c["state"],0)+1
    obligations=registry.open_obligations()
    adapters={}
    for o in obligations:
        x=adapters.setdefault(o["adapter_id"],{"adapter_id":o["adapter_id"],"affected":[]})
        x["affected"].append({"sector":o["sector"],"function":o["function"],"obligation_id":o["obligation_id"]})
    queue=[]
    for a,x in adapters.items():
        queue.append({"adapter_id":a,"work_module_id":"WM-ADAPTER-"+hashlib.sha256(a.encode()).hexdigest()[:16],
                      "affected_function_count":len(x["affected"]),"affected_sectors":sorted({v["sector"] for v in x["affected"]}),
                      "groups":["research","runtime","verification","evolution","proof"],"state":"OPEN_CAPABILITY"})
    return {"schema":"braink.sector-binding-runtime.r2/v1","total_functions":len(classified),
            "classification_counts":counts,"bound_adapters":sorted(DEFAULT_BOUND),
            "open_adapter_capabilities":len(queue),"open_function_adapter_obligations":len(obligations),
            "adapter_queue":sorted(queue,key=lambda x:(-x["affected_function_count"],x["adapter_id"]))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--state-dir",default=".braink/market-services-r2");ap.add_argument("--out")
    args=ap.parse_args();result=scan(Path(args.state_dir))
    text=json.dumps(result,indent=2)
    if args.out: Path(args.out).write_text(text+"\n")
    print(text)
if __name__=="__main__": main()
