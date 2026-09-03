import json, subprocess, sys
from pathlib import Path
SCRIPT=Path(__file__).parents[1]/"runtime/governance/skeleton_program.py"
def test_governance_pack_generation(tmp_path):
    cmd=[sys.executable,str(SCRIPT),"--kind","MODULE","--name","DNS Adapter","--sector","Infrastructure","--unit-id","INFRA-DNS-001","--owner","KEDDEH_SYSTEMS","--author","A.KEDDEH","--authority","KEDDEH_SYSTEMS_ADMINISTRATION","--purpose","Govern authoritative DNS adapter lifecycle","--runtime-boundary","BRAINK internal object to external DNS authority adapter","--proof-condition","external mutation plus independent DNS readback","--platform","linux","--platform","macos","--out",str(tmp_path)]
    cp=subprocess.run(cmd,check=True,capture_output=True,text=True)
    result=json.loads(cp.stdout)
    assert result["status"]=="PASS"
    target=Path(result["path"])
    control=json.loads((target/"unit.control.json").read_text())
    assert control["unit"]["unit_id"]=="INFRA-DNS-001"
    assert control["controls"]["filing"]["hash_required"] is True
    for name in control["artifacts"]: assert (target/name).exists()
    assert (target/"MANIFEST.sha256.json").exists()
