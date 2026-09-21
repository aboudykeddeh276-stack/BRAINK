from dataclasses import replace

import pytest

from braink_runtime.node_identity import validate_instance
from braink_runtime.sector_nodes import SECTOR_INSTANCES, SECTOR_TEMPLATE, validate_sector_instances


def test_all_named_sectors_instantiated():
    assert set(SECTOR_INSTANCES) == {
        "CASEPATH",
        "MATHEMATICS_SCIENCE",
        "LAW",
        "GOOGLE_PLATFORM_SERVICES",
        "MESH_INFRASTRUCTURE",
        "HCI",
        "STORAGE",
        "NETWORKING",
        "RUNTIME",
    }


def test_one_definition_many_independent_instances():
    receipt = validate_sector_instances()
    assert receipt["status"] == "PASS"
    assert receipt["count"] == 9
    assert receipt["same_template_definition"] is True
    assert receipt["no_instance_identity_collision"] is True
    assert receipt["no_observer_collision"] is True


def test_state_target_attribution_edges_are_instance_owned():
    casepath = SECTOR_INSTANCES["CASEPATH"]
    mesh = SECTOR_INSTANCES["MESH_INFRASTRUCTURE"]
    assert casepath.instance_id != mesh.instance_id
    assert casepath.target_context != mesh.target_context
    assert casepath.observer_relation != mesh.observer_relation
    assert casepath.integration_edges != mesh.integration_edges
    assert casepath.attributes["sector"] != mesh.attributes["sector"]


def test_capability_escalation_still_rejected_across_sector_rollout():
    node = SECTOR_INSTANCES["HCI"]
    forged = replace(node, capability_class="SMART")
    with pytest.raises(ValueError, match="CAPABILITY_ESCALATION_REJECTED"):
        validate_instance(SECTOR_TEMPLATE, forged)


def test_template_definition_unchanged_by_sector_instantiation():
    before = SECTOR_TEMPLATE.definition_fingerprint
    _ = tuple(SECTOR_INSTANCES.values())
    assert SECTOR_TEMPLATE.definition_fingerprint == before
