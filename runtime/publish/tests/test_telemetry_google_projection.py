from braink_runtime.telemetry_google_projection import _stream_rows, reconcile_records


def test_pool_telemetry_never_promotes_block_discovery():
    snap={
        "claim_class":"POOL_SHARE_TELEMETRY",
        "bitcoin_block_discovery":False,
        "streams":[{
            "worker_id":"keddeh.blade01",
            "accepted_shares":10,
            "rejected_shares":1,
            "reject_rate_pct":9.0909,
            "status":"ONLINE",
        }],
    }
    rows=_stream_rows(snap)
    assert rows[0][1]=="keddeh.blade01"
    assert rows[0][8]==10


def test_block_discovery_flag_is_rejected_on_pool_projection():
    snap={"claim_class":"POOL_SHARE_TELEMETRY","bitcoin_block_discovery":True,"streams":[]}
    try:
        _stream_rows(snap)
        raise AssertionError("expected fail-closed rejection")
    except ValueError as exc:
        assert "CANNOT_PROMOTE_BLOCK_DISCOVERY" in str(exc)


def test_cross_projection_drift_detected_and_cleared():
    registry=[{"worker_id":"keddeh.blade06","accepted_shares":24250,"rejected_shares":14}]
    telemetry=[{"worker_id":"keddeh.blade06","accepted_shares":24260,"rejected_shares":14}]
    result=reconcile_records(registry,telemetry)
    assert result["status"]=="DRIFT_DETECTED"
    assert result["drift_count"]==1
    telemetry[0]["accepted_shares"]=24250
    result=reconcile_records(registry,telemetry)
    assert result["status"]=="PASS"
    assert result["drift_count"]==0
