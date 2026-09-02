from dataclasses import dataclass
from typing import Dict
import secrets

@dataclass(frozen=True)
class FenceCertificate:
    resource:str; generation:int; owner:str; nonce:str

class NativeFenceAuthority:
    def __init__(self): self.heads:Dict[str,FenceCertificate]={}
    def acquire(self,resource,owner):
        prior=self.heads.get(resource); gen=1 if prior is None else prior.generation+1
        cert=FenceCertificate(resource,gen,owner,secrets.token_hex(16)); self.heads[resource]=cert; return cert
    def verify(self,cert): return self.heads.get(cert.resource)==cert
    def current(self,resource): return self.heads.get(resource)
