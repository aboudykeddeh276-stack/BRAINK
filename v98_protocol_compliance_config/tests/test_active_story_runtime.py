from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.keddeh_active_story_runtime import ActiveStoryRuntime

ROOT = Path(__file__).resolve().parents[1]


def make_runtime() -> tuple[tempfile.TemporaryDirectory, Path, ActiveStoryRuntime]:
    raw = tempfile.TemporaryDirectory()
    root = Path(raw.name)
    (root / "config").mkdir(parents=True)
    shutil.copy2(ROOT / "config" / "active_story_lexicon.json", root / "config" / "active_story_lexicon.json")
    return raw, root, ActiveStoryRuntime(root)


def test_registry_and_source_definitions_are_valid() -> None:
    raw, root, runtime = make_runtime()
    try:
        index = runtime.build_index()
        assert index["registry_valid"] is True
        assert index["word_count"] >= 13
        expression = runtime.compose_expression("expression://verify-manifest-before-node-execution")
        assert expression["sourceDefinitions"]["word://verify"]
        assert "readback_required" in expression["sourceInvariants"]["word://verify"]
    finally:
        raw.cleanup()


def test_missing_evidence_holds_only_associated_service() -> None:
    raw, root, runtime = make_runtime()
    try:
        result = runtime.transition(
            "expression://observe-node-health",
            subject="node://17",
            prior_state="REGISTERED",
            next_state="HEALTHY",
            observer="service://health-state-monitor",
            environment="environment://mesh",
            execution_plane="CONTROL_PLANE",
            evidence_class="OBSERVED",
            evidence={"node_id": "17"},
        )
        assert result["promotion_state"] == "EVIDENCE_CORRELATION_REQUIRED"
        assert result["global_stop"] is False
        assert result["capability_effect"] == "hold only service://health-state-monitor transition"
    finally:
        raw.cleanup()


def test_transition_writes_receipt_ledger_and_backlinks() -> None:
    raw, root, runtime = make_runtime()
    try:
        result = runtime.transition(
            "expression://connect-bitcoin-p2p-stream",
            subject="node://bitcoin-local",
            prior_state="DISCONNECTED",
            next_state="PROTOCOL_OBSERVED",
            observer="service://btc-node-observer",
            environment="environment://loopback",
            execution_plane="LOCAL_PROCESS",
            evidence_class="RECEIPT_BACKED",
            evidence={
                "endpoint": "127.0.0.1:8333",
                "network_magic": "0xF9BEB4D9",
                "command": "version",
                "payload_length": 86,
                "checksum_result": "PASS",
                "connection_state": "CONNECTED",
            },
        )
        assert result["promotion_state"] == "LOCAL_PASS"
        assert result["ledger_readback"] is True
        transition_id = result["transition"]["transition_id"]
        assert transition_id in runtime.backlink("word://connect")
        assert transition_id in runtime.backlink("service://btc-node-observer")
        receipts = list((root / "runtime_volume" / "active_story" / "receipts").glob("*.json"))
        assert len(receipts) == 1
        saved = json.loads(receipts[0].read_text(encoding="utf-8"))
        assert saved["transition"]["source_words"] == ["word://connect", "word://stream", "word://verify"]
    finally:
        raw.cleanup()


def test_null_presence_preserves_character_relation_invariants() -> None:
    raw, root, runtime = make_runtime()
    try:
        word = runtime.definition("word://null-presence")
        assert "character_required" in word["invariants"]
        assert "relation_required" in word["invariants"]
        assert "lineage_preserved" in word["invariants"]
    finally:
        raw.cleanup()
