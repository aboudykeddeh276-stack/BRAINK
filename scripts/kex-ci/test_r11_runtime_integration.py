from __future__ import annotations
import tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from enterprise.orc_runtime import ORCRuntime,Obligation
from enterprise.vfs_adapter import VFSAdapter
from enterprise.aperture_registry import ApertureRegistry
from enterprise.native_fence_authority import NativeFenceAuthority,FenceCertificate
from enterprise.agent_runtime import AgentRuntime
from enterprise.carrier_runtime import CarrierRuntime
from enterprise.casepath_runtime_adapter import CasePathRuntimeAdapter,CASEPATH_AGENT
from enterprise.observer_reconciler import reconcile

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    vfs=VFSAdapter(td/'vfs'); apertures=ApertureRegistry(); fences=NativeFenceAuthority(); agents=AgentRuntime()
    agents.bind(CASEPATH_AGENT,'braink-agent-casepath','casepath.trust-centre.patch',lambda p:{'accepted_patch':p['patch_id']})
    cp=CasePathRuntimeAdapter(vfs,apertures,fences,agents); cp.bind()
    orc=ORCRuntime(); orc.register('KEX://DOMAIN/CASEPATH.COM.AU',lambda o:cp.execute_patch(o.payload['patch_id'],o.payload))
    obligation=Obligation('CASEPATH-R11','KEX://DOMAIN/CASEPATH.COM.AU/YOUR-DATA/TRUST-CENTRE','casepath.trust-centre.patch','PATCH',{'patch_id':'CP-TC-20260727-C01'},unlock_value=1,information_gain=1)
    dispatch=orc.dispatch(obligation)
    assert dispatch.status=='COMMITTED',dispatch
    stored=vfs.read('vfs://casepath/page/your-data'); assert stored['status']=='READ'
    rec=reconcile('PROCESS_EXECUTED',[]); assert rec['observer_state']=='OBSERVER_UNREAD'; assert rec['reconciliation_state']=='RECONCILIATION_ACCEPTED'
    carrier=CarrierRuntime(td/'carrier.json')
    f1=carrier.rewrite({'dispatch_root':dispatch.receipt_root,'observer':'UNREAD'})
    f2=carrier.rewrite({'dispatch_root':dispatch.receipt_root,'observer':'OBSERVED'})
    assert f2['tick']==2 and f2['predecessor_root']==f1['carrier_root']
    current=fences.current('vfs://casepath/page/your-data')
    stale=FenceCertificate(current.resource,current.generation-1,'old','n')
    assert not fences.verify(stale)
print('R11_END_TO_END_PASS')
