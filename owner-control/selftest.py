#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
R=ROOT/"owner_control_bridge.py"
M=ROOT/"casepath.site.json"
with tempfile.TemporaryDirectory() as d:
    db=str(Path(d)/"t.sqlite3")
    def run(*a):
        p=subprocess.run([sys.executable,str(R),"--db",db,*a],text=True,capture_output=True)
        assert p.returncode==0,(p.stdout,p.stderr)
        return json.loads(p.stdout)
    a=run("register","--manifest",str(M))
    assert a["state"]=="COMMITTED"
    run("capability","--project","appgprj_6a5e0e6d2bd08191948bfd94fcf1804b",
        "--provider","openai-chatgpt-sites","--capability","site.read,site.write,site.publish",
        "--authority","OWNER","--state","BLOCKED:PROVIDER_ACTUATOR_NOT_EXPOSED")
    s=run("status","--project","appgprj_6a5e0e6d2bd08191948bfd94fcf1804b")
    assert s["project"]["source_repo"] is None
    assert s["capabilities"][0]["state"].startswith("BLOCKED:")
    v=run("verify")
    assert v["ok"] and v["count"]==2
    print(json.dumps({"ok":True,"project":s["project"]["project_id"],"ledger":v},indent=2))
