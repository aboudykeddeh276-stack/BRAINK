from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any,Optional
import hashlib,json,os,tempfile,time

def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def root(v): return hashlib.sha256(canonical(v)).hexdigest()

@dataclass(frozen=True)
class VFSReceipt:
    operation:str; address:str; status:str; before_root:Optional[str]; after_root:Optional[str]; generation:int; produced_at_ns:int
    @property
    def receipt_root(self): return root(asdict(self))

class VFSAdapter:
    def __init__(self,root_dir:Path):
        self.root_dir=Path(root_dir); self.root_dir.mkdir(parents=True,exist_ok=True)
    def _path(self,address:str)->Path:
        return self.root_dir/f"{hashlib.sha256(address.encode()).hexdigest()}.json"
    def _load(self,address):
        p=self._path(address)
        if not p.exists(): return None
        return json.loads(p.read_text("utf-8"))
    def read(self,address):
        obj=self._load(address)
        if obj is None:return {"status":"HOLE","address":address}
        return {"status":"READ","address":address,"object":obj,"state_root":root(obj)}
    def commit(self,address,payload:Any,expected_root:Optional[str]=None,fence_generation:Optional[int]=None):
        p=self._path(address); prior=self._load(address); before=root(prior) if prior is not None else None
        prior_generation=prior.get("generation",0) if prior else 0
        if expected_root is not None and expected_root!=before:
            return VFSReceipt("WRITE",address,"REJECTED_EXPECTED_ROOT",before,before,prior_generation,time.time_ns())
        if fence_generation is not None and fence_generation<=prior_generation:
            return VFSReceipt("WRITE",address,"REJECTED_STALE_FENCE",before,before,prior_generation,time.time_ns())
        generation=max(prior_generation+1,fence_generation or 0)
        obj={"schema":"braink.vfs.object/v1","address":address,"generation":generation,"payload":payload,"predecessor_root":before}
        encoded=canonical(obj)
        with tempfile.NamedTemporaryFile("wb",dir=p.parent,delete=False,prefix=".vfs.",suffix=".tmp") as f:
            tmp=Path(f.name); f.write(encoded); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,p)
        fd=os.open(str(p.parent),os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
        return VFSReceipt("WRITE",address,"COMMITTED",before,root(obj),generation,time.time_ns())
