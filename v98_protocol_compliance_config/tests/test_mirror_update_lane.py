from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keddeh_mirror_update_lane as mirror


def test_mirror_lane_config_preserves_non_manual_promotion() -> None:
    cfg = mirror.read_json(ROOT / "config" / "mirror_update_lane.json")
    rules = cfg["promotion_rules"]
    assert rules["manual_promotion_allowed"] is False
    assert rules["agent_self_promotion_allowed"] is False
    assert rules["acceptance_harness_promotion_required"] is True
    assert rules["hash_used_as_functional_proof"] is False


def test_mirror_lane_documents_exist() -> None:
    cfg = mirror.read_json(ROOT / "config" / "mirror_update_lane.json")
    for rel in cfg["source_documents"] + cfg["required_mirror_documents"]:
        path = ROOT / rel
        assert path.exists(), rel
        assert path.is_file(), rel


def test_mirror_lane_runs_writes_readback_and_handoff() -> None:
    final = mirror.run_mirror_lane(ROOT, emit_receipt=True)
    receipt = final["receipt"]
    assert receipt["promotion_state"] == "LOCAL_PASS"
    assert receipt["all_documents_present"] is True
    assert receipt["ledger_readback"] is True
    assert final["hash_used_as_functional_proof"] is False
    assert final["certification_claimed"] is False
    outbox = Path(receipt["outbox_manifest"])
    assert outbox.exists()
    assert (ROOT / "evidence" / "mirror_update_lane_receipt.json").exists()
    payload = json.loads((ROOT / "evidence" / "mirror_update_lane_receipt.json").read_text(encoding="utf-8"))
    assert payload["receipt"]["lane_id"] == "mirror_update_lane"
