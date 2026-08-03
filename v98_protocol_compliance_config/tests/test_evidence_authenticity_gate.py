from __future__ import annotations

import tempfile
from pathlib import Path

from src.keddeh_evidence_authenticity_gate import run_gate


def test_clean_source_passes() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "app.ts").write_text("export const health = observedHealth;\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "LOCAL_PASS"
        assert result["finding_count"] == 0
        assert result["global_stop"] is False


def test_randomized_projection_is_declared_variant_not_invalidity() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "visual_demo.ts").write_text("const animationLoad = Math.random() * 100;\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "PASS_WITH_DECLARED_VARIANTS"
        finding = result["findings"][0]
        assert finding["context_variant"] == "PROJECTION"
        assert finding["invariant_assessment"] == "CONTEXTUALLY_VALID_VARIANT"
        assert finding["derived_state"] == "DECLARED_VARIANT"


def test_undeclared_generated_value_opens_context_task() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "server.ts").write_text("const load = Math.random() * 100;\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "CONTEXT_RESOLUTION_REQUIRED"
        assert result["global_stop"] is False
        assert result["context_resolution_count"] == 1


def test_observed_health_requires_receipt_correlation() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "heartbeat_readback.js").write_text("return { status: 'ONLINE' };\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "EVIDENCE_CORRELATION_REQUIRED"
        finding = result["findings"][0]
        assert finding["context_variant"] == "OBSERVED"
        assert finding["capability_effect"].startswith("Hold only the associated")


def test_target_hardware_declaration_is_preserved_as_variant() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "hardware_target_manifest.ts").write_text(
            "const target = 'CPU: BRAINK Quantum Core @ ∞ GHz';\n",
            encoding="utf-8",
        )
        result = run_gate(root)
        assert result["promotion_state"] == "PASS_WITH_DECLARED_VARIANTS"
        assert "HARDWARE_REPRESENTATION" in result["categories"]
        assert result["findings"][0]["context_variant"] == "TARGET_DECLARATION"


def test_assurance_word_without_context_is_not_global_rejection() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "api.js").write_text("const state = 'ATTESTED';\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "CONTEXT_RESOLUTION_REQUIRED"
        assert result["global_stop"] is False
        assert result["findings"][0]["category"] == "ASSURANCE_REPRESENTATION"
