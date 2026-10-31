"""Execute original V4 JS algorithm in Node, then commit its actual candidate records
through the real aiohttp WebSocket and native IL-LLM ledger. No fabricated input.
Architect A. Keddeh / KEDDEH Systems. Local verification, not production host.
"""
from __future__ import annotations
import asyncio, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
from aiohttp import ClientSession, web
from runtime.learning.v4.host_bridge import V4HostBridge, TRANSPORT_SCHEMA
from runtime.illlm_ledger import ILLLMImmutableLedger

ROOT=Path(__file__).resolve().parent
ORIGIN="http://127.0.0.1:43210"
TOKEN="BRAINK-NATIVE-ORIGINAL-V4-REAL-TEST-" + "K"*32

async def run(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    source_file=ROOT/"KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html"
    ledger_path=out/"illlm_v4_original_100.jsonl"
    candidates=out/"v4_native_original_candidates.json"
    store=out/"v4_native_storage.json"
    proc=subprocess.run(["node",str(ROOT/"run_v4_resident.mjs"),str(candidates),str(store)],capture_output=True,text=True,timeout=70)
    if proc.returncode:
        raise RuntimeError(f"REAL_V4_ALGORITHM_FAILED exit={proc.returncode}\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}")
    data=json.loads(candidates.read_text())
    if data["passes"]!=100 or data["mirror_candidates"]!=101:
        raise RuntimeError("SOURCE_ALGORITHM_WRONG_COUNTS")
    if ledger_path.exists():
        raise RuntimeError("LEDGER_PATH_MUST_START_EMPTY")
    original_src_hash=hashlib.sha256(source_file.read_bytes()).hexdigest()
    if original_src_hash!=data['source_sha256']:
        raise RuntimeError("ORIGINAL_V4_ALGORITHM_PROVENANCE_MISMATCH")
    bridge=V4HostBridge(token=TOKEN,ledger_path=ledger_path,source_path=source_file,allowed_origins={ORIGIN})
    runner=web.AppRunner(bridge.app,access_log=None)
    await runner.setup()
    site=web.TCPSite(runner,"127.0.0.1",0)
    await site.start()
    port=site._server.sockets[0].getsockname()[1]
    try:
        async with ClientSession() as client:
            async with client.ws_connect(f"http://127.0.0.1:{port}/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                await ws.send_json({"action":"AUTH","instance_id":data['instance_id'],"token":TOKEN})
                auth=await ws.receive_json(timeout=10)
                if auth.get('action')!='AUTH_ACCEPTED':raise RuntimeError(f"AUTH_DENIED {auth}")
                for i, snapshot in enumerate(data['records'],1):
                    payload={"action":"STATE_TELEMETRY","schema":TRANSPORT_SCHEMA,
                        "source_sha256":data['source_sha256'],"sequence":i,**snapshot}
                    await ws.send_json(payload)
                    ack=await ws.receive_json(timeout=15)
                    if ack.get('action')!='MIRROR_COMMITTED':
                        raise RuntimeError(f"SOURCE_ALGORITHM_WS_ADMISSION_FAILED_ITER_{i}: {ack}")
                    if ack['sequence']!=i or ack['promotion_state']!='NOT_PROMOTED':
                        raise RuntimeError(f"WRONG_ADMISSION_OR_PROMOTION: {ack}")
                    if i==1: first_ack=ack
                    last_ack=ack
            async with client.get(f"http://127.0.0.1:{port}/api/readback",
                                params={"correlation_id":last_ack['correlation_id']},
                                headers={"Authorization":"Bearer "+TOKEN}) as response:
                if response.status!=200:raise RuntimeError(f"LIVE_READBACK_HTTP_{response.status}")
                body=await response.json()
                if body['verification']['events']!=101:raise RuntimeError('NOT_101_DISK_EVENTS')
                if body['events'][0]['event_root']!=last_ack['event_root']:
                    raise RuntimeError('LIVE_READBACK_HEAD_MISMATCH')
        first_pid=os.getpid()
    finally:
        await runner.cleanup()
    reopened=V4HostBridge(token=TOKEN,ledger_path=ledger_path,source_path=source_file,allowed_origins={ORIGIN})
    after=reopened.ledger.verify()
    if after['status']!='PASS' or after['events']!=101 or after['head']!=last_ack['event_root']:
        raise RuntimeError(f"RESTART_READBACK_FAILED {after}")
    events=ILLLMImmutableLedger(ledger_path).read_by_correlation(last_ack['correlation_id'])
    if len(events)!=1 or events[0]['event_root']!=last_ack['event_root']:
        raise RuntimeError('RESTART_CORRELATION_READBACK_FAILED')
    # Verify original algorithm rather than 101 source-shaped test fixtures.
    rows=[json.loads(x) for x in ledger_path.read_text().splitlines()]
    actual=[r['payload']['state']['polygon']['iteration'] for r in rows]
    if actual != list(range(1,101))+[100]:
        raise RuntimeError(f"NON_SOURCE_POLYGON_PROGRESS_OR_ORDER: {actual[:5]} {actual[-5:]}")
    v4_receipts=[r['payload']['state']['v4_receipt']['type'] for r in rows]
    if v4_receipts!=['POLYGON_100_ITERATION']*100+['POLYGON_100_COMMIT']:
        raise RuntimeError('V4_RECEIPT_LINEAGE_MISMATCH')
    proof={"schema":"KS-BRAINK-IL-LLM/actual-v4-node-algorithm-to-native-ledger/1",
       "architect":"A. Keddeh", "original_source_sha256":original_src_hash,
       "v5_wrapper_source_sha256":data['control_source_sha256'],
       "execution_plane":"NODE_VM_EXECUTED_ORIGINAL_V4_SOURCE_EXACT_POLYGON_ALGORITHM_PLUS_V5_WRAPPER",
       "host_plane":"REAL_AIOHTTP_TCP_WEBSOCKET_NATIVE_ILLM_LEDGER_LOCAL_CONTAINER",
       "original_v4_algorithm_passes":100,"source_successors":100,
       "source_generated_mirror_candidates":len(data['records']),"native_ledger_events":len(rows),
       "first_event_root":first_ack['event_root'],"final_event_root":last_ack['event_root'],
       "ledger_file_sha256":hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
       "after_service_restart_readback":after,"source_native_result":proc.stdout.strip(),
       "event_sequence_verified":True,"v4_receipt_type_lineage_verified":True,
       "learning_promotion":"NOT_PROMOTED","has_real_browser":False,
       "external_keddeh_node_admitted":False,"independent_quorum":False,
       "verification":"EXECUTED_LOCAL_SOURCE_ALGORITHM_AND_DISK_TRANSPORT_NOT_HOSTED_PRODUCTION"}
    (out/"v4_100_to_illlm_verification.json").write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:proof[k] for k in ('original_v4_algorithm_passes','native_ledger_events','final_event_root','ledger_file_sha256','verification')},sort_keys=True))

if __name__=='__main__':
    asyncio.run(run(Path(sys.argv[1] if len(sys.argv)>1 else tempfile.mkdtemp(prefix='braink-original-v4-'))))
