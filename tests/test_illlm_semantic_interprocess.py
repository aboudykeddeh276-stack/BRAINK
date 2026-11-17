"""Independent OS-process ledger writers, fsync/readback and semantic verifier.
Architect: A. Keddeh. Real filesystem and multiprocessing; no mock workers.
"""
from __future__ import annotations
import json
import multiprocessing
from runtime.illlm_ledger import ILLLMImmutableLedger


def _writer(path, lane, barrier, failures):
    try:
        ledger = ILLLMImmutableLedger(path)
        barrier.wait(timeout=20)
        for n in range(10):
            ledger.append(source_uri=f"process://{lane}", source_level="PROCESS", semantic_type="NATIVE_TEST",
                          correlation_id=f"lane/{lane}/{n}", payload={"lane": lane, "n": n},
                          lexical_state={"lane": lane}, illlm_state={"n": n})
    except BaseException as exc:
        failures.put(repr(exc))
        raise


def test_six_native_writers_and_reopen(tmp_path):
    path = tmp_path / "interprocess-ledger.jsonl"
    ctx = multiprocessing.get_context("spawn")
    barrier, failures = ctx.Barrier(6), ctx.Queue()
    children = [ctx.Process(target=_writer, args=(str(path), lane, barrier, failures)) for lane in range(6)]
    for child in children: child.start()
    for child in children: child.join(45)
    for child in children:
        if child.is_alive(): child.terminate(); child.join(10)
    assert [p.exitcode for p in children] == [0] * 6
    assert failures.empty()
    verification = ILLLMImmutableLedger(path).verify()
    assert verification["status"] == "PASS", verification
    assert verification["events"] == 60
    assert len({json.loads(line)["event_id"] for line in path.read_text().splitlines()}) == 60
    assert ILLLMImmutableLedger(path).verify() == verification


def _v4_writer(path, lane, barrier, failures):
    from runtime.illlm_ledger import root
    try:
        ledger = ILLLMImmutableLedger(path)
        barrier.wait(timeout=20)
        for n in range(5):
            state = {
                "instance_id": f"resident-lane-{lane}",
                "source_sha256": "3cf4c7713e2fa4e38cfba840336854b3e488c899c35fd27e7a21e376b910b1d3",
                "observer": {"wholeIdentity": "1_BRAINK", "stateFormula": "O_AS_OBS=1_O⊗S_O(E)", "queryRoot": "source-bound"},
                "polygon": {"iteration": n + 1, "lastSuccessor": f"①_{n + 1}", "history_tail": []},
                "v4_receipt": {"id": f"R-lane-{lane}-{n}", "type": "POLYGON_100_ITERATION", "iteration": n + 1, "status": "PASS"},
            }
            source = state["source_sha256"]
            candidate = root(state)
            ledger.append(
                source_uri=f"braink://learning/v4/browser/{state['instance_id']}",
                source_level="OBSERVER_MIRROR_ONLY", semantic_type="POLYGON_MIRROR_CANDIDATE",
                correlation_id=root({"instance_id": state["instance_id"], "v4_receipt_id": state["v4_receipt"]["id"], "source_sha256": source}),
                payload={"candidate_hash": candidate, "sequence": n + 1, "observer_policy_digest": root({"candidate_must_be_mirror_only": True, "resident_capability_required": True}), "state": state, "promotion_state": "NOT_PROMOTED"},
                lexical_state={"source": "V4", "receipt": state["v4_receipt"], "polygon_lexical_context": state["polygon"]},
                illlm_state={"candidate": candidate, "observer": state["observer"], "source": source, "authority": "MIRROR_ONLY"},
                idempotency_payload_field="candidate_hash",
            )
    except BaseException as exc:
        failures.put(repr(exc))
        raise


def test_native_v4_interprocess_semantic_rehash_rejected(tmp_path):
    from runtime.illlm_ledger import root
    path = tmp_path / "v4-interprocess.jsonl"
    ctx = multiprocessing.get_context("spawn")
    barrier, failures = ctx.Barrier(4), ctx.Queue()
    children = [ctx.Process(target=_v4_writer, args=(str(path), lane, barrier, failures)) for lane in range(4)]
    for child in children: child.start()
    for child in children: child.join(45)
    for child in children:
        if child.is_alive(): child.terminate(); child.join(10)
    assert [p.exitcode for p in children] == [0] * 4
    assert failures.empty()
    verified = ILLLMImmutableLedger(path).verify()
    assert verified["status"] == "PASS" and verified["events"] == 20, verified
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert len({event["correlation_id"] for event in events}) == 20
    # A privileged out-of-band writer can rehash the chain; semantic readback
    # must still reject a forged admission-policy digest at event 7.
    events[6]["payload"]["observer_policy_digest"] = "0" * 64
    previous = events[5]["event_root"]
    for event in events[6:]:
        event["previous_event_root"] = previous
        event["event_root"] = root({k: v for k, v in event.items() if k != "event_root"})
        previous = event["event_root"]
    path.write_text("".join(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n" for e in events))
    assert ILLLMImmutableLedger(path).verify() == {
        "status": "FAILED", "reason": "SEMANTIC_V4_ADMISSION_POLICY", "index": 6,
    }
