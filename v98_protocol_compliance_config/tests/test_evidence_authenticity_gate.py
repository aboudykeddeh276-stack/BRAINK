from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.keddeh_evidence_authenticity_gate import run_gate


def write_registry(root: Path, contexts: list[dict]) -> None:
    config = root / "config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "evidence_context_registry.json").write_text(
        json.dumps({"version": "TEST", "contexts": contexts}), encoding="utf-8"
    )


def test_clean_source_passes() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "app.ts").write_text("export const health = observedHealth;\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "LOCAL_PASS"
        assert result["finding_count"] == 0
        assert result["global_stop"] is False


def test_explicit_projection_context_is_valid_bounded_variant() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        write_registry(root, [{
            "path_pattern": "visual.ts", "capability": "TPU_LOAD_PROJECTION",
            "purpose": "PROJECTION", "observer": "BROWSER_UI",
            "environment": "WORKSTATION", "execution_plane": "BROWSER_PROJECTION",
            "evidence_class": "MODELED", "promotion_boundary": "PROJECTION_ONLY"
        }])
        (root / "visual.ts").write_text("const load = Math.random() * 100;\n", encoding="utf-8")
        result = run_gate(root)
        finding = result["findings"][0]
        assert result["promotion_state"] == "PASS_WITH_DECLARED_VARIANTS"
        assert finding["context"]["capability"] == "TPU_LOAD_PROJECTION"
        assert finding["context"]["execution_plane"] == "BROWSER_PROJECTION"
        assert finding["derived_state"] == "DECLARED_VARIANT"
        assert finding["continuation_packet"] == ""


def test_undeclared_generated_value_creates_bounded_packet() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "server.ts").write_text("const load = Math.random() * 100;\n", encoding="utf-8")
        result = run_gate(root)
        finding = result["findings"][0]
        assert result["promotion_state"] == "CONTEXT_RESOLUTION_REQUIRED"
        assert result["global_stop"] is False
        assert result["continuation_packet_count"] == 1
        packet = Path(finding["continuation_packet"])
        assert packet.exists()
        payload = json.loads(packet.read_text(encoding="utf-8"))
        assert payload["impact_radius"] == ["UNDECLARED_CAPABILITY"]
        assert "all capabilities outside" in payload["unaffected_domains"][0]


def test_observed_health_requires_correlation_not_global_stop() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        write_registry(root, [{
            "path_pattern": "health.js", "capability": "NODE_HEALTH",
            "purpose": "RUNTIME_HEALTH", "observer": "MESH_MONITOR",
            "environment": "LOCAL_MESH", "execution_plane": "LOCAL_PROCESS",
            "evidence_class": "OBSERVED", "promotion_boundary": "NODE_HEALTH_ONLY"
        }])
        (root / "health.js").write_text("return { status: 'ONLINE' };\n", encoding="utf-8")
        result = run_gate(root)
        finding = result["findings"][0]
        assert result["promotion_state"] == "EVIDENCE_CORRELATION_REQUIRED"
        assert result["global_stop"] is False
        assert finding["context"]["observer"] == "MESH_MONITOR"
        assert "NODE_HEALTH" in finding["capability_effect"]
        assert Path(finding["continuation_packet"]).exists()


def test_target_hardware_declaration_preserves_target_variant() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "hardware_target_manifest.ts").write_text(
            "const target = 'CPU: BRAINK Quantum Core @ ∞ GHz';\n", encoding="utf-8"
        )
        result = run_gate(root)
        assert result["promotion_state"] == "PASS_WITH_DECLARED_VARIANTS"
        assert result["findings"][0]["context"]["purpose"] == "TARGET_DECLARATION"


def test_assurance_term_without_context_opens_resolution_only() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "api.js").write_text("const state = 'ATTESTED';\n", encoding="utf-8")
        result = run_gate(root)
        assert result["promotion_state"] == "CONTEXT_RESOLUTION_REQUIRED"
        assert result["global_stop"] is False
        assert result["findings"][0]["category"] == "ASSURANCE_REPRESENTATION"
