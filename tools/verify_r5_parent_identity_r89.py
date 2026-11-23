#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys, os
from pathlib import Path
from html.parser import HTMLParser
import openpyxl
class Scripts(HTMLParser):
 def __init__(self): super().__init__(convert_charrefs=False); self.current=None; self.parts=[]; self.rows=[]
 def handle_starttag(self,t,a):
  if t.lower()=="script": self.current=dict(a); self.parts=[]
 def handle_data(self,d):
  if self.current is not None: self.parts.append(d)
 def handle_endtag(self,t):
  if t.lower()=="script" and self.current is not None: self.rows.append((self.current,"".join(self.parts))); self.current=None; self.parts=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--r5-parent",required=True); ap.add_argument("--cross-work",required=True); ap.add_argument("--workbook",required=True); a=ap.parse_args()
 p=Path(a.r5_parent); b=p.read_bytes(); h=Scripts(); h.feed(b.decode("utf-8")); xs=[s for attrs,s in h.rows if attrs.get("id")=="r5-system-manifest"]
 assert len(xs)==1; raw=xs[0]; m=json.loads(raw); cross=json.loads(Path(a.cross_work).read_text())
 ids=[m["identity"],m["parent"]["identity"]]
 for k in ["tool_volumes","system_volumes","runtime_resources","workbooks","unified_surfaces","candidates","specializations"]:
  for x in m.get(k,[]): ids.append(x.get("tool_identity") or x.get("address") or x.get("identity"))
 ids=[x for x in ids if x]; assert len(ids)==33 and len(set(ids))==33
 assert len(m["relations"])==23 and cross["identity"]=="braink://volume/r5/system-orchestrator/cross-work-r1" and len(cross["relations"])==32
 assert cross["parent_system_orchestrator"]["sha256"]==sha(b)
 wb=openpyxl.load_workbook(a.workbook,read_only=True,data_only=True)
 def get(sheet): return [r[1] for r in wb[sheet].iter_rows(min_row=2,values_only=True) if len(r)>1 and r[1]]
 old=get("R5_33"); reconciled=get("R5_Reconciliation")
 assert len(old)==33 and len(set(old))==33 and set(old)!=set(ids)
 assert set(ids)-set(old)=={"braink://volume/r5/system-orchestrator"}
 assert set(old)-set(ids)=={"braink://volume/r5/system-orchestrator/cross-work-r1"}
 assert len(reconciled)==33 and set(reconciled)==set(ids)
 print(json.dumps({"pid":os.getpid(),"exitCode":0,"r5Parent":{"bytes":len(b),"sha256":sha(b),"identity":m["identity"],"embeddedManifestBytes":len(raw.encode()),"embeddedManifestSha256":sha(raw.encode()),"baseRelations":len(m["relations"]),"canonicalIdentityCount":len(ids)},"crossWork":{"identity":cross["identity"],"relations":len(cross["relations"]),"parentBinding":cross["parent_system_orchestrator"]},"workbook":{"R5_33":{"rows":len(old),"missing":sorted(set(ids)-set(old)),"extra":sorted(set(old)-set(ids))},"R5_Reconciliation":{"rows":len(reconciled),"matchesCanonical":set(reconciled)==set(ids)}},"standaloneManifest":{"declaredSha256":cross["parent_system_orchestrator"]["manifest_sha256"],"embeddedParentManifestSha256":sha(raw.encode()),"same":False}},indent=2)); return 0
if __name__=="__main__":
 try: sys.exit(main())
 except Exception as e: print(f"VERIFY_FAILED: {type(e).__name__}: {e}",file=sys.stderr); sys.exit(1)
