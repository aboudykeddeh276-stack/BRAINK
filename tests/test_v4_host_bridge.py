"""Real aiohttp socket + durable file integration checks for the V4 mirror lane.

Import the existing runtime.illlm_ledger and observer2_runtime.kernel from BRAINK.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import pytest
from aiohttp import ClientSession, WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer
from runtime.learning.v4.host_bridge import V4HostBridge, TRANSPORT_SCHEMA

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
