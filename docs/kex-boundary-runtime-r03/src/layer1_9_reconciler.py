#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from dataclasses import dataclass,asdict

def canon(v): return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(v): return hashlib.sha256(v if isinstance(v,bytes) else canon(v)).hexdigest()
class LayerViolation(RuntimeError): pass

@dataclass(frozen=True)
class LayerState:
    layer:int
    generation:int
    input_root:str
    output_root:str
    status:str='ACTIVE'

class Layer1to9Reconciler:
    """Deterministic nine-layer state pipeline. Each layer is hash-bound to the prior output."""
    LAYERS={
      1:'INGRESS',2:'IDENTITY',3:'COORDINATE',4:'GEOMETRY',5:'PROPAGATION',
      6:'CONSENSUS',7:'EXECUTION',8:'OBSERVATION',9:'EVIDENCE'
    }
    def __init__(self): self.state={}
    def _derive(self,layer,generation,input_root,payload):
        if layer not in self.LAYERS: raise LayerViolation('LAYER_OUT_OF_RANGE')
        if generation<=0: raise LayerViolation('GENERATION_MUST_BE_POSITIVE')
        return sha({'layer':layer,'name':self.LAYERS[layer],'generation':generation,'input_root':input_root,'payload':payload})
    def apply(self,layer,generation,input_root,payload):
        expected='GENESIS' if layer==1 else self.state.get(layer-1,LayerState(0,0,'','','MISSING')).output_root
        if input_root!=expected: raise LayerViolation('UPSTREAM_ROOT_MISMATCH')
        old=self.state.get(layer)
        if old and generation<=old.generation: raise LayerViolation('STALE_LAYER_GENERATION')
        out=self._derive(layer,generation,input_root,payload)
        s=LayerState(layer,generation,input_root,out)
        self.state[layer]=s
        # Any downstream state is now causally stale and must be recomputed.
        for n in range(layer+1,10): self.state.pop(n,None)
        return s
    def reconcile_all(self,generation,payloads):
        if set(payloads)!=set(range(1,10)): raise LayerViolation('ALL_NINE_LAYERS_REQUIRED')
        root='GENESIS'; out=[]
        for layer in range(1,10):
            s=self.apply(layer,generation,root,payloads[layer]); out.append(s); root=s.output_root
        return tuple(out)
    @property
    def root(self):
        if 9 not in self.state: raise LayerViolation('PIPELINE_INCOMPLETE')
        return self.state[9].output_root
    def verify(self):
        root='GENESIS'
        for layer in range(1,10):
            s=self.state.get(layer)
            if not s: raise LayerViolation('PIPELINE_INCOMPLETE')
            if s.input_root!=root: raise LayerViolation('CHAIN_BROKEN')
            root=s.output_root
        return True
