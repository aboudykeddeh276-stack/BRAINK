from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CapabilityClass = Literal["DUMB", "SMART", "DUMB_OR_SMART_BY_BOUND_CAPABILITY"]


@dataclass(frozen=True)
class TypedPort:
    name: str
    type_name: str
    required: bool = True


@dataclass(frozen=True)
class Attribution:
    authored_by: str | None = None
    executed_by: str | None = None
    validated_by: str | None = None
    routed_by: str | None = None
    provisioned_by: str | None = None


@dataclass(frozen=True)
class IntegrationEdge:
    edge_id: str
    relation: str
    target: str
    contract: str | None = None


@dataclass(frozen=True)
class NodeTemplate:
    template_id: str
    definition_version: str
    stable_definition: str
    capability_class: CapabilityClass
    inputs: tuple[TypedPort, ...]
    outputs: tuple[TypedPort, ...]
    attributes: dict[str, Any] = field(default_factory=dict)
    attribution: Attribution = field(default_factory=Attribution)
    integration_edges: tuple[IntegrationEdge, ...] = ()
    authority_binding: str = "CONTEXTUAL_BY_CAPABILITY"
    validator_binding: str = "CONTEXTUAL_BY_VALIDATOR_ROLE"

    def instantiate(
        self,
        *,
        node_id: str,
        local_state: str,
        observer_relation: str,
        attribution: Attribution,
        integration_edges: tuple[IntegrationEdge, ...] | None = None,
        authority_binding: str | None = None,
        validator_binding: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> "NodeInstance":
        if not node_id.strip():
            raise ValueError("NODE_ID_REQUIRED")
        if not observer_relation.strip():
            raise ValueError("OBSERVER_RELATION_REQUIRED")
        return NodeInstance(
            node_id=node_id,
            template_id=self.template_id,
            definition_version=self.definition_version,
            lineage_parent=self.template_id,
            capability_class=self.capability_class,
            inputs=self.inputs,
            outputs=self.outputs,
            attributes=dict(attributes if attributes is not None else self.attributes),
            attribution=attribution,
            integration_edges=integration_edges if integration_edges is not None else self.integration_edges,
            local_state=local_state,
            observer_relation=observer_relation,
            authority_binding=authority_binding or self.authority_binding,
            validator_binding=validator_binding or self.validator_binding,
        )


@dataclass(frozen=True)
class NodeInstance:
    node_id: str
    template_id: str
    definition_version: str
    lineage_parent: str
    capability_class: CapabilityClass
    inputs: tuple[TypedPort, ...]
    outputs: tuple[TypedPort, ...]
    attributes: dict[str, Any]
    attribution: Attribution
    integration_edges: tuple[IntegrationEdge, ...]
    local_state: str
    observer_relation: str
    authority_binding: str
    validator_binding: str

    def describe(self) -> dict[str, Any]:
        return {
            "schema": "braink.node.instance.v1",
            **asdict(self),
            "lineage_authority_rule": "LINEAGE_IS_PROVENANCE_NOT_AUTOMATIC_AUTHORITY",
            "instance_policy": "PRESERVE_TEMPLATE_LINEAGE_WITH_INDEPENDENT_INSTANCE_STATE_OBSERVER_EDGES_ATTRIBUTION",
        }


def validate_instance(template: NodeTemplate, instance: NodeInstance) -> None:
    if instance.template_id != template.template_id:
        raise ValueError("TEMPLATE_ID_MISMATCH")
    if instance.definition_version != template.definition_version:
        raise ValueError("TEMPLATE_VERSION_MISMATCH")
    if instance.inputs != template.inputs or instance.outputs != template.outputs:
        raise ValueError("TYPED_IO_CONTRACT_MISMATCH")
    if not instance.observer_relation:
        raise ValueError("OBSERVER_RELATION_REQUIRED")
    if not instance.authority_binding:
        raise ValueError("AUTHORITY_BINDING_REQUIRED")
    if not instance.validator_binding:
        raise ValueError("VALIDATOR_BINDING_REQUIRED")
