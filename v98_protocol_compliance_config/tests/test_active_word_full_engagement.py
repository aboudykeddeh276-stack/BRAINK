from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.keddeh_active_word_full_engagement import ActiveWordFullEngagement

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp: Path) -> None:
    (tmp / "config").mkdir(parents=True, exist_ok=True)
    for name in (
        "active_word_full_engagement.json",
        "active_story_lexicon.json",
        "active_word_governance.json",
        "il_llm_active_story_registry.json",
    ):
        shutil.copy2(ROOT / "config" / name, tmp / "config" / name)


def test_full_engagement_preserves_all_registered_words_and_expressions() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        result = ActiveWordFullEngagement(tmp).run(iterations=3, emit_receipt=True)
        assert result["words_engaged"] == 13
        assert result["expressions_engaged"] == 4
        assert result["derivations_preserved"] > 0
        assert result["bilateral_readback"] is True
        assert result["promotion_state"] == "REINTEGRATED"


def test_every_word_expression_link_has_reverse_link() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        ActiveWordFullEngagement(tmp).run(iterations=2, emit_receipt=True)
        import json
        forward = json.loads((tmp / "runtime_volume" / "active_word_full_engagement" / "indexes" / "word_to_expression.json").read_text())
        reverse = json.loads((tmp / "runtime_volume" / "active_word_full_engagement" / "indexes" / "expression_to_word.json").read_text())
        for word, expressions in forward.items():
            for expression in expressions:
                assert word in reverse[expression]


def test_service_bindings_are_bilateral() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        ActiveWordFullEngagement(tmp).run(iterations=2)
        import json
        transition_to_service = json.loads((tmp / "runtime_volume" / "active_word_full_engagement" / "indexes" / "transition_to_service.json").read_text())
        service_to_transition = json.loads((tmp / "runtime_volume" / "active_word_full_engagement" / "indexes" / "service_to_transition.json").read_text())
        for expression, services in transition_to_service.items():
            for service in services:
                assert expression in service_to_transition[service]


def test_iteration_converges_without_erasing_prior_derivations() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        result = ActiveWordFullEngagement(tmp).run(iterations=5)
        assert result["iterations_executed"] >= 2
        assert result["iteration_receipts"][-1]["converged"] is True
        assert result["iteration_receipts"][-1]["derivations_total"] == result["derivations_preserved"]


def test_local_binding_gap_is_non_terminal_and_mirror_routed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        prepare(tmp)
        import json
        story_path = tmp / "config" / "active_story_lexicon.json"
        story = json.loads(story_path.read_text())
        story["expressions"][0]["handler"] = ""
        story_path.write_text(json.dumps(story), encoding="utf-8")
        result = ActiveWordFullEngagement(tmp).run(iterations=2)
        assert result["mirror_lane_proposals"] == 1
        assert result["global_stop"] is False
        proposals = list((tmp / "runtime_volume" / "workplans" / "active_word_mirror_lane").glob("*.json"))
        assert len(proposals) == 1
