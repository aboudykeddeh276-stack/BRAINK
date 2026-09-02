from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
import subprocess, sys

class ProductionActuatorAdapter:
    adapter_id='adapter://keddeh/production-actuator'
    schemes=('actuator://',)
    capabilities=('PROBE','VALIDATE_ORIGIN','AMEND','RELEASE','READBACK')
    def __init__(self,actuator_path:str|None=None):
        self.actuator_path=Path(actuator_path).resolve() if actuator_path else None
    def probe(self,backing:str)->Dict[str,Any]:
        ok=bool(self.actuator_path and self.actuator_path.exists() and self.actuator_path.is_file())
        return {'status':'READY' if ok else 'UNBOUND_ACTUATOR','actuator_path':str(self.actuator_path) if self.actuator_path else None}
    def _run(self,args):
        if not self.actuator_path: return {'status':'UNBOUND_ACTUATOR'}
        p=subprocess.run([sys.executable,str(self.actuator_path),*args],capture_output=True,text=True,timeout=20)
        return {'status':'EXECUTED' if p.returncode==0 else 'FAILED','returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    def apply(self,backing:str,logical:str,operation:str,payload:Any=None)->Dict[str,Any]:
        payload=payload or {}
        if operation=='PROBE': return self.probe(backing)
        origin=payload.get('origin')
        if operation in {'VALIDATE_ORIGIN','AMEND','RELEASE'} and not origin:
            return {'status':'ORIGIN_UNBOUND','operation':operation}
        if operation=='VALIDATE_ORIGIN': return self._run(['validate-origin','--origin',origin])
        if operation=='AMEND': return self._run(['amend','--origin',origin,'--target',payload['target'],'--patch-id',payload['patch_id']])
        if operation=='RELEASE': return self._run(['release','--origin',origin,'--release-id',payload['release_id']])
        if operation=='READBACK':
            target=payload.get('target_url')
            if not target: return {'status':'TARGET_URL_UNBOUND'}
            return self._run(['readback','--target-url',target])
        return {'status':'UNSUPPORTED_OPERATION','operation':operation}
