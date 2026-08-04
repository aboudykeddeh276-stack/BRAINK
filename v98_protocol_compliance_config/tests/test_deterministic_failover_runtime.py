from pathlib import Path

from keddeh_deterministic_failover_runtime import DeterministicFailoverRuntime


ROOT = Path(__file__).resolve().parents[1]


def runtime() -> DeterministicFailoverRuntime:
    return DeterministicFailoverRuntime(ROOT)


def test_registry_enforces_exact_path_order():
    engine = runtime()
    assert engine.validate() == []
    assert engine.path_order == ["path_a", "path_b", "path_c"]


def test_path_a_is_selected_when_complete():
    result = runtime().execute(
        "service://universal/example",
        ["component://database/primary", "component://model/primary"],
    )
    output = result["outputs"][0]
    assert output["selected_path"] == "path_a"
    assert output["output_state"] == "FULLY_DERIVED"
    assert result["service_state"] == "FULLY_DERIVED"


def test_path_b_is_selected_only_after_path_a_fails():
    result = runtime().execute(
        "service://universal/example",
        ["component://database/replica", "component://model/fallback"],
    )
    output = result["outputs"][0]
    assert [item["path_id"] for item in output["evaluated_paths"]] == ["path_a", "path_b"]
    assert output["evaluated_paths"][0]["complete"] is False
    assert output["selected_path"] == "path_b"
    assert result["service_state"] == "SUBSTITUTED"


def test_path_c_is_selected_only_after_a_and_b_fail():
    result = runtime().execute(
        "service://universal/example",
        ["component://api/cache", "component://ledger/prior-authority"],
    )
    output = result["outputs"][0]
    assert [item["path_id"] for item in output["evaluated_paths"]] == [
        "path_a",
        "path_b",
        "path_c",
    ]
    assert output["selected_path"] == "path_c"
    assert result["service_state"] == "DEGRADED_DERIVATION"


def test_partial_inputs_from_different_paths_are_not_blended():
    result = runtime().execute(
        "service://universal/example",
        ["component://database/primary", "component://model/fallback"],
    )
    output = result["outputs"][0]
    assert output["selected_path"] is None
    assert output["output_state"] == "BOUNDED_STOP"
    assert result["global_stop"] is False


def test_component_loss_removes_only_supplied_inputs():
    result = runtime().execute(
        "service://visual/projection",
        ["component://gpu/cpu-renderer"],
    )
    states = {output["output_id"]: output for output in result["outputs"]}
    assert states["output.frame"]["selected_path"] == "path_b"
    assert states["output.frame"]["derived"] is True
    assert states["output.hardware-acceleration-proof"]["derived"] is False
    assert result["service_state"] == "SUBSTITUTED"
    assert result["impact_radius"] == ["output.hardware-acceleration-proof"]
    assert result["preserved_outputs"] == ["output.frame"]


def test_mac_absence_preserves_portable_validation():
    result = runtime().execute(
        "service://apple/native-validation",
        ["component://host/github-linux"],
    )
    outputs = {output["output_id"]: output for output in result["outputs"]}
    assert outputs["output.portable-validation"]["selected_path"] == "path_b"
    assert outputs["output.apple-native-proof"]["selected_path"] is None
    assert result["service_state"] == "SUBSTITUTED"
    assert result["global_stop"] is False


def test_bilateral_service_output_indexes_are_written():
    result = runtime().execute(
        "service://application/runtime",
        ["component://server/application-primary"],
    )
    assert result["bilateral_readback"] is True
