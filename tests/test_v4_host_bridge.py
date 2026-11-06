"""Real aiohttp socket + durable file integration checks for the V4 mirror lane.

Import the existing runtime.illlm_ledger and observer2_runtime.kernel from BRAINK.
"""
from __future__ import annotations
import asyncio
import json
import multiprocessing
import time
from pathlib import Path
import pytest
from aiohttp import ClientSession, WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer
from runtime.learning.v4.host_bridge import V4HostBridge, BrowserSession, TRANSPORT_SCHEMA
from runtime.illlm_ledger import ILLLMImmutableLedger

TOKEN = "kstest_" + "a" * 52
SOURCE = Path(__file__).resolve().parents[1] / "runtime/learning/v4/KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html"
ORIGIN = "http://127.0.0.1:8080"


def sample(bridge: V4HostBridge, seq: int = 1, receipt: str = "V4-OP-1") -> dict:
    return {"action":"STATE_TELEMETRY","schema":TRANSPORT_SCHEMA,
            "source_sha256":bridge.source_sha256,"sequence":seq,
            "observer":{"observer":"BRAINK:BRAINK_CHAT_AI_AGENTIC_PLATFORM_V4_CONTROL_WRAPPER",
                        "wholeIdentity":"1_BRAINK","stateFormula":"O_AS_OBS=1_O⊗S_O(E)",
                        "queryRoot":"ABEF0404","epoch":1,"observation":{"query":"evidence"}},
            "polygon":{"iteration":1,"lastApex":"concept","lastSuccessor":"successor-1",
                       "history_tail":[{"iteration":1,"evidenceIds":["source-1"]}]},
            "v4_receipt":{"id":receipt,"type":"POLYGON_100_ITERATION","status":"PASS"}}


@pytest.mark.asyncio
async def test_tcp_ws_mirror_receipt_readback_and_restart(tmp_path):
    path=tmp_path/"illlm-v4.jsonl"
    bridge=V4HostBridge(token=TOKEN,ledger_path=path,source_path=SOURCE,allowed_origins={ORIGIN})
    async with TestServer(bridge.app) as srv:
        async with ClientSession() as c:
            url=f"http://127.0.0.1:{srv.port}"
            async with c.get(url+"/api/health") as resp:
                status=await resp.json();assert status["status"]=="BRIDGE_READY"
                assert status["external_host_executors"] is None
            async with c.ws_connect(url+"/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                await ws.send_json({"action":"AUTH","instance_id":"v4-session-0001","token":TOKEN})
                assert (await ws.receive_json())["action"]=="AUTH_ACCEPTED"
                await ws.send_json(sample(bridge))
                ack=await ws.receive_json();assert ack["action"]=="MIRROR_COMMITTED",ack
                assert ack["promotion_state"]=="NOT_PROMOTED"
                # true server-side disk persistence and independently authenticated readback
                async with c.get(url+"/api/readback?correlation_id="+ack["correlation_id"],headers={"Authorization":"Bearer "+TOKEN}) as res:
                    data=await res.json();assert res.status==200
                assert data["verification"]["events"]==1
                assert data["events"][0]["event_root"]==ack["event_root"]
                assert data["events"][0]["payload"]["state"]["polygon"]["lastSuccessor"]=="successor-1"
                await ws.send_json({"action":"HEARTBEAT"})
                assert (await ws.receive_json())["action"]=="HEARTBEAT_ACK"
    restarted=V4HostBridge(token=TOKEN,ledger_path=path,source_path=SOURCE,allowed_origins={ORIGIN})
    assert restarted.ledger.verify()==data["verification"]
    assert restarted.ledger.read_by_correlation(ack["correlation_id"])[0]["event_root"]==ack["event_root"]


@pytest.mark.asyncio
async def test_unauthorised_and_wrong_origin_rejected(tmp_path):
    bridge=V4HostBridge(token=TOKEN,ledger_path=tmp_path/"l.jsonl",source_path=SOURCE,allowed_origins={ORIGIN})
    async with TestServer(bridge.app) as srv:
        async with ClientSession() as c:
            url=f"http://127.0.0.1:{srv.port}"
            with pytest.raises(WSServerHandshakeError) as err:
                await c.ws_connect(url+"/api/ws/state",headers={"Origin":"https://untrusted.example"})
            assert err.value.status==403
            async with c.ws_connect(url+"/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                await ws.send_json({"action":"AUTH","instance_id":"v4-evil-01","token":"wrong"})
                assert (await ws.receive_json())["action"]=="REJECTED"
            async with c.get(url+"/api/health") as resp:
                assert (await resp.json())["browser_learning_sessions"]==0
    assert bridge.ledger.verify()["events"]==0


@pytest.mark.asyncio
async def test_invalid_source_and_nonmonotonic_sequence(tmp_path):
    bridge=V4HostBridge(token=TOKEN,ledger_path=tmp_path/"l.jsonl",source_path=SOURCE,allowed_origins={ORIGIN})
    async with TestServer(bridge.app) as srv:
        async with ClientSession() as c:
            url=f"http://127.0.0.1:{srv.port}"
            async with c.ws_connect(url+"/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                await ws.send_json({"action":"AUTH","instance_id":"v4-session-0001","token":TOKEN})
                assert (await ws.receive_json())["action"]=="AUTH_ACCEPTED"
                bad=sample(bridge);bad["source_sha256"]="0"*64
                await ws.send_json(bad)
                assert (await ws.receive_json())["reason"]=="SOURCE_PROVENANCE_MISMATCH"
                await ws.send_json(sample(bridge))
                assert (await ws.receive_json())["action"]=="MIRROR_COMMITTED"
                await ws.send_json(sample(bridge))
                assert (await ws.receive_json())["reason"]=="NON_MONOTONIC_SEQUENCE"
    assert bridge.ledger.verify()["events"]==1


@pytest.mark.asyncio
async def test_ledger_tamper_detected_and_blocks_future_commit(tmp_path):
    path=tmp_path/"l.jsonl"
    bridge=V4HostBridge(token=TOKEN,ledger_path=path,source_path=SOURCE,allowed_origins={ORIGIN})
    async with TestServer(bridge.app) as srv:
        async with ClientSession() as c:
            url=f"http://127.0.0.1:{srv.port}"
            async with c.ws_connect(url+"/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                await ws.send_json({"action":"AUTH","instance_id":"v4-session-0001","token":TOKEN})
                await ws.receive_json()
                await ws.send_json(sample(bridge))
                assert (await ws.receive_json())["action"]=="MIRROR_COMMITTED"
                contents=path.read_text();path.write_text(contents.replace("NOT_PROMOTED","YES_PROMOTED"))
                assert bridge.ledger.verify()["status"]=="FAILED"
                await ws.send_json(sample(bridge,seq=2,receipt="V4-OP-2"))
                assert (await ws.receive_json())["reason"]=="CORRUPT_LEDGER"
    assert bridge.ledger.verify()["status"]=="FAILED"


@pytest.mark.asyncio
async def test_reconnect_duplicate_receipt_is_idempotent(tmp_path):
    path=tmp_path/"l.jsonl"
    bridge=V4HostBridge(token=TOKEN,ledger_path=path,source_path=SOURCE,allowed_origins={ORIGIN})
    async with TestServer(bridge.app) as srv:
        async with ClientSession() as c:
            url=f"http://127.0.0.1:{srv.port}"
            async def one(seq):
                async with c.ws_connect(url+"/api/ws/state",headers={"Origin":ORIGIN}) as ws:
                    await ws.send_json({"action":"AUTH","instance_id":"v4-session-0001","token":TOKEN})
                    await ws.receive_json()
                    await ws.send_json(sample(bridge,seq))
                    return await ws.receive_json()
            first=await one(10);second=await one(11)
            assert first["event_root"]==second["event_root"]
    assert bridge.ledger.verify()["events"]==1


def test_derived_carrier_matches_original_and_contains_real_v4_growth():
    original=SOURCE.read_text()
    derivative=SOURCE.with_name("KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4_HOST_LINK.html").read_text()
    assert "async function run100GrowthPasses()" in original
    assert "S.polygonState.history.push(rec)" in derivative
    assert "function hostMirrorOnReceipt(r)" in derivative
    assert "EXTERNAL EXECUTOR ATTACHED" not in derivative
    assert "OBSERVER_SOURCE_FORMULA_MISMATCH" not in derivative  # Python-only gate


def _mirror_duplicate_process_worker(path, barrier, output):
    """Force two independent processes to read the same empty predecessor."""
    try:
        bridge = V4HostBridge(token=TOKEN, ledger_path=path, source_path=SOURCE, allowed_origins={ORIGIN})
        session = BrowserSession("test-session", "same-browser-instance", time.monotonic())
        original_read = bridge.ledger.read_by_correlation
        def read_before_both_append(correlation):
            existing = original_read(correlation)
            barrier.wait(timeout=15)
            return existing
        bridge.ledger.read_by_correlation = read_before_both_append
        output.put(("ok", bridge._record(sample(bridge, receipt="V4-REPLAY-SHARED"), session)))
    except BaseException as exc:
        output.put(("error", repr(exc)))


def test_duplicate_cross_process_mirror_receipt_is_exactly_once(tmp_path):
    path = tmp_path / "illlm-v4.jsonl"
    ctx = multiprocessing.get_context("spawn")
    barrier, output = ctx.Barrier(2), ctx.Queue()
    processes = [ctx.Process(target=_mirror_duplicate_process_worker,
                             args=(str(path), barrier, output)) for _ in range(2)]
    for process in processes: process.start()
    for process in processes: process.join(25)
    for process in processes:
        if process.is_alive(): process.terminate(); process.join(5)
    assert [process.exitcode for process in processes] == [0, 0]
    results = [output.get(timeout=3) for _ in processes]
    assert all(status == "ok" for status, _ in results), results
    verification = ILLLMImmutableLedger(path).verify()
    assert verification["status"] == "PASS", verification
    assert verification["events"] == 1, verification
    assert results[0][1]["event_root"] == results[1][1]["event_root"]


def test_idempotency_conflict_fails_closed_without_extra_event(tmp_path):
    ledger = ILLLMImmutableLedger(tmp_path / "illlm-v4.jsonl")
    args = dict(source_uri="braink://learning/v4/browser/same-browser-instance",
                source_level="OBSERVER_MIRROR_ONLY", semantic_type="POLYGON_MIRROR_CANDIDATE",
                correlation_id="same-source-receipt",
                payload={"candidate_hash": "a" * 64, "sequence": 1},
                lexical_state={"polygon": "stable"},
                illlm_state={"candidate": "a" * 64},
                idempotency_payload_field="candidate_hash")
    first = ledger.append(**args)
    second = ledger.append(**{**args, "payload": {"candidate_hash": "a" * 64, "sequence": 2}})
    assert second.event_root == first.event_root
    with pytest.raises(ValueError, match="CORRELATION_REPLAY_CONFLICT"):
        ledger.append(**{**args, "payload": {"candidate_hash": "b" * 64, "sequence": 3}})
    assert ledger.verify()["events"] == 1
    assert ledger.head() == first.event_root
