from __future__ import annotations
import hashlib,json,os,time
from pathlib import Path

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v):
    raw=v if isinstance(v,bytes) else canonical(v).encode()
    return hashlib.sha256(raw).hexdigest()

class ImmutableLedger:
    def __init__(self,path):
        self.path=Path(path).resolve(); self.path.parent.mkdir(parents=True,exist_ok=True)
    def read(self):
        if not self.path.exists(): return []
        out=[]; prev=None
        for line in self.path.read_text("utf-8").splitlines():
            if not line.strip(): continue
            try:r=json.loads(line)
            except json.JSONDecodeError: break
            core={k:r[k] for k in ("seq","kind","subject","payload","artifact_path","created_ns","previous_hash")}
            if r["previous_hash"]!=prev or r["record_hash"]!=digest(core): break
            out.append(r); prev=r["record_hash"]
        return out
    def append(self,kind,subject,payload,artifact_path=None):
        rows=self.read(); prev=rows[-1]["record_hash"] if rows else None
        ap=str(Path(artifact_path).resolve()) if artifact_path else None
        core={"seq":len(rows)+1,"kind":kind,"subject":subject,"payload":payload,"artifact_path":ap,"created_ns":time.time_ns(),"previous_hash":prev}
        row={**core,"record_hash":digest(core)}
        with self.path.open("ab",buffering=0) as f:
            f.write((canonical(row)+"\n").encode()); os.fsync(f.fileno())
        return row
    @property
    def root(self):
        rows=self.read(); return rows[-1]["record_hash"] if rows else digest([])
