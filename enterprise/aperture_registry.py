from dataclasses import dataclass,asdict
from typing import Optional,Dict
import hashlib,json

def root(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class ApertureRecord:
    logical:str; state:str; aperture:Optional[str]; adapter:Optional[str]; backing:Optional[str]; generation:int; reason:Optional[str]=None
    @property
    def binding_root(self): return root(asdict(self))

class ApertureRegistry:
    def __init__(self):
        self.records:Dict[str,ApertureRecord]={}; self.generation=0
    def hole(self,logical,reason="UNRESOLVED"):
        self.generation+=1; r=ApertureRecord(logical,"HOLE",None,None,None,self.generation,reason); self.records[logical]=r; return r
    def bind(self,logical,aperture,adapter,backing):
        self.generation+=1; r=ApertureRecord(logical,"BOUND",aperture,adapter,backing,self.generation); self.records[logical]=r; return r
    def resolve(self,logical): return self.records.get(logical) or self.hole(logical)
