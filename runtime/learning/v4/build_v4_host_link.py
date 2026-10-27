"""Add transport projection to the unchanged A. Keddeh BRAINK V4 HTML carrier.

The V4's existing polygon learning and observer formula are not replaced.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html"
DEST = ROOT / "KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4_HOST_LINK.html"

PANEL = '''
<section class="panel" id="hostBridgePanel"><h2>BRAINK resident learning mirror</h2>
<div class="muted small" id="host-state" role="status">OFFLINE · Browser mirror, not an external host executor</div>
<label for="hostBrokerUrl">Resident broker address</label><input id="hostBrokerUrl" type="url" value="http://127.0.0.1:8080" autocomplete="off" spellcheck="false">
<label for="hostAuthToken">Session access token (not saved)</label><input id="hostAuthToken" type="password" autocomplete="off" spellcheck="false" placeholder="Read from BRAINK_V4_BRIDGE_TOKEN">
<button type="button" id="connectHostBtn">Connect authenticated mirror</button>
<div class="muted small" id="hostBridgeReceipt">Receipts stay local until authenticated host readback.</div>
</section>
'''

BRIDGE_JS = r'''
// Additive host-mirror binding: preserves original V4 learning and wrapper admissions.
const HOST_MIRROR_SCHEMA='KS-BRAINK-IL-LLM/observer-v4-mirror-transport/1';
const HOST_MIRROR_SOURCE_SHA256='__SOURCE_SHA256__';
let hostMirrorSocket=null,hostMirrorAuthorised=false,hostMirrorInFlight=null,latestV4Observer=null,hostMirrorHeartbeat=null;
function hostMirrorEnsureState(){
 if(!S.hostLink || typeof S.hostLink!=='object')S.hostLink={instanceId:'',sequence:0,pending:[],lastAck:null};
 if(!S.hostLink.instanceId)S.hostLink.instanceId='v4-'+crypto.randomUUID();
 if(!Array.isArray(S.hostLink.pending))S.hostLink.pending=[];
 if(!Number.isSafeInteger(S.hostLink.sequence))S.hostLink.sequence=0;
}
function hostMirrorStatus(s){const el=$('#host-state');if(el)el.textContent=s}
function hostMirrorAck(s){const el=$('#hostBridgeReceipt');if(el)el.textContent=s}
function hostMirrorOnReceipt(r){
 // Only mirror source-observed learning candidates; leave other V4 receipts untouched.
 if(!latestV4Observer||!/POLYGON|LEARNING_DELTA|LEXICON_RECURSIVE_ADAPT/.test(r.type))return;
 hostMirrorEnsureState();
 const p=S.polygonState||{};
 const snapshot={observer:JSON.parse(JSON.stringify(latestV4Observer)),
  polygon:{iteration:p.iteration||0,lastApex:p.lastApex??null,lastSuccessor:p.lastSuccessor??null,
   history_tail:(p.history||[]).slice(-10).map(z=>JSON.parse(JSON.stringify(z)))},
  v4_receipt:JSON.parse(JSON.stringify(r))};
 if(S.hostLink.pending.some(z=>z.v4_receipt.id===r.id))return;
 if(S.hostLink.pending.length>=1000){hostMirrorStatus('BACKLOG_FULL: local source retained; no silent deletion');return;}
 S.hostLink.pending.push(snapshot);save();hostMirrorFlush();
}
function hostMirrorFlush(){
 if(!hostMirrorAuthorised||!hostMirrorSocket||hostMirrorSocket.readyState!==WebSocket.OPEN||hostMirrorInFlight)return;
 hostMirrorEnsureState();const current=S.hostLink.pending[0];if(!current)return;
 if(hostMirrorSocket.bufferedAmount>65536){hostMirrorAck('Backpressure: retaining queued candidates');return;}
 S.hostLink.sequence+=1;
 const seq=S.hostLink.sequence;hostMirrorInFlight={sequence:seq,receiptId:current.v4_receipt.id};save();
 hostMirrorSocket.send(JSON.stringify({action:'STATE_TELEMETRY',schema:HOST_MIRROR_SCHEMA,
  source_sha256:HOST_MIRROR_SOURCE_SHA256,sequence:seq,...current}));
}
function hostMirrorDisconnect(){
 hostMirrorAuthorised=false;hostMirrorInFlight=null;
 if(hostMirrorHeartbeat){clearInterval(hostMirrorHeartbeat);hostMirrorHeartbeat=null}
 if(hostMirrorSocket){hostMirrorSocket.close();hostMirrorSocket=null}
 hostMirrorStatus('OFFLINE · Local V4 learning preserved');
 const b=$('#connectHostBtn');if(b)b.textContent='Connect authenticated mirror';
}
function toggleHostConnection(){
 if(hostMirrorSocket){hostMirrorDisconnect();return}
 hostMirrorEnsureState();const base=$('#hostBrokerUrl').value.trim().replace(/\/$/,'');
 let address;try{address=new URL(base);if(!['http:','https:'].includes(address.protocol)||!address.host)throw Error('Invalid broker URL')}catch(e){hostMirrorStatus('REJECTED: '+e.message);return}
 const secret=$('#hostAuthToken').value;
 if(secret.length<32){hostMirrorStatus('REJECTED: token length below 32');return}
 const target=new URL('/api/ws/state',address);
 target.protocol=address.protocol==='https:'?'wss:':'ws:';
 hostMirrorStatus('CONNECTING · awaiting authenticated admission');
 const ws=new WebSocket(target.href);hostMirrorSocket=ws;
 ws.onopen=()=>{ws.send(JSON.stringify({action:'AUTH',instance_id:S.hostLink.instanceId,token:secret}));$('#hostAuthToken').value=''};
 ws.onmessage=(e)=>{
  let data;try{data=JSON.parse(e.data)}catch{hostMirrorAck('Invalid server response');return}
  if(data.action==='AUTH_ACCEPTED'){
   if(data.source_sha256!==HOST_MIRROR_SOURCE_SHA256){hostMirrorStatus('SOURCE_MISMATCH; disconnecting');hostMirrorDisconnect();return}
   hostMirrorAuthorised=true;hostMirrorStatus('AUTHENTICATED · Browser learning mirror only');
   $('#connectHostBtn').textContent='Disconnect mirror';
   hostMirrorHeartbeat=setInterval(()=>{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({action:'HEARTBEAT'}))},5000);
   hostMirrorFlush();return;
  }
  if(data.action==='MIRROR_COMMITTED'){
   if(!hostMirrorInFlight||data.sequence!==hostMirrorInFlight.sequence){hostMirrorStatus('Receipt sequence mismatch; disconnecting');hostMirrorDisconnect();return}
   const head=S.hostLink.pending[0];
   if(!head||head.v4_receipt.id!==hostMirrorInFlight.receiptId){hostMirrorStatus('Local queue mismatch; disconnecting');hostMirrorDisconnect();return}
   S.hostLink.pending.shift();S.hostLink.lastAck={event_id:data.event_id,event_root:data.event_root,
    correlation_id:data.correlation_id,sequence:data.sequence,source_receipt_id:head.v4_receipt.id};
   hostMirrorInFlight=null;save();hostMirrorAck('Ledger readback: '+data.event_root+' · queued: '+S.hostLink.pending.length);
   hostMirrorFlush();return;
  }
  if(data.action==='REJECTED'){
   hostMirrorAck('NOT ADMITTED: '+String(data.reason||'unknown'));
   hostMirrorInFlight=null;hostMirrorDisconnect();
  }
 };
 ws.onerror=()=>hostMirrorStatus('TRANSPORT_ERROR · No host execution proof');
 ws.onclose=()=>{if(hostMirrorSocket===ws)hostMirrorDisconnect()};
}
function syncStateToHostBroker(){hostMirrorFlush()}
$('#connectHostBtn').onclick=toggleHostConnection;
if(location.protocol==='http:'||location.protocol==='https:')$('#hostBrokerUrl').value=location.origin;
hostMirrorEnsureState();save();
hostMirrorAck('Queued mirror records: '+S.hostLink.pending.length+' · no global promotion');
'''

def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert source.count('})();\n</script>') == 1
    assert source.count('</aside>') == 2
    assert source.count('function receipt(type,status,detail={})') == 1
    assert source.count('function observerState(q,intentObj,lex,ev,cycle=0)') == 1
    # Observer capture references the V4 formula directly; no replacement formula.
    old = "return {observer:`BRAINK:${VERSION}`,wholeIdentity:`1_BRAINK`,epoch:"
    new = "const frame={observer:`BRAINK:${VERSION}`,wholeIdentity:`1_BRAINK`,epoch:"
    assert source.count(old) == 1
    source = source.replace(old, new)
    old = "stateFormula:'O_AS_OBS=1_O⊗S_O(E)',at:new Date().toISOString()};\n}"
    new = "stateFormula:'O_AS_OBS=1_O⊗S_O(E)',at:new Date().toISOString()};latestV4Observer=frame;return frame;\n}"
    assert source.count(old) == 1
    source = source.replace(old, new)
    old = "S.receipts.push(r);save();return r}"
    new = "S.receipts.push(r);save();hostMirrorOnReceipt(r);return r}"
    assert source.count(old) == 1
    source = source.replace(old,new)
    before, after = source.rsplit('</aside>',1)
    source = before + PANEL + '</aside>' + after
    source = source.replace('})();\n</script>',BRIDGE_JS.replace('__SOURCE_SHA256__',sha)+'\n})();\n</script>')
    DEST.write_text(source,encoding="utf-8")
    print({"source_sha256":sha,"source_bytes":SOURCE.stat().st_size,"derived_sha256":hashlib.sha256(DEST.read_bytes()).hexdigest(),"derived_bytes":DEST.stat().st_size})

if __name__ == '__main__':
    main()
