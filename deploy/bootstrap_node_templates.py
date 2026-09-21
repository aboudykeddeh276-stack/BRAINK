#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from runtime.node.braink_node_templates import NodeTemplateRegistry

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_CATALOG=ROOT/"governance/node/BRAINK_CORE_NODE_TEMPLATES_R1.json"

def bootstrap(catalog_path: Path=DEFAULT_CATALOG, db_path: Path|None=None):
    data=json.loads(catalog_path.read_text(encoding="utf-8"))
    registry=NodeTemplateRegistry(db_path) if db_path else NodeTemplateRegistry()
    registered=[]
    for template in data.get("templates",[]):
        registered.append(registry.register_template(template))
    return {
        "status":"PASS",
        "catalog_schema":data.get("schema"),
        "registered_count":len(registered),
        "templates":[{"template_id":t["template_id"],"version":t["version"],"proof_root":t["proof_root"]} for t in registered]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--catalog",default=str(DEFAULT_CATALOG))
    p.add_argument("--db")
    a=p.parse_args()
    result=bootstrap(Path(a.catalog),Path(a.db) if a.db else None)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
