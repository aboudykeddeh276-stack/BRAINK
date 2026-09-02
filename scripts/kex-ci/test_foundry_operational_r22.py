import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.foundries.foundry_runtime_r22 import expected_state,qualify_materialized
from enterprise.foundries.materialize_foundry_corpus_r22 import materialize
s=expected_state()
with tempfile.TemporaryDirectory() as td:
    materialize(td)
    q=qualify_materialized(td)
checks={
 "release":s["release"]=="R22",
 "foundries":s["foundries"]==18,
 "work_modules":s["work_modules"]==190,
 "hr_team_assignments":s["hr_team_assignments"]==96,
 "server_sets":s["server_sets"]==89,
 "virtual_space":s["virtual_space"]=="/KEDDEH_SYSTEMS/FOUNDRIES/R22_OPERATIONAL",
 "materialized_qualified":q["status"]=="QUALIFIED",
 "materialized_foundries":q["counts"]["foundries"]==18,
 "materialized_work_modules":q["counts"]["work_modules"]==190,
 "materialized_hr":q["counts"]["hr_assignments"]==96,
 "materialized_servers":q["counts"]["server_sets"]==89,
 "state_root_declared":len(s["state_root"])==64,
}
print(json.dumps({"checks":checks,"state":s,"materialized":q},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
