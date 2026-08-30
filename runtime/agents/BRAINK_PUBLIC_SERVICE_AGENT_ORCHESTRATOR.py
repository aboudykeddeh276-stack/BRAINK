#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, hashlib, time, sys
HERE=pathlib.Path(__file__).resolve().parent
FABRIC=json.loads((HERE/'BRAINK_PUBLIC_SERVICE_AGENT_FABRIC.json').read_text())
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'))
def sha(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def resolve_process(process_id:str):
    for p in FABRIC['processes']:
        if p['id']==process_id: return p
    raise KeyError(process_id)
def dispatch(process_id:str,input_state:dict):
    p=resolve_process(process_id)
    receipt={'schema':'kex.braink.agent-dispatch-receipt.v1','fabric':FABRIC['identity'],'process':process_id,'owner_team':p['owner_team'],'lead':p['lead'],'input_hash':sha(input_state),'actions':p['actions'],'handoff':p.get('handoff',[]),'proof_gate':p['PROOF_GATE'],'state':'STATE_DISPATCHED','provenance':'SOURCE_VERIFIED_PROCESS_CONTRACT','at':time.time()}
    receipt['receipt_sha256']=sha(receipt)
    return receipt
def main():
    if len(sys.argv)<2:
        print(json.dumps({'WHOLE_NAME':FABRIC['WHOLE_NAME'],'identity':FABRIC['identity'],'graph_validation':FABRIC['graph_validation'],'processes':[p['id'] for p in FABRIC['processes']]},indent=2)); return
    payload=json.loads(sys.stdin.read() or '{}')
    print(json.dumps(dispatch(sys.argv[1],payload),indent=2))
if __name__=='__main__': main()
