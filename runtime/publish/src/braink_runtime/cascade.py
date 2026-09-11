from __future__ import annotations
import hashlib, json
from copy import deepcopy
from .models import ActionExecutionRequest, MutationReceipt
from .storage import Store

STAGES=['MOUNT','VERIFY','HYDRATE','RESOLVE','MUTATE','WRITE_BACK','PROOF']
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(v): return hashlib.sha256(canonical(v)).hexdigest()

def merge(base,patch):
    out=deepcopy(base)
    for k,v in patch.items():
        if isinstance(v,dict) and isinstance(out.get(k),dict): out[k]=merge(out[k],v)
        else: out[k]=v
    return out

class Cascade:
    def __init__(self,store:Store): self.store=store
    def execute(self,req:ActionExecutionRequest)->MutationReceipt:
        prior=self.store.prior_receipt(req.request_id)
        if prior: return MutationReceipt.model_validate(prior)
        current,version=self.store.get_state(req.target)
        if req.expected_version is not None and req.expected_version != version:
            raise ValueError(f'version_conflict expected={req.expected_version} actual={version}')
        before=sha(current)
        if req.action=='merge': new=merge(current,req.payload)
        elif req.action=='replace': new=req.payload
        elif req.action=='append':
            seq=list(current) if isinstance(current,list) else []
            seq.append(req.payload); new=seq
        else: raise ValueError('unsupported_action')
        new_version=version+1; after=sha(new)
        mutation_hash=sha({'request_id':req.request_id,'action':req.action,'target':req.target,'before':before,'after':after,'version':new_version})
        self.store.put_state(req.target,new,new_version)
        event={'request_id':req.request_id,'target':req.target,'version':new_version,'mutation_hash':mutation_hash,'before_hash':before,'after_hash':after,'stages':STAGES}
        idx=self.store.append_ledger(event)
        receipt=MutationReceipt(request_id=req.request_id,action=req.action,target=req.target,stages=STAGES,before_hash=before,after_hash=after,mutation_hash=mutation_hash,version=new_version,ledger_index=idx)
        self.store.save_receipt(req.request_id,receipt.model_dump())
        return receipt
