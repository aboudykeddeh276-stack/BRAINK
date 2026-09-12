import asyncio
import json

from braink_runtime.stratum_carrier import StratumEndpoint, probe_stratum


async def _fake_pool(reader, writer):
    subscribe=json.loads((await reader.readline()).decode())
    assert subscribe["method"]=="mining.subscribe"
    writer.write((json.dumps({
        "id":subscribe["id"],
        "result":[[["mining.notify","sub-1"]],"4e01",4],
        "error":None,
    })+"\n").encode())
    await writer.drain()

    authorize=json.loads((await reader.readline()).decode())
    assert authorize["method"]=="mining.authorize"
    writer.write((json.dumps({"id":authorize["id"],"result":True,"error":None})+"\n").encode())
    writer.write((json.dumps({"id":None,"method":"mining.set_difficulty","params":[16384]})+"\n").encode())
    writer.write((json.dumps({"id":None,"method":"mining.notify","params":["JOB_TEST"]})+"\n").encode())
    await writer.drain()
    await asyncio.sleep(0.05)
    writer.close(); await writer.wait_closed()


def test_read_only_stratum_probe():
    async def run():
        server=await asyncio.start_server(_fake_pool,"127.0.0.1",0)
        port=server.sockets[0].getsockname()[1]
        endpoint=StratumEndpoint("TEST","127.0.0.1",port,False,"TEST")
        try:
            receipt=await probe_stratum(endpoint,worker_name="user.worker01",observe_s=0.2,timeout_s=1.0)
        finally:
            server.close(); await server.wait_closed()
        assert receipt["status"]=="SESSION_ESTABLISHED"
        assert receipt["authorized"] is True
        assert receipt["extranonce1"]=="4e01"
        assert receipt["extranonce2_size"]==4
        assert receipt["difficulty"]==16384.0
        assert receipt["current_job_id"]=="JOB_TEST"
        assert receipt["share_submission"]=="NOT_PERFORMED"
        assert receipt["accepted_shares"]=="NOT_DERIVED_FROM_PROBE"
        assert receipt["bitcoin_block_discovery"] is False
    asyncio.run(run())
