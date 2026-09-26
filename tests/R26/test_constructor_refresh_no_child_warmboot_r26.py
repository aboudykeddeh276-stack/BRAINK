from pathlib import Path

from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


def _ledger_len(node: RecursiveComputer) -> int:
    return len(node.ledger.events)


def test_constructor_refresh_does_not_warmboot_existing_children(tmp_path: Path):
    root = RecursiveComputer(computer_id="A", state_root=tmp_path / "A")
    first = root.instantiate("B")
    before = _ledger_len(first)

    root.instantiate("C")
    root.instantiate("D")

    restored_first = RecursiveComputer.restore(tmp_path / "A" / "descendants" / "B")
    # One event is added by this explicit restore. Constructor refresh itself must
    # not have mutated B's ledger while admitting C and D.
    assert _ledger_len(restored_first) == before + 1
    assert root.readback()["children"] == ["B", "C", "D"]


def test_nonrecursive_restore_tracks_committed_child_ids_without_rehydrating_tree(tmp_path: Path):
    root = RecursiveComputer(computer_id="A", state_root=tmp_path / "A")
    root.instantiate("B")
    root.instantiate("C")

    restored = RecursiveComputer.restore(tmp_path / "A")
    assert restored.children == {}
    assert restored._committed_child_ids == {"B", "C"}

    restored.instantiate("D")
    assert restored.readback()["children"] == ["B", "C", "D"]
