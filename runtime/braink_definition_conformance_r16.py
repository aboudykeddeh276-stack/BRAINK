from __future__ import annotations
from pathlib import Path
import json, sys, hashlib

REGISTRY = Path(sys.argv[1] if len(sys.argv) > 1 else "/mnt/data/BRAINK_CANONICAL_DEFINITIONS_R16.json")
MANIFEST = Path(sys.argv[2] if len(sys.argv) > 2 else "/mnt/data/BRAINK_IMPLEMENTATION_MANIFEST_R16.json")
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "/mnt/data/BRAINK_DEFINITION_CONFORMANCE_R16_RECEIPT.json")

def load(p): return json.loads(Path(p).read_text())

registry = load(REGISTRY)
manifest = load(MANIFEST)

results = []
for item in manifest["instances"]:
    ident = item["definition_id"]
    definition = registry["definitions"].get(ident)
    if definition is None:
        results.append({"instance_id": item["instance_id"], "definition_id": ident, "status": "FAIL_UNKNOWN_DEFINITION"})
        continue

    required_props = set(definition["properties"])
    impl_props = set(item.get("properties", []))
    missing_props = sorted(required_props - impl_props)

    forbidden = set(definition["invalid_interpretations"])
    interpretations = set(item.get("interpretations", []))
    forbidden_hits = sorted(forbidden & interpretations)

    required_proofs = set(definition["proof_conditions"])
    proofs = set(item.get("proof_conditions_satisfied", []))
    missing_proofs = sorted(required_proofs - proofs)

    allowed_transitions = set(definition["traversal_rules"])
    attempted = set(item.get("transitions_used", []))
    invalid_transitions = sorted(attempted - allowed_transitions)

    version_match = item.get("definition_version") == definition["version"]
    pass_state = version_match and not missing_props and not forbidden_hits and not missing_proofs and not invalid_transitions

    results.append({
        "instance_id": item["instance_id"],
        "definition_id": ident,
        "definition_version": definition["version"],
        "version_match": version_match,
        "missing_properties": missing_props,
        "forbidden_interpretations": forbidden_hits,
        "missing_proofs": missing_proofs,
        "invalid_transitions": invalid_transitions,
        "status": "PASS_CONFORMS" if pass_state else "FAIL_NONCONFORMING"
    })

receipt = {
    "schema": "braink.definition-conformance.r16.receipt",
    "registry_sha256": hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
    "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
    "results": results,
    "status": "PASS" if all(r["status"] == "PASS_CONFORMS" for r in results) else "FAIL"
}
OUT.write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt, indent=2))
