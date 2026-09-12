from braink_runtime.telemetry import TelemetryFabric
DATA=[("keddeh.blade01",24510,18,"STALE_SHARE"),("keddeh.blade02",23980,12,"NONE"),("keddeh.blade03",24820,25,"DUPLICATE_SHARE"),("keddeh.blade04",24150,15,"LOW_DIFFICULTY"),("keddeh.blade05",24390,20,"NONE"),("keddeh.blade06",24250,14,"NONE"),("keddeh.blade07",24120,16,"STALE_SHARE")]
def test_known_seven_stream_aggregate():
    f=TelemetryFabric(stale_after_s=999999); now=10_000_000_000
    for worker,a,r,reason in DATA:
        assert f.ingest({"worker_id":worker,"accepted_shares":a,"rejected_shares":r,"last_reject_reason":reason,"difficulty":16384,"source_kind":"LOCAL_TEST","observed_ns":now})["status"]=="INGESTED"
    snap=f.snapshot(now_ns=now)
    assert snap["active_streams"]==7 and snap["total_accepted_shares"]==170220 and snap["total_rejected_shares"]==120
    assert snap["fleet_reject_rate_pct"]==0.0704 and snap["claim_class"]=="POOL_SHARE_TELEMETRY" and snap["bitcoin_block_discovery"] is False
def test_ref_error_is_quarantined_not_promoted():
    f=TelemetryFabric(); got=f.ingest({"worker_id":"keddeh.blade08","accepted_shares":"#REF!","rejected_shares":0})
    assert got["status"]=="QUARANTINED"; snap=f.snapshot(); assert snap["known_streams"]==0 and snap["quarantined_samples"]==1
def test_sheet_projection_is_not_transport_authority():
    f=TelemetryFabric(stale_after_s=999999); now=12_000_000_000
    f.ingest({"worker_id":"keddeh.blade01","accepted_shares":1,"rejected_shares":0,"source_kind":"SHEET_PROJECTION","observed_ns":now})
    snap=f.snapshot(now_ns=now); assert snap["sheet_role"]=="PROJECTION_READBACK_ONLY" and snap["transport_authority"]=="carrier/host runtime" and "socket_flags" not in snap
