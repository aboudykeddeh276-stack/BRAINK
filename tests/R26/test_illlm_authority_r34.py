from deployment.kex_runtime_service_r34 import ILLLMGovernedRuntimeHost


def test_illlm_state_write_is_resolved_and_observer2_governed(tmp_path):
    host = ILLLMGovernedRuntimeHost(tmp_path / "A", "A")
    out = host.illlm_execute({"intent": "state.write", "lineage": "A", "key": "illlm_evoked", "value": 297})
    assert out["status"] == "EXECUTED"
    assert out["authority"]["process_id"] == "process://illlm/kex/state-write"
    assert out["result"]["state"]["illlm_evoked"] == 297
    assert out["result"]["observer2_governance"]["continuation"] == "FOLLOW_SUCCESSOR_STATE"
    assert out["result"]["ledger_verified"]
    assert out["receipt_ledger_verified"]
    assert host.illlm.verify_receipts()


def test_illlm_recursive_instantiation_and_memory_persist(tmp_path):
    host = ILLLMGovernedRuntimeHost(tmp_path / "A", "A")
    child = host.illlm_execute({"intent": "computer.instantiate", "lineage": "A", "child_id": "B"})
    assert child["result"]["lineage"] == ["A", "B"]
    assert child["result"]["observer2_governance"]["continuation"] == "FOLLOW_SUCCESSOR_STATE"
    mem = host.illlm_execute({"intent": "memory.write", "lineage": "A/B", "key": "seed", "value": 88})
    assert mem["result"]["memory"]["seed"] == 88
    restored = ILLLMGovernedRuntimeHost(tmp_path / "A", "A")
    snap = restored.snapshot(restored.resolve("A/B"))
    assert snap["memory"]["seed"] == 88
    assert snap["ledger_verified"]


def test_illlm_rejects_unbound_intent_without_mutation(tmp_path):
    host = ILLLMGovernedRuntimeHost(tmp_path / "A", "A")
    before = host.snapshot()
    try:
        host.illlm_execute({"intent": "filesystem.delete", "lineage": "A", "path": "/"})
    except ValueError as exc:
        assert str(exc) == "ILLLM_UNRESOLVED_INTENT"
    else:
        raise AssertionError("unbound intent executed")
    after = host.snapshot()
    assert after["state"] == before["state"]
    assert after["memory"] == before["memory"]
    assert after["children"] == before["children"]
