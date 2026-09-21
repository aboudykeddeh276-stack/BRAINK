from __future__ import annotations

import copy
import time

import pytest

from enterprise.node_template_r40 import (
    NodeTemplateRegistry,
    derive_runtime_template,
    legacy_recursive_template,
    materialize_template,
    validate_template,
)
from enterprise.recursive_computer_runtime_r26 import RecursiveComputer


def hci_template():
    template = {
        "definition": {
            "authority": "A.KEDDEH",
            "description": "Reusable HCI primitive.",
            "name": "KEX HCI Command Card",
            "node_id": "HCI_PRIMITIVE_COMMAND_CARD",
            "version": "1.0.0",
        },
        "typed_io": {
            "inputs": [{"name": "user_intent", "type": "string", "required": True}],
            "outputs": [{"name": "command_packet", "type": "KEXCommandPacket", "required": True}],
            "contracts": ["Template identity remains stable."],
        },
        "attributes": {
            "visual": {"surface": "card"},
            "runtime": {"stateful": True},
            "security": {"zero_trust": True},
            "proof": {"ledger_required": True},
        },
        "capability_class": {
            "class": "SMART_NODE",
            "allowed_actions": ["render", "instantiate"],
            "blocked_actions": ["copy_markup_as_identity"],
        },
        "attribution_graph": {
            "author": "A.KEDDEH",
            "source_template": "TPL_HCI_COMMAND_CARD_V1",
            "derived_from": ["KEX_NODE_TEMPLATE_CONTRACT_V1"],
            "credit_edges": [{"from": "A.KEDDEH", "to": "TPL_HCI_COMMAND_CARD_V1", "relation": "PRIMARY_AUTHOR"}],
        },
        "integration_edges": {
            "inbound": [{"from": "USER_INPUT", "to": "user_intent", "type": "intent_edge"}],
            "outbound": [{"from": "command_packet", "to": "BRAINK_DIRECTOR", "type": "command_edge"}],
            "event_edges": [{"event": "NODE_INSTANTIATED", "route": "template->instance->ledger"}],
        },
        "template_contract": {
            "template_id": "TPL_HCI_COMMAND_CARD_V1",
            "instantiation_policy": "Instantiate by contract.",
            "lineage_policy": "Preserve template and parent lineage.",
            "non_copy_policy": "Markup is projection only.",
            "state_policy": "Instance state and observer relations are unique.",
        },
    }
    from enterprise.node_template_r40 import root
    template["definition"]["definition_hash"] = root(template["definition"])
    return template


def test_legacy_template_is_valid():
    validated = validate_template(legacy_recursive_template())
    assert validated["template_contract"]["template_id"] == "TPL_KEX_RECURSIVE_COMPUTER_R26"


def test_materialization_is_deterministic_without_wall_clock():
    template = hci_template()
    a = materialize_template(
        template, parent_lineage=("A",), instance_key="B",
        initial_state={"status": "READY"}, observer_context="OBSERVER2://BRAINK/R26/A/B",
    )
    time.sleep(0.001)
    b = materialize_template(
        template, parent_lineage=("A",), instance_key="B",
        initial_state={"status": "READY"}, observer_context="OBSERVER2://BRAINK/R26/A/B",
    )
    assert a.identity == b.identity
    assert a.instance_integration_edges == b.instance_integration_edges
    assert a.instance_attribution_graph == b.instance_attribution_graph


def test_same_template_produces_distinct_instance_relations():
    template = hci_template()
    left = materialize_template(template, parent_lineage=("A",), instance_key="B", initial_state={"x": 1})
    right = materialize_template(template, parent_lineage=("A",), instance_key="C", initial_state={"x": 1})
    assert left.identity.template_id == right.identity.template_id
    assert left.identity.definition_hash == right.identity.definition_hash
    assert left.identity.template_root == right.identity.template_root
    assert left.identity.instance_lineage_id != right.identity.instance_lineage_id
    assert left.identity.observer_relation_id != right.identity.observer_relation_id
    assert left.identity.integration_root != right.identity.integration_root
    assert left.identity.attribution_root != right.identity.attribution_root


def test_definition_hash_tamper_is_rejected():
    template = hci_template()
    template["definition"]["description"] = "tampered"
    with pytest.raises(ValueError, match="TEMPLATE_DEFINITION_HASH_MISMATCH"):
        validate_template(template)


def test_copy_markup_identity_must_be_blocked():
    template = hci_template()
    template["capability_class"]["blocked_actions"] = []
    with pytest.raises(ValueError, match="TEMPLATE_NON_COPY_POLICY_UNENFORCED"):
        validate_template(template)


def test_recursive_node_persists_template_identity_across_restore(tmp_path):
    root = RecursiveComputer(computer_id="A", state_root=tmp_path / "A")
    child = root.instantiate("B")
    before = child.identity.template_identity
    restored = RecursiveComputer.restore_tree(tmp_path / "A").children["B"]
    assert restored.identity.template_identity == before
    assert restored.identity.template_identity["observer_relation_id"] == "OBSERVER2://BRAINK/R26/A/B"


def test_explicit_template_identity_is_bound_at_construction(tmp_path):
    root = RecursiveComputer(computer_id="A", state_root=tmp_path / "A")
    materialized = materialize_template(
        hci_template(),
        parent_lineage=("A",),
        instance_key="HCI1",
        initial_state={"status": "READY"},
        observer_context="OBSERVER2://BRAINK/R26/A/HCI1",
    )
    child = root.instantiate("HCI1", template_identity=materialized.identity.to_dict())
    assert child.identity.template_identity == materialized.identity.to_dict()
    assert child.readback()["identity"]["template_identity"] == materialized.identity.to_dict()


class MemVFS:
    def __init__(self):
        self.cells = {}

    def cas_write(self, node_id, path, value, expected_hash):
        key = (node_id, path)
        if key in self.cells:
            return {"logical": f"vfs://node/{node_id}/{path}", "result": {"status": "CONFLICT"}}
        self.cells[key] = copy.deepcopy(value)
        return {"logical": f"vfs://node/{node_id}/{path}", "result": {"status": "COMMITTED"}}

    def read(self, node_id, path):
        key = (node_id, path)
        if key not in self.cells:
            return {"logical": f"vfs://node/{node_id}/{path}", "result": {"status": "HOLE"}}
        return {"logical": f"vfs://node/{node_id}/{path}", "result": {"status": "READ", "value": copy.deepcopy(self.cells[key])}}


def test_template_registry_is_idempotent_and_conflict_detecting():
    vfs = MemVFS()
    registry = NodeTemplateRegistry(vfs, "A")
    template = hci_template()
    first = registry.register(template)
    second = registry.register(template)
    assert first["status"] == "REGISTERED"
    assert second["status"] == "EXISTING"
    resolved = registry.resolve(template["template_contract"]["template_id"], template["definition"]["version"])
    assert resolved == validate_template(template)

    changed = copy.deepcopy(template)
    changed["attributes"]["visual"]["surface"] = "different"
    with pytest.raises(RuntimeError, match="TEMPLATE_VERSION_CONFLICT"):
        registry.register(changed)


def test_runtime_template_generalises_resolved_dependencies():
    template = derive_runtime_template(
        data_class="WORKLOAD",
        sector="developer_ops",
        function_id="function://illlm/kex/instantiate",
        process_id="process://illlm/kex/instantiate",
        runtime_action="instantiate",
        mutating=True,
        capabilities=["process", "readback", "process"],
    )
    validated = validate_template(template)
    assert validated["capability_class"]["class"] == "SMART_NODE"
    assert validated["definition"]["data_class"] == "WORKLOAD"
    assert validated["definition"]["sector"] == "developer_ops"
    targets = [e["to"] for e in validated["integration_edges"]["outbound"]]
    assert "capability://process" in targets
    assert "capability://readback" in targets
    assert "runtime-action://instantiate" in targets

    same = derive_runtime_template(
        data_class="WORKLOAD",
        sector="developer_ops",
        function_id="function://illlm/kex/instantiate",
        process_id="process://illlm/kex/instantiate",
        runtime_action="instantiate",
        mutating=True,
        capabilities=["readback", "process"],
    )
    assert same["template_contract"]["template_id"] == template["template_contract"]["template_id"]
    assert same["definition"]["definition_hash"] == template["definition"]["definition_hash"]
