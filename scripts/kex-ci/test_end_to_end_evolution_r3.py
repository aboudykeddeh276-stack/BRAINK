import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from enterprise.evolution.evolution_pipeline import EvolutionPipeline
with tempfile.TemporaryDirectory() as td:
 d=Path(td); tree=d/"tree"; tree.mkdir()
 (tree/"service_runtime.py").write_text("x=1\n"); (tree/"proof_ledger.json").write_text("{}\n")
 p=EvolutionPipeline(d/"state")
 r=p.execute(tree,{"process":"EXECUTED","projection":"UNOBSERVED","step":2},
                   {"process":"EXECUTED","projection":"UNOBSERVED","step":3},
                   [{"name":"Agent Control","callable_functions":3,"test_pass_rate":1.0,"persistent_state":True,"audit_receipts":True,"billable_unit":"managed_agent","external_adapter_gaps":0},
                    {"name":"Sector Telemetry","callable_functions":1,"test_pass_rate":1.0,"persistent_state":True,"audit_receipts":True,"billable_unit":"telemetry_stream","external_adapter_gaps":2}])
 checks={"audit":r["audit"]["file_count"]==2,
 "drift":r["reconciliation"]["status"]=="DELTA_FOUND",
 "projection_not_gate":all(x["key"]!="projection" for x in r["reconciliation"]["deltas"]),
 "market_ready":r["market"][0]["validation"]["classification"]=="MARKET_READY_CORE",
 "gapped_not_ready":r["market"][1]["validation"]["classification"]!="MARKET_READY_CORE",
 "checkpoint":r["checkpoint"]["step"]==3,
 "ledger":len(p.ledger.read())==4 and len(r["ledger_root"])==64}
 print(json.dumps({"checks":checks,"result":r},indent=2))
 raise SystemExit(0 if all(checks.values()) else 2)
