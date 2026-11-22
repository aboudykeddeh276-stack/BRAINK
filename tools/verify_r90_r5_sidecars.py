#!/usr/bin/env python3
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

EXPECTED = {
 "KEDDEH_LINUX_COMPUTER_v71_AUTOSTART_LINUX_SERVERS.html": (5093904,"a9b8cba41499dd95a4a8bb0c735e408c592517eccd1514b683d372b52325e3e4"),
 "KEDDEH_LINUX_COMPUTER_v71_RESEARCH_SECTOR_FABRIC_S26_S29.html": (5103217,"9aaf61466c123acc0554ce0a1514b40bd57b824b9bfeea0ac2b3313e150d294b"),
 "BRAINK_IL_LLM_UNIFIED_HCI_v2.html": (54952,"9aeece2e7ee166420a2da45337c952beee7d1b2c1811bf52c36afb6e76d39bad"),
 "KEDDEH_BRAINK_LIBRARY_DNA_EVOLUTION_R1.html": (766963,"3dbd9009b34c41f88e1349e9faec3d786f93f6ce79e974da07f3c2036b4c650e"),
 "runtime-abi.json": (772,"358dc830620480130f3a421bd01ff006d9ce8247923eed5ee036b0a85686ad2f"),
 "runtime-registry.json": (1441,"7dbd586e68475449a435b62c0eeb0362aaa7b8d102557ffafce6dbc6799ccd96"),
 "runtime-contract.v2.json": (1917,"ae2108098838e97416174d48099b8e329f660bc273ccb59892c846eca1abd0fa"),
 "braink-sdos.service": (309,"a6118a759afefab1dbb0795117116a5b02991cdafee55df432c4a01ae7b935da"),
 "braink-infrastructure-mesh-ignition.mjs": (12890,"4e02d1e09fd484844387a12c699a8d564f0cc86c301b6e334f59f64051670af7"),
 "KEDDEH_RESIDENT_ENGINEERING_CORPUS_PROJECTION_v3_SERVICE_LAYERS.html": (4023659,"254f466c559c29b8814bb434724abbebd20bfcdf54c7af143ee74fe9c098a09b"),
 "BRAINK_IL_LLM_KEX_V11_ENGINEERING_CONTROL_PLANE.html": (6337343,"484f05f39c487b7573404c21a7f024c764e41812781e80c2929304e76deb2965"),
}
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--source-dir",required=True)
 a=ap.parse_args(); root=Path(a.source_dir); failures=[]; results=[]
 for name,(size,digest) in EXPECTED.items():
  p=root/name
  if not p.is_file(): failures.append(name+":missing"); continue
  b=p.read_bytes(); got=hashlib.sha256(b).hexdigest()
  ok=len(b)==size and got==digest
  results.append({"file":name,"bytes":len(b),"sha256":got,"pass":ok})
  if not ok: failures.append(name+":hash_or_size_mismatch")
 for name in ("runtime-abi.json","runtime-registry.json","runtime-contract.v2.json"):
  try: json.loads((root/name).read_text())
  except Exception as e: failures.append(name+":json:"+str(e))
 r=subprocess.run(["node","--check",str(root/"braink-infrastructure-mesh-ignition.mjs")],capture_output=True,text=True)
 if r.returncode: failures.append("mesh-ignition-node-check:"+r.stderr)
 print(json.dumps({"pid":__import__("os").getpid(),"checked":len(results),"passed":sum(x["pass"] for x in results),"failures":failures,"results":results},indent=2))
 return 1 if failures else 0
if __name__=="__main__": raise SystemExit(main())
