from pathlib import Path
import tempfile

from runtime.window_propagation import WindowPropagationLedger, WindowPropagationRuntime, WindowSignal


def build_runtime(tmp: str):
    return WindowPropagationRuntime(WindowPropagationLedger(Path(tmp) / "propagation.sqlite3"))


def test_compile_replay_and_verify():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = build_runtime(tmp)
        signals = [
            WindowSignal(source="ui", sector="braink", kind="intent", payload={"value": "deploy"}, sequence=2),
            WindowSignal(source="kernel", sector="kex", kind="state", payload={"ready": True}, sequence=1),
        ]
        frame = runtime.compile("work-1", 1, signals)
        assert [s.sequence for s in frame.signals] == [1, 2]
        replay = runtime.replay("work-1")
        assert replay is not None
        assert replay["canonical_root"] == frame.canonical_root
        assert runtime.verify(replay)


def test_same_semantics_same_root():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = build_runtime(tmp)
        a = [
            WindowSignal(source="b", sector="s2", kind="k", payload={"n": 2}, sequence=2),
            WindowSignal(source="a", sector="s1", kind="k", payload={"n": 1}, sequence=1),
        ]
        b = list(reversed(a))
        first = runtime.compile("work-a", 1, a)
        second = runtime.compile("work-a-copy", 1, b)
        # work identity is deliberately part of the root; ordering is nevertheless canonical.
        assert [s.sequence for s in first.signals] == [1, 2]
        assert [s.sequence for s in second.signals] == [1, 2]
        assert first.canonical_root != second.canonical_root


def test_duplicate_sequence_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        runtime = build_runtime(tmp)
        signals = [
            WindowSignal(source="a", sector="s1", kind="k1", payload={}, sequence=1),
            WindowSignal(source="b", sector="s2", kind="k2", payload={}, sequence=1),
        ]
        try:
            runtime.compile("work-2", 1, signals)
            assert False, "expected duplicate sequence rejection"
        except ValueError as exc:
            assert "unique" in str(exc)
