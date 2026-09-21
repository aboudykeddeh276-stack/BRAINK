#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sqlite3
from pathlib import Path
from runtime.node.braink_node_templates import NodeTemplateRegistry

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CATALOG=ROOT/"governance/node/BRAINK_CORE_NODE_TEMPLATES_R1.json"
DEFAULT_EXPORT_DIR=Path(os.environ.get("BRAINK_NODE_INSTANCE_EXPORT_DIR",str(Path.home()/".braink/node-instances")))

CORE_INSTANCES=[
    {
      "template_id":"TPL_HCI_STATUS_CARD_V1","version":"1.0.0",
      "instance_id":"node:hci:native-dashboard",
      "initial_state":{"status":"UNOBSERVED","surface":"native-dashboard"},
      "observer_relations":[{"observer_relation_id":"observer:native-dashboard","observer_context":"NATIVE_APP"}],
      "integration_edges":[{"direction":"IN","source":"BRAINK_RUNTIME","target":"native-dashboard","interface":"status.read","state":"DECLARED"}]
    },
    {
      "template_id":"TPL_HCI_COMMAND_CARD_V1_1","version":"1.1.0",
      "instance_id":"node:hci:native-command-card",
      "initial_state":{"status":"READY","surface":"native-chat-input"},
      "observer_relations":[{"observer_relation_id":"observer:native-command-card","observer_context":"NATIVE_APP"}],
      "integration_edges":[{"direction":"OUT","source":"native-command-card","target":"BRAINK_DIRECTOR","interface":"command.emit","state":"DECLARED"}]
    }
]

def ensure_instance(registry: NodeTemplateRegistry, spec: dict):
    try:
        return registry.get_instance(spec["instance_id"])
    except KeyError:
        return registry.instantiate(
            spec["template_id"],spec["version"],instance_id=spec["instance_id"],
            initial_state=spec.get("initial_state") or {},
            observer_relations=spec.get("observer_relations") or [],
            integration_edges=spec.get("integration_edges") or [],
            attribution_extensions=[{"type":"BOOTSTRAPPED_AS","target":spec["instance_id"]}]
        )

def bootstrap(catalog_path: Path=DEFAULT_CATALOG, db_path: Path|None=None, export_dir: Path=DEFAULT_EXPORT_DIR):
    data=json.loads(catalog_path.read_text(encoding="utf-8"))
    registry=NodeTemplateRegistry(db_path) if db_path else NodeTemplateRegistry()
    registered=[]
    for template in data.get("templates",[]):
        registered.append(registry.register_template(template))

    export_dir.mkdir(parents=True,exist_ok=True)
    instances=[]
    for spec in CORE_INSTANCES:
        instance=ensure_instance(registry,spec)
        out=export_dir/(spec["instance_id"].replace(":","_")+".json")
        tmp=out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(instance,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        os.replace(tmp,out)
        instances.append({"instance_id":instance["instance_id"],"proof_root":instance["proof_root"],"export":str(out)})

    return {
        "status":"PASS","catalog_schema":data.get("schema"),
        "registered_count":len(registered),
        "templates":[{"template_id":t["template_id"],"version":t["version"],"proof_root":t["proof_root"]} for t in registered],
        "core_instances":instances
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",default=str(DEFAULT_CATALOG))
    p.add_argument("--db")
    p.add_argument("--export-dir",default=str(DEFAULT_EXPORT_DIR))
    a=p.parse_args()
    result=bootstrap(Path(a.catalog),Path(a.db) if a.db else None,Path(a.export_dir))
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
