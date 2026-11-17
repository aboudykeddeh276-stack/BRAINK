"""Real OS process + TCP + disk/restart lifecycle validation for the V4 bridge.

Source-shaped transport fixtures are *not* execution of V4's polygon algorithm.
No mock sockets, in-memory ledger, or TestServer are used here.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from aiohttp import ClientSession
from runtime.illlm_ledger import ILLLMImmutableLedger

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'runtime/learning/v4/KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html'
TOKEN = 'source_lifecycle_' + 'e'*48


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


async def launch(port: int, path: Path, log_path: Path):
    env = os.environ.copy()
    env.update({'PYTHONPATH': str(ROOT), 'BRAINK_V4_BRIDGE_BIND': '127.0.0.1',
                'BRAINK_V4_BRIDGE_PORT': str(port), 'BRAINK_V4_BRIDGE_TOKEN': TOKEN,
                'BRAINK_V4_LEDGER_PATH': str(path)})
    handle = log_path.open('ab')
    process = subprocess.Popen([sys.executable, '-m', 'runtime.learning.v4.host_bridge'],
                               cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                               stdout=handle, stderr=subprocess.STDOUT)
    handle.close()
    base = f'http://127.0.0.1:{port}'
    async with ClientSession() as client:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(f'SERVER_EXITED:{process.returncode}:{log_path.read_text()[-1000:]}')
            try:
                async with client.get(base+'/api/health', timeout=1) as reply:
                    if reply.status == 200:
                        state = await reply.json()
                        if state['status'] == 'BRIDGE_READY':
                            return process, state
            except (OSError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(0.08)
    process.terminate()
    raise AssertionError('STARTUP_READINESS_MISSING')


def terminate(process: subprocess.Popen):
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=10)


def source_bound_fixture(source_sha: str, sequence: int):
    return {'action':'STATE_TELEMETRY','schema':'KS-BRAINK-IL-LLM/observer-v4-mirror-transport/1',
            'source_sha256':source_sha,'sequence':sequence,
            'observer':{'observer':'BRAINK:BRAINK_CHAT_AI_AGENTIC_PLATFORM_V4_CONTROL_WRAPPER',
                        'wholeIdentity':'1_BRAINK','stateFormula':'O_AS_OBS=1_O⊗S_O(E)',
                        'queryRoot':'ABEF0404','epoch':sequence,
                        'observation':{'query':'source-bound transport verification only'}},
            'polygon':{'iteration':sequence,'lastApex':'test-boundary',
                       'lastSuccessor':f'RECEIPT_TEST_{sequence}',
                       'history_tail':[{'iteration':sequence, 'source':'TEST_FIXTURE_NOT_V4_EXECUTION'}]},
            'v4_receipt':{'id':f'host-transporter-test-{sequence}',
                          'type':'POLYGON_100_ITERATION','status':'PASS'}}


@pytest.mark.asyncio
async def test_actual_os_process_websocket_100_events_restart_and_independent_readback(tmp_path):
    port=free_port()
    path=tmp_path/'native-illlm.jsonl'
    log_path=tmp_path/'server.log'
    base=f'http://127.0.0.1:{port}'
    origin=base
    first=None
    second=None
    try:
        first, original_state=await launch(port,path,log_path)
        assert original_state['external_host_executors'] is None
        assert original_state['ledger']['events'] == 0
        source_sha=original_state['source_sha256']
        assert len(source_sha)==64
        first_pid=first.pid
        first_ack=None
        last_ack=None
        async with ClientSession() as client:
            async with client.ws_connect(base+'/api/ws/state',headers={'Origin':origin}) as ws:
                await ws.send_json({'action':'AUTH','token':TOKEN,'instance_id':'host-lifecycle-source-0001'})
                auth=await ws.receive_json(timeout=5)
                assert auth['action']=='AUTH_ACCEPTED'
                assert auth['scope']=='BROWSER_LEARNING_MIRROR_ONLY'
                for sequence in range(1,101):
                    await ws.send_json(source_bound_fixture(source_sha,sequence))
                    reply=await ws.receive_json(timeout=8)
                    assert reply['action']=='MIRROR_COMMITTED',reply
                    assert reply['sequence']==sequence
                    assert reply['promotion_state']=='NOT_PROMOTED'
                    if sequence==1:first_ack=reply
                    last_ack=reply
            async with client.get(base+'/api/health') as response:
                health=await response.json()
                assert health['ledger']['status']=='PASS'
                assert health['ledger']['events']==100
                assert health['external_host_executors'] is None
            async with client.get(base+'/api/readback?correlation_id='+last_ack['correlation_id'],
                    headers={'Authorization':'Bearer '+TOKEN}) as response:
                assert response.status==200
                readback=await response.json()
                assert readback['events'][0]['event_root']==last_ack['event_root']
                assert readback['verification']['head']==last_ack['ledger_head']
        terminate(first)
        second,restarted=await launch(port,path,log_path)
        assert second.pid!=first_pid
        assert restarted['ledger']['events']==100
        assert restarted['ledger']['head']==last_ack['event_root']
        assert ILLLMImmutableLedger(path).verify()==restarted['ledger']
        assert len(path.read_bytes().splitlines())==100
        assert ILLLMImmutableLedger(path).read_by_correlation(first_ack['correlation_id'])[0]['event_root']==first_ack['event_root']
        (tmp_path / 'host_lifecycle_receipt.json').write_text(json.dumps({
            'schema': 'KS-BRAINK-IL-LLM/local-host-process-100-transport-receipts/1',
            'initial_pid': first_pid, 'restart_pid': second.pid, 'events': 100,
            'ledger_head_sha256': last_ack['event_root'], 'source_sha256': source_sha,
            'verified_restart': True, 'local_os_process': True,
            'host_scope': 'TEST_CONTAINER_NOT_KEDDEH_OWNER_EXTERNAL_HOST',
            'source_algorithms_executed': False,
            'input_classification': 'SOURCE_SHAPED_TEST_FIXTURES_NOT_100_V4_POLYGON_PASSES',
            'external_executor_admitted': False,
        }, indent=2)+'\n')
    finally:
        for p in (first, second):
            if p is not None:terminate(p)
