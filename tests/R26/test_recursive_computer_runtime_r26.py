from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import execute_recursive_proof


def test_recursive_tree_rehydration_and_post_restore_constructor(tmp_path: Path) -> None:
    proof = execute_recursive_proof(tmp_path)

    assert proof["status"] == "VERIFIED"
    assert proof["lineage"]["A"] == ["A"]
    assert proof["lineage"]["B"] == ["A", "B"]
    assert proof["lineage"]["C"] == ["A", "B", "C"]
    assert proof["lineage"]["D"] == ["A", "B", "C", "D"]
    assert proof["lineage"]["E"] == ["A", "B", "C", "D", "E"]

    assert proof["memory"]["A"] == {"seed": 297}
    assert proof["memory"]["B"] == {"child": 88, "seed": 297}
    assert proof["memory"]["C"] == {"child": 88, "seed": 297}
    assert proof["memory"]["D"] == {"child": 88, "seed": 297}
    assert proof["memory"]["E"] == {"child": 88, "seed": 297}

    assert proof["tree"] == {
        "A": ["B"],
        "B": ["C"],
        "C": ["D"],
        "D": ["E"],
        "E": [],
    }
    assert proof["warm_boot"]["root_restored"] == "A"
    assert proof["warm_boot"]["rehydrated_path"] == ["A", "B", "C", "D"]
    assert proof["warm_boot"]["post_tree_restore_descendant"] == "E"

    assert set(proof["constructor_ids"].values()) == {
        "constructor://kex/recursive-computer/r26"
    }
    assert all(proof["ledger_verified"].values())
    assert len(set(proof["state_roots"].values())) == 5
