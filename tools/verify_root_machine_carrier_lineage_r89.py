#!/usr/bin/env python3
from __future__ import annotations
import argparse, base64, hashlib, html, json, re, sys, os
from pathlib import Path
from html.parser import HTMLParser

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False); self.current=None; self.parts=[]; self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="script": self.current=dict(attrs); self.parts=[]
    def handle_data(self,data):
        if self.current is not None: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="script" and self.current is not None:
            self.rows.append((self.current,"".join(self.parts))); self.current=None; self.parts=[]

def sha(b): return hashlib.sha256(b).hexdigest()
def scripts(path):
    p=Scripts(); p.feed(Path(path).read_text(encoding="utf-8")); out={}
    for a,b in p.rows:
        if a.get("id"): out.setdefault(a["id"],[]).append(b)
    return p.rows,out
def one(m,k):
    if len(m.get(k,[]))!=1: raise ValueError(f"{k}: expected one script, got {len(m.get(k,[]))}")
    return m[k][0]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--v27",required=True); ap.add_argument("--v28",required=True); ap.add_argument("--r4-s29",required=True)
    a=ap.parse_args(); paths={"v27":Path(a.v27),"v28":Path(a.v28),"r4S29Container":Path(a.r4_s29)}
    parsed={}; out={}
    for key,p in paths.items():
        b=p.read_bytes(); rows,m=scripts(p); p11=one(m,"p11-carrier-model"); arch=one(m,"architecture-root")
        p11j=json.loads(p11); archj=json.loads(arch)
        root=next(x for x in p11j["carriers"] if x["carrier_id"]=="carrier://html/root-v16")
        parsed[key]=(p11,arch,p11j,archj,root,m)
        out[key]={"name":p.name,"bytes":len(b),"sha256":sha(b),"script_count":len(rows),"p11_bytes":len(p11.encode()),"p11_sha256":sha(p11.encode()),"architecture_bytes":len(arch.encode()),"architecture_sha256":sha(arch.encode())}
    base=parsed["v27"]
    for key in ["v28","r4S29Container"]:
        assert sha(parsed[key][0].encode())==sha(base[0].encode())
        assert sha(parsed[key][1].encode())==sha(base[1].encode())
        assert parsed[key][4]==base[4]
    root=base[4]; arch=base[3]; dims=arch["identity_dimensions"]
    assert root["bytes"]==3741393 and root["integrity"]=="50a894e92fe06be3b19168d741b84bf6f6169fbc7130bbf0c2332649d8371c53"
    assert dims["logical_identity"]=="volume://keddeh/braink/root"
    assert dims["carrier_identity"]=="carrier://html/keddeh-unified-v11"
    assert dims["projection_identity"]=="projection://volume/root-hci"
    assert dims["materialisation_identity"]=="materialisation://browser/current"
    v28m=parsed["v28"][5]
    conv=json.loads(html.unescape(one(v28m,"ks-20260815-convergence-manifest")))
    assert conv["parent_sha256"]==out["v27"]["sha256"]
    r4=paths["r4S29Container"].read_bytes(); hstart=re.search(rb"<html\b",r4,re.I); hend=r4.lower().rfind(b"</html>")+7
    lexical=r4[hstart.start():hend]
    payload=base64.b64decode(one(parsed["r4S29Container"][5],"s29q-r4payload").strip(),validate=True)
    assert len(payload)==13050075 and sha(payload)=="5e55b7c3179d2afd246929bd5793186af65c8025ca4b65a32a06b10dbfe6c592"
    assert sha(r4)!=root["integrity"] and sha(lexical)!=root["integrity"] and sha(payload)!=root["integrity"]
    print(json.dumps({"pid":os.getpid(),"exitCode":0,"sources":out,"p11RootV16Declaration":root,"rootMachineIdentityDimensions":dims,"architectureRoot":{"namespaceCount":len(arch["namespace_registry"]),"relationTypeCount":len(arch["relation_types"]),"carrierClassCount":len(arch["carrier_classes"]),"planResolutionCount":len(arch["plan_resolution"]),"planStates":arch["plan_state"],"recursiveLaw":arch["recursive_law"]},"v28Parent":{"artifact":conv["parent_artifact"],"sha256":conv["parent_sha256"],"matchesV27":True},"r4Outer":{"bytes":len(r4),"sha256":sha(r4),"lexicalHtmlBytes":len(lexical),"lexicalHtmlSha256":sha(lexical)},"r4ExecutablePayload":{"bytes":len(payload),"sha256":sha(payload)},"rootV16ExactSourceRecovered":False},indent=2))
    return 0
if __name__=="__main__":
    try: sys.exit(main())
    except Exception as e: print(f"VERIFY_FAILED: {type(e).__name__}: {e}",file=sys.stderr); sys.exit(1)
