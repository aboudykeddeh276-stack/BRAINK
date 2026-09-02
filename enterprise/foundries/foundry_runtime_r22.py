from __future__ import annotations
from pathlib import Path
import json, hashlib

ROOT=Path(__file__).resolve().parent
DEPLOYMENT=Path(__file__).resolve().parents[2]/"deployment/KEDDEH_SYSTEMS_R22_OPERATIONAL_FOUNDRIES.json"

CANONICAL_ARTIFACTS=(
    "FOUNDRY_OPERATIONAL_CORPUS_R22.json",
    "FOUNDRY_WORK_QUEUE_R22.json",
    "FOUNDRY_HR_TOPOLOGY_R22.json",
    "FOUNDRY_SERVER_TOPOLOGY_R22.json",
)

def deployment():
    return json.loads(DEPLOYMENT.read_text())

def expected_state():
    d=deployment()
    return {
        "release":d["release"],
        "foundries":d["counts"]["foundries"],
        "work_modules":d["counts"]["work_modules"],
        "hr_team_assignments":d["counts"]["hr_team_assignments"],
        "server_sets":d["counts"]["server_sets"],
        "state_root":d["state_root"],
        "virtual_space":d["canonical_virtual_space"],
        "artifacts":list(CANONICAL_ARTIFACTS),
    }

def qualify_materialized(root: str|Path):
    root=Path(root)
    missing=[name for name in CANONICAL_ARTIFACTS if not (root/name).exists()]
    if missing:
        return {"status":"HOLE","missing":missing}
    corpus=json.loads((root/CANONICAL_ARTIFACTS[0]).read_text())
    queue=json.loads((root/CANONICAL_ARTIFACTS[1]).read_text())
    hr=json.loads((root/CANONICAL_ARTIFACTS[2]).read_text())
    servers=json.loads((root/CANONICAL_ARTIFACTS[3]).read_text())
    state={"corpus":corpus,"queue":queue,"hr":hr,"servers":servers}
    state_root=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {
        "status":"QUALIFIED" if (
            len(corpus["foundries"])==18 and
            queue["count"]==190 and
            len(hr["assignments"])==96 and
            len(servers["server_sets"])==89
        ) else "MISMATCH",
        "materialized_state_root":state_root,
        "declared_state_root":deployment()["state_root"],
        "counts":{"foundries":len(corpus["foundries"]),"work_modules":queue["count"],"hr_assignments":len(hr["assignments"]),"server_sets":len(servers["server_sets"])}
    }

if __name__=="__main__":
    print(json.dumps(expected_state(),indent=2))
