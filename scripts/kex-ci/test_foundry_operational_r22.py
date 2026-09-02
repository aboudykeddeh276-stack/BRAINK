import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.foundries.foundry_runtime_r22 import expected_state
s=expected_state()
checks={
 "release":s["release"]=="R22",
 "foundries":s["foundries"]==18,
 "work_modules":s["work_modules"]==190,
 "hr_team_assignments":s["hr_team_assignments"]==96,
 "server_sets":s["server_sets"]==89,
 "virtual_space":s["virtual_space"]=="/KEDDEH_SYSTEMS/FOUNDRIES/R22_OPERATIONAL",
 "artifacts":len(s["artifacts"])==4,
 "state_root":len(s["state_root"])==64,
}
print(json.dumps({"checks":checks,"state":s},indent=2))
raise SystemExit(0 if all(checks.values()) else 2)
