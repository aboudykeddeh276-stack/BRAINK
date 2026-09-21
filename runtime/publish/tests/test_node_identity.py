from braink_runtime.node_identity import (
    Attribution,
    IntegrationEdge,
    NodeTemplate,
    TypedPort,
    validate_instance,
)
from braink_runtime.node_stack import describe_profile


def test_template_instantiation_preserves_contract_but_not_instance_state():
    template = NodeTemplate(
        template_id="TPL-HCI-PRIMITIVE",
        definition_version="1",
        stable_definition="Reusable HCI primitive",
        capability_class="DUMB_OR_SMART_BY_BOUND_CAPABILITY",
        inputs=(TypedPort("event", "HCIEvent"),),
        outputs=(TypedPort("result", "HCIResult"),),
        attributes={"role": "control"},
        attribution=Attribution(authored_by="author"),
        integration_edges=(IntegrationEdge("EDGE-TEMPLATE", "ROUTES_TO", "NODE-X"),),
    )
    a = template.instantiate(
        node_id="NODE-A",
        local_state="READY",
        observer_relation="OBSERVER-A",
        attribution=Attribution(executed_by="agent-a", validated_by="validator-a"),
    )
    b = template.instantiate(
        node_id="NODE-B",
        local_state="BUSY",
        observer_relation="OBSERVER-B",
        attribution=Attribution(executed_by="agent-b", validated_by="validator-b"),
        integration_edges=(IntegrationEdge("EDGE-B", "BINDS_TO", "NODE-Y"),),
    )

    validate_instance(template, a)
    validate_instance(template, b)
    assert a.template_id == b.template_id == template.template_id
    assert a.inputs == b.inputs == template.inputs
    assert a.outputs == b.outputs == template.outputs
    assert a.node_id != b.node_id
    assert a.local_state != b.local_state
    assert a.observer_relation != b.observer_relation
    assert a.attribution.executed_by != b.attribution.executed_by
    assert a.integration_edges != b.integration_edges


def test_lineage_does_not_assign_authority():
    template = NodeTemplate(
        template_id="TPL-CONTEXT",
        definition_version="1",
        stable_definition="Contextual authority template",
        capability_class="SMART",
        inputs=(),
        outputs=(),
    )
    node = template.instantiate(
        node_id="NODE-CONTEXT",
        local_state="READY",
        observer_relation="OBSERVER-CONTEXT",
        attribution=Attribution(),
        authority_binding="CAPABILITY:EXPERT_EXECUTOR",
        validator_binding="VALIDATOR:DOMAIN_EXPERT",
    )
    assert node.lineage_parent == "TPL-CONTEXT"
    assert node.authority_binding == "CAPABILITY:EXPERT_EXECUTOR"
    assert node.validator_binding == "VALIDATOR:DOMAIN_EXPERT"
    assert "PARENT" not in node.authority_binding


def test_stack_profile_exposes_contextual_authority():
    profile = describe_profile("SOFTWARE_CREATION_NODE")
    assert profile["authority"] == "CONTEXTUAL_BY_CAPABILITY"
    assert profile["promotion_authority"] == "BOUND_BY_CONTEXTUAL_AUTHORITY_AND_VALID_RECEIPT"
    assert profile["lineage_authority_rule"] == "LINEAGE_IS_PROVENANCE_NOT_AUTOMATIC_AUTHORITY"
    assert profile["validator_binding"] == "CONTEXTUAL_BY_VALIDATOR_ROLE"
