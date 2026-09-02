from __future__ import annotations
import json
from pathlib import Path
from .capability_registry import CapabilityRegistry

SHARED_FUNCTION_MAP={
 "authorize_action":("agent_control","authorize_action"),
 "fence_stale_actor":("agent_control","fence_agent"),
 "validate_handoff":("handoff_guard","validate_handoff"),
 "checkpoint_work":("runtime_supervisor","checkpoint"),
 "checkpoint_run":("runtime_supervisor","checkpoint"),
 "rehydrate_run":("runtime_supervisor","rehydrate"),
 "resume_work":("runtime_supervisor","rehydrate"),
 "export_audit_pack":("proof_service","export_audit_pack"),
 "measure_outcome":("ai_finops","measure_run"),
 "measure_customer_outcome":("ai_finops","measure_run"),
 "attribute_cost":("ai_finops","measure_run"),
}

class SectorFunctionRouter:
    def __init__(self,broker,registry:CapabilityRegistry,contracts_path):
        self.broker=broker;self.registry=registry;self.contracts=json.loads(Path(contracts_path).read_text())["products"]
    def classify(self,sector,function):
        product=self.contracts.get(sector)
        if not product or function not in product["functions"]: return {"state":"UNKNOWN_FUNCTION","sector":sector,"function":function}
        if function in SHARED_FUNCTION_MAP:
            service,shared_fn=SHARED_FUNCTION_MAP[function]
            return {"state":"EXECUTABLE_SHARED","service":service,"shared_function":shared_fn,"sector":sector,"function":function,"missing_adapters":[]}
        missing=[a for a in product["adapters"] if not (self.registry.adapter(a) and self.registry.adapter(a)["status"]=="BOUND")]
        return {"state":"EXECUTABLE_DOMAIN" if not missing else "CAPABILITY_GAP","sector":sector,"function":function,"missing_adapters":missing}
    def dispatch(self,sector,function,payload,customer_id="customer://local"):
        c=self.classify(sector,function)
        if c["state"]=="EXECUTABLE_SHARED":
            r=self.broker.execute(c["service"],c["shared_function"],payload,customer_id=customer_id,authority_scope=f"SECTOR:{sector}")
            return {"route":c,"execution":r}
        if c["state"]=="CAPABILITY_GAP":
            obligations=[self.registry.ensure_obligation(sector,function,a) for a in c["missing_adapters"]]
            return {"route":c,"status":"DEFERRED_CAPABILITY_CLOSURE","obligations":obligations}
        if c["state"]=="EXECUTABLE_DOMAIN": return {"route":c,"status":"READY_FOR_DOMAIN_HANDLER_BINDING"}
        return {"route":c,"status":"REJECTED"}
