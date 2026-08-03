from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.keddeh_active_word_governance import ActiveWordGovernance

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp: Path) -> None:
    (tmp / "config").mkdir(parents=True, exist_ok=True)
    for name in ("active_word_governance.json", "active_story_lexicon.json", "il_llm_active_story_registry.json"):
        shutil.copy2(ROOT / "config" / name, tmp / "config" / name)


def test_registry_and_il_llm_binding_are_valid() -> None:
    runtime = ActiveWordGovernance(ROOT)
    assert runtime.validate() == []
    assert runtime.policy["equation"] == "A_W=f(W,C,E,S,V,O,L,T)"
    assert runtime.il_llm["wordModel"] == "(- WORD +)"


def test_word_instance_preserves_full_context_and_bilateral_links() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        runtime = ActiveWordGovernance(tmp)
        result = runtime.instantiate(
            "word://observe",
            {"domain": "mesh", "purpose": "node health", "environment": "test-mesh"},
            {"subject": "node.mesh-17", "action": "observe", "object": "runtime availability"},
            "sector://mesh-infrastructure",
            "service://health-state-monitor",
            {"type": "heartbeat-probe", "identity": "probe://mesh-17"},
            "LOCAL_PROCESS",
            "RECEIPT_BACKED",
            {"required": ["heartbeat"], "optional": ["telemetry"]},
            "ACTIVE",
            {"source": "word://observe", "prior_state": "DEFINED", "next_state": "OBSERVED"},
            ["OBSERVED", "DEGRADED", "DEFERRED"],
        )
        assert result["promotion_state"] == "ACTIVE_WORD_INSTANTIATED"
        assert result["bilateral_readback"] is True
        active = result["active_word"]
        assert active["canonical_identity"] == "word://observe"
        assert active["service"] == "service://health-state-monitor"
        assert active["observer"]["identity"] == "probe://mesh-17"


def test_unknown_word_opens_learning_without_global_stop() -> None:
    runtime = ActiveWordGovernance(ROOT)
    result = runtime.instantiate(
        "word://unknown-new-term", {}, {}, "sector://x", "service://x", {},
        "CONTROL_PLANE", "DECLARED", {"required": [], "optional": []},
        "DEFINED", {"source": "source://test"}, ["CONTEXTUALIZED"],
    )
    assert result["promotion_state"] == "LEARNING_REQUIRED"
    assert result["global_stop"] is False


def test_disallowed_transition_is_bounded_to_service() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        runtime = ActiveWordGovernance(tmp)
        created = runtime.instantiate(
            "word://verify",
            {"domain": "deployment"},
            {"subject": "manifest", "action": "verify", "object": "hash"},
            "sector://application-deployment",
            "service://k-cloud-admission",
            {"identity": "service://k-cloud-admission"},
            "CONTROL_PLANE",
            "RECEIPT_BACKED",
            {"required": ["manifest-integrity"], "optional": []},
            "ACTIVE",
            {"source": "canonical-lexicon"},
            ["OBSERVED", "VERIFIED"],
        )
        blocked = runtime.transition(created["active_word"]["address"], "PRESERVED", {"receipt": "x"})
        assert blocked["promotion_state"] == "BOUNDED_STOP"
        assert blocked["global_stop"] is False
        assert "service://k-cloud-admission" in blocked["capability_effect"]
