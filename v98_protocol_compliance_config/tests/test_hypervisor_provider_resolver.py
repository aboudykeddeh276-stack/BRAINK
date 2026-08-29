from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.keddeh_hypervisor_provider_resolver import HypervisorProviderResolver

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp: Path) -> HypervisorProviderResolver:
    (tmp / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "hypervisor_provider_registry.json", tmp / "config" / "hypervisor_provider_registry.json")
    return HypervisorProviderResolver(tmp)


def test_registry_is_valid() -> None:
    assert HypervisorProviderResolver(ROOT).validate() == []


def test_github_hosted_runtime_ignites_portable_workload() -> None:
    with tempfile.TemporaryDirectory() as raw:
        runtime = prepare(Path(raw))
        result = runtime.resolve("workload://host-acceptance/portable")
        assert result["promotion_state"] == "PROVIDER_SELECTED"
        assert result["selected_provider"] == "provider://github-hosted/ubuntu-x64"
        assert result["selected_runner"] == "ubuntu-latest"
        assert result["bilateral_readback"] is True


def test_substitutable_arm64_provider_can_run_without_m3() -> None:
    with tempfile.TemporaryDirectory() as raw:
        runtime = prepare(Path(raw))
        result = runtime.resolve(
            "workload://host-acceptance/portable",
            ["provider://github-hosted/ubuntu-arm64"],
        )
        assert result["promotion_state"] == "PROVIDER_SELECTED"
        assert result["global_stop"] is False


def test_apple_specific_workload_defers_when_m3_is_absent() -> None:
    with tempfile.TemporaryDirectory() as raw:
        runtime = prepare(Path(raw))
        result = runtime.resolve("workload://apple/native-validation")
        assert result["promotion_state"] == "DEFERRED"
        assert result["selected_provider"] is None
        assert result["global_stop"] is False
        packet = result["continuation_packet"]
        assert packet["criticality"] == "EXTERNAL_GATE"
        assert "workload://host-acceptance/portable" in packet["unaffected_domains"]


def test_m3_is_selected_only_after_observed_availability() -> None:
    with tempfile.TemporaryDirectory() as raw:
        runtime = prepare(Path(raw))
        result = runtime.resolve(
            "workload://apple/native-validation",
            ["provider://local/m3"],
        )
        assert result["promotion_state"] == "PROVIDER_SELECTED"
        assert result["selected_provider"] == "provider://local/m3"
        assert result["selected_runner"] == ["self-hosted", "macOS", "ARM64", "KEDDEH-M3"]
        assert result["bilateral_readback"] is True


def test_unknown_workload_is_bounded() -> None:
    result = HypervisorProviderResolver(ROOT).resolve("workload://unknown")
    assert result["promotion_state"] == "CONTEXT_RESOLUTION_REQUIRED"
    assert result["global_stop"] is False
