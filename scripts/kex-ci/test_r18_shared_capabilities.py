from enterprise.sector_runtime import SectorRuntime
from enterprise.braink_sector_federation import BrainKSectorFederation
from enterprise.audit_observability import AuditLog
from enterprise.observer_policy import ObserverPolicyEngine

# Work-module and evidence capabilities.
registry = {
    'sectors': {
        'AI_CLOUD_INFRA': {
            'market_functions': ['runtime.process'],
            'controls': ['proof'],
            'required_adapters': ['runtime']
        }
    }
}
rt = SectorRuntime(registry)
mods = rt.work_modules('AI_CLOUD_INFRA')
assert len(mods) == 1 and mods[0].function == 'runtime.process'
edge = rt.supervise('agent://supervisor','agent://worker',mods[0],'KEX://RUNTIME/')
receipt = rt.complete(edge,'PASS',{'result':'verified'})
assert len(receipt['evidence_root']) == 64

# Cross-sector/tool routing capability.
fed = BrainKSectorFederation()
fed.register({'sector_id':'AI_CLOUD_INFRA','braink':{'runtime_address':'runtime://ai-cloud'},'capabilities':['runtime.process']})
routed = fed.route('AI_CLOUD_INFRA','runtime.process',{'job':'42'})
assert routed['status'] == 'ROUTED' and routed['runtime_address'] == 'runtime://ai-cloud'

# Audit capability.
audit = AuditLog()
ev = audit.append('tenant-A','agent://worker','EXECUTE','runtime://job/42','ALLOW','COMMITTED','corr-r18')
assert len(ev.event_root) == 64 and len(audit.by_correlation('corr-r18')) == 1

# Observer readback/conflict/signal classification capabilities.
policy = ObserverPolicyEngine()
readback = policy.as_dict({'kind':'PUBLIC_READBACK','subject':'casepath://projection','payload':{'status':200}})
assert readback['action'] == 'CONTINUE'
conflict = policy.as_dict({'kind':'CONTRADICTION','subject':'casepath://projection','payload':{}})
assert conflict['action'] == 'QUARANTINE_AND_REPAIR' and conflict['severity'] == 'CRITICAL'
signal = policy.as_dict({'kind':'CUSTOM_SIGNAL','subject':'runtime://x','payload':{'value':1}})
assert signal['action'] == 'RECONCILE'

print('R18_SHARED_CAPABILITIES_PASS')
