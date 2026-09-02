from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import execute_recursive_proof


def test_recursive_constructor_state_memory_lineage_and_warm_boot(tmp_path: Path) -> None:
    proof = execute_recursive_proof(tmp_path)

    assert proof["status"] == "VERIFIED"
    assert proof["lineage"]["A"] == ["A"]
    assert proof["lineage"]["B"] == ["A", "B"]
    assert proof["lineage"]["C"] == ["A", "B", "C"]
    assert proof["lineage"]["D"] == ["A", "B", "C", "D"]

    assert proof["memory"]["A"]["seed"] == 297
    assert proof["memory"]["B"]["seed"] == 297
    assert proof["memory"]["B"]["child"] == 88
    assert proof["memory"]["C"] == {"seed": 297, "child": 88}
    assert proof["memory"]["D"] == {"seed": 297, "child": 88}

    assert proof["warm_boot"]["restored_computer"] == "C"
    assert proof["warm_boot"]["restored_lineage"] == ["A", "B", "C"]
    assert proof["warm_boot"]["restored_memory"] == {"seed": 297, "child": 88}
    assert proof["warm_boot"]["post_restore_descendant"] == "D"

    constructor_ids = set(proof["constructor_ids"].values())
    assert constructor_ids == {"constructor://kex/recursive-computer/r26"}
    assert all(proof["ledger_verified"].values())
    assert len(set(proof["state_roots"].values())) == 4
