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


def test_randomized_telemetry_requires_evidence() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "server.ts").write_text("const load = Math.random() * 100;\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "EVIDENCE_REQUIRED"
        assert "RANDOMIZED_TELEMETRY" in result["categories"]


def test_synthetic_hardware_and_certification_are_detected() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "server.ts").write_text(
            "const banner = 'CPU: BRAINK Quantum Core @ ∞ GHz ISO 9001 CERTIFIED';\n",
            encoding="utf-8",
        )
        result = run_gate(root)
        assert "SYNTHETIC_HARDWARE_CLAIM" in result["categories"]
        assert "UNSUPPORTED_CERTIFICATION_CLAIM" in result["categories"]


def test_hardcoded_online_state_is_not_live_evidence() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "api.js").write_text("return { status: 'ONLINE' };\n", encoding="utf-8")
        result = run_gate(root)
        assert "HARDCODED_HEALTH" in result["categories"]
