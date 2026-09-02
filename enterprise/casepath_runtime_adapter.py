from typing import Any,Mapping
from .aperture_registry import ApertureRegistry
from .native_fence_authority import NativeFenceAuthority
from .vfs_adapter import VFSAdapter
from .agent_runtime import AgentRuntime

CASEPATH_ADDRESS="KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA/TRUST-CENTRE"
CASEPATH_VFS="vfs://casepath/page/your-data"
CASEPATH_AGENT="agent://casepath/trust-centre"

class CasePathRuntimeAdapter:
    def __init__(self,vfs:VFSAdapter,apertures:ApertureRegistry,fences:NativeFenceAuthority,agents:AgentRuntime):
        self.vfs=vfs; self.apertures=apertures; self.fences=fences; self.agents=agents
    def bind(self):
        self.apertures.bind(CASEPATH_ADDRESS,"aperture://casepath/your-data","adapter://casepath/vfs",CASEPATH_VFS)
    def execute_patch(self,patch_id:str,payload:Mapping[str,Any]):
        binding=self.apertures.resolve(CASEPATH_ADDRESS)
        if binding.state!="BOUND": return {"status":"DEFERRED_HOLE","binding":binding.state}
        cert=self.fences.acquire(CASEPATH_VFS,"braink://casepath-publisher")
        agent=self.agents.invoke(CASEPATH_AGENT,"casepath.trust-centre.patch",{"patch_id":patch_id,"payload":dict(payload)})
        if agent["status"]!="EXECUTED": return agent
        receipt=self.vfs.commit(CASEPATH_VFS,{"patch_id":patch_id,"agent_effect":agent["effect"]},fence_generation=cert.generation)
        return {"status":receipt.status,"fence_generation":cert.generation,"vfs_receipt_root":receipt.receipt_root,"agent":agent}
