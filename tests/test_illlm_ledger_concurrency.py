"""Actual independent-process file IO regression for shared KS-BRAINK-IL-LLM ledger."""
from __future__ import annotations
import json
import multiprocessing
from pathlib import Path
from runtime.illlm_ledger import ILLLMImmutableLedger


def append_worker(file_path, lane, count, barrier, error_queue):
    try:
        ledger = ILLLMImmutableLedger(file_path)
        barrier.wait(timeout=20)
        for index in range(count):
            receipt = ledger.append(
                source_uri=f"worker://{lane}",
                source_level="CONCURRENT_REAL_PROCESS",
                semantic_type="LEARNING_CANDIDATE",
                correlation_id=f"lane/{lane}/event/{index}",
                payload={"lane": lane, "index": index},
                lexical_state={"lane": lane},
                illlm_state={"index": index},
            )
            if not ledger.read_by_correlation(f"lane/{lane}/event/{index}"):
                raise AssertionError("MISSING_READBACK")
    except BaseException as error:
        error_queue.put(repr(error))


def test_six_independent_process_writers_preserve_all_hash_links(tmp_path):
    path = tmp_path / "illlm.jsonl"
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(6)
    errors = ctx.Queue()
    workers = [ctx.Process(target=append_worker, args=(str(path), i, 10, barrier, errors)) for i in range(6)]
    for process in workers:process.start()
    for process in workers:process.join(40)
    for process in workers:
        if process.is_alive():
            process.terminate();process.join(10)
    assert [p.exitcode for p in workers] == [0] * len(workers)
    complaints = []
    while not errors.empty():complaints.append(errors.get_nowait())
    assert not complaints, complaints
    ledger = ILLLMImmutableLedger(path)
    status = ledger.verify()
    assert status["status"] == "PASS", status
    assert status["events"] == 60, status
    ids = {event["correlation_id"] for event in ledger._events()}
    assert len(ids) == 60
    # Disk close/reopen is an actual readback. No in-memory expected ledger.
    assert ILLLMImmutableLedger(path).verify() == status


def test_tamper_and_truncated_line_prevent_further_write(tmp_path):
    path = tmp_path / "events.jsonl"
    ledger = ILLLMImmutableLedger(path)
    ledger.append(source_uri="src://auth", source_level="SOURCE", semantic_type="TEST", correlation_id="first",
                  payload={"ok": True}, lexical_state={"lex": 1}, illlm_state={"version": 1})
    with path.open("ab") as w:w.write(b'{"partial":')
    assert ledger.verify()["status"] == "FAILED"
    import pytest
    with pytest.raises(RuntimeError, match="UNVERIFIED"):
        ledger.append(source_uri="src://auth", source_level="SOURCE", semantic_type="TEST", correlation_id="second",
                      payload={}, lexical_state={}, illlm_state={})
    assert len(path.read_bytes().splitlines()) == 2
