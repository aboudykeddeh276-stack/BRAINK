from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CapabilityClass = Literal["DUMB", "SMART", "DUMB_OR_SMART_BY_BOUND_CAPABILITY"]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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

    def contract_payload(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "definition_version": self.definition_version,
            "stable_definition": self.stable_definition,
            "capability_class": self.capability_class,
            "inputs": [asdict(x) for x in self.inputs],
            "outputs": [asdict(x) for x in self.outputs],
            "attributes": self.attributes,
            "attribution": asdict(self.attribution),
            "integration_edges": [asdict(x) for x in self.integration_edges],
            "authority_binding": self.authority_binding,
            "validator_binding": self.validator_binding,
        }

    @property
    def definition_fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.contract_payload())).hexdigest()

    def instantiate(
        self,
        *,
        instance_id: str,
        local_state: str,
        observer_relation: str,
        attribution: Attribution,
        integration_edges: tuple[IntegrationEdge, ...] | None = None,
        authority_binding: str | None = None,
        validator_binding: str | None = None,
        attributes: dict[str, Any] | None = None,
        target_context: str = "UNBOUND_TARGET",
    ) -> "NodeInstance":
        if not instance_id.strip():
            raise ValueError("INSTANCE_ID_REQUIRED")
        if not observer_relation.strip():
            raise ValueError("OBSERVER_RELATION_REQUIRED")
        return NodeInstance(
            instance_id=instance_id,
            template_id=self.template_id,
            definition_version=self.definition_version,
            definition_fingerprint=self.definition_fingerprint,
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
            target_context=target_context,
        )


@dataclass(frozen=True)
class NodeInstance:
    instance_id: str
    template_id: str
    definition_version: str
    definition_fingerprint: str
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
    target_context: str

    def describe(self) -> dict[str, Any]:
        return {
            "schema": "kex.node.instance.v2",
            **asdict(self),
            "lineage_authority_rule": "LINEAGE_IS_PROVENANCE_NOT_AUTOMATIC_AUTHORITY",
            "instance_policy": "PRESERVE_TEMPLATE_LINEAGE_WITH_INDEPENDENT_INSTANCE_STATE_OBSERVER_EDGES_ATTRIBUTION_TARGET",
        }


def validate_instance(template: NodeTemplate, instance: NodeInstance) -> None:
    if instance.template_id != template.template_id:
        raise ValueError("TEMPLATE_ID_MISMATCH")
    if instance.definition_version != template.definition_version:
        raise ValueError("TEMPLATE_VERSION_MISMATCH")
    if instance.definition_fingerprint != template.definition_fingerprint:
        raise ValueError("DEFINITION_FINGERPRINT_MISMATCH")
    if instance.inputs != template.inputs or instance.outputs != template.outputs:
        raise ValueError("TYPED_IO_CONTRACT_MISMATCH")
    if instance.capability_class != template.capability_class:
        raise ValueError("CAPABILITY_ESCALATION_REJECTED")
    if not instance.observer_relation:
        raise ValueError("OBSERVER_RELATION_REQUIRED")
    if not instance.authority_binding:
        raise ValueError("AUTHORITY_BINDING_REQUIRED")
    if not instance.validator_binding:
        raise ValueError("VALIDATOR_BINDING_REQUIRED")
