from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Sequence, Tuple


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class CapabilityClass(str, Enum):
    DUMB = "DUMB"
    SMART = "SMART"
    AGENTIC = "AGENTIC"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True)
class PortSpec:
    name: str
    data_type: str
    required: bool = True
    description: str = ""

    def canonical(self) -> Dict[str, Any]:
        return {"name": self.name, "data_type": self.data_type, "required": self.required, "description": self.description}


@dataclass(frozen=True)
class AttributeSpec:
    name: str
    data_type: str
    required: bool = False
    default: Any = None
    mutable_per_instance: bool = True

    def canonical(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "required": self.required,
            "default": copy.deepcopy(self.default),
            "mutable_per_instance": self.mutable_per_instance,
        }


@dataclass(frozen=True)
class AttributionEdge:
    subject: str
    predicate: str
    object: str
    evidence: str | None = None

    def canonical(self) -> Dict[str, Any]:
        return {"subject": self.subject, "predicate": self.predicate, "object": self.object, "evidence": self.evidence}


@dataclass(frozen=True)
class IntegrationContract:
    edge_type: str
    source_port: str
    destination_port: str
    allowed_target_classes: Tuple[str, ...] = ()

    def canonical(self) -> Dict[str, Any]:
        return {
            "edge_type": self.edge_type,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "allowed_target_classes": list(self.allowed_target_classes),
        }


@dataclass(frozen=True)
class TemplateContract:
    template_name: str
    version: str
    parameter_names: Tuple[str, ...]
    reusable: bool = True
    opaque_fragment_copy_allowed: bool = False

    def __post_init__(self) -> None:
        if self.opaque_fragment_copy_allowed:
            raise ValueError("Node templates cannot authorize opaque fragment copying")

    def canonical(self) -> Dict[str, Any]:
        return {
            "template_name": self.template_name,
            "version": self.version,
            "parameter_names": list(self.parameter_names),
            "reusable": self.reusable,
            "opaque_fragment_copy_allowed": self.opaque_fragment_copy_allowed,
        }


@dataclass(frozen=True)
class NodeDefinition:
    node_type: str
    version: str
    capability_class: CapabilityClass
    inputs: Tuple[PortSpec, ...]
    outputs: Tuple[PortSpec, ...]
    attributes: Tuple[AttributeSpec, ...]
    attribution_graph: Tuple[AttributionEdge, ...]
    integration_contracts: Tuple[IntegrationContract, ...]
    template_contract: TemplateContract
    implementation_ref: str
    definition_revision: int = 1
    sector_id: str = "unscoped"
    sector_class: str = "runtime"
    lifecycle: Tuple[str, ...] = ("DEFINED", "READY", "RUNNING", "STOPPED")
    target_constraints: Tuple[str, ...] = ()
    capability_requirements: Tuple[str, ...] = ()
    evidence_requirements: Tuple[str, ...] = ()
    definition_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.node_type or not self.version or not self.implementation_ref:
            raise ValueError("node_type, version and implementation_ref are required")
        if self.definition_revision < 1:
            raise ValueError("definition_revision must be >= 1")
        self._validate_unique_names(self.inputs, "input")
        self._validate_unique_names(self.outputs, "output")
        self._validate_unique_names(self.attributes, "attribute")
        object.__setattr__(self, "definition_id", sha256_hex(self.canonical_definition()))

    @staticmethod
    def _validate_unique_names(items: Sequence[Any], label: str) -> None:
        names = [item.name for item in items]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate {label} name in node definition")

    def canonical_definition(self) -> Dict[str, Any]:
        return {
            "node_type": self.node_type,
            "version": self.version,
            "capability_class": self.capability_class.value,
            "inputs": [x.canonical() for x in self.inputs],
            "outputs": [x.canonical() for x in self.outputs],
            "attributes": [x.canonical() for x in self.attributes],
            "attribution_graph": [x.canonical() for x in self.attribution_graph],
            "integration_contracts": [x.canonical() for x in self.integration_contracts],
            "template_contract": self.template_contract.canonical(),
            "implementation_ref": self.implementation_ref,
            "definition_revision": self.definition_revision,
            "sector_id": self.sector_id,
            "sector_class": self.sector_class,
            "lifecycle": list(self.lifecycle),
            "target_constraints": list(self.target_constraints),
            "capability_requirements": list(self.capability_requirements),
            "evidence_requirements": list(self.evidence_requirements),
        }


@dataclass(frozen=True)
class ObserverRelation:
    observer_id: str
    relation_type: str = "OBSERVES"

    def canonical(self) -> Dict[str, str]:
        return {"observer_id": self.observer_id, "relation_type": self.relation_type}


@dataclass(frozen=True)
class IntegrationEdge:
    edge_id: str
    edge_type: str
    source_instance_id: str
    source_port: str
    destination_instance_id: str
    destination_port: str
    attribution: Tuple[AttributionEdge, ...] = ()

    def canonical(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type,
            "source_instance_id": self.source_instance_id,
            "source_port": self.source_port,
            "destination_instance_id": self.destination_instance_id,
            "destination_port": self.destination_port,
            "attribution": [x.canonical() for x in self.attribution],
        }


@dataclass
class NodeInstance:
    definition_id: str
    template_identity: str
    instance_id: str
    state: Dict[str, Any]
    attributes: Dict[str, Any]
    observer_relation: ObserverRelation
    integration_edges: list[IntegrationEdge]
    attribution_graph: list[AttributionEdge]
    definition_revision: int
    target_profile: str
    capability_grant: Tuple[str, ...]
    lifecycle_state: str = "DEFINED"
    lineage_parent_instance_id: str | None = None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "template_identity": self.template_identity,
            "instance_id": self.instance_id,
            "state": copy.deepcopy(self.state),
            "attributes": copy.deepcopy(self.attributes),
            "observer_relation": self.observer_relation.canonical(),
            "integration_edges": [x.canonical() for x in self.integration_edges],
            "attribution_graph": [x.canonical() for x in self.attribution_graph],
            "definition_revision": self.definition_revision,
            "target_profile": self.target_profile,
            "capability_grant": list(self.capability_grant),
            "lifecycle_state": self.lifecycle_state,
            "lineage_parent_instance_id": self.lineage_parent_instance_id,
        }

    def state_hash(self) -> str:
        return sha256_hex(self.snapshot())


class NodeTemplateRegistry:
    def __init__(self) -> None:
        self._definitions: Dict[str, NodeDefinition] = {}
        self._template_index: Dict[str, str] = {}
        self._instances: Dict[str, NodeInstance] = {}

    def register(self, definition: NodeDefinition) -> str:
        existing = self._definitions.get(definition.definition_id)
        if existing is not None and existing != definition:
            raise ValueError("Definition hash collision")
        template_identity = self.template_identity(definition)
        bound = self._template_index.get(template_identity)
        if bound is not None and bound != definition.definition_id:
            raise ValueError("Template identity already bound to a different definition")
        self._definitions[definition.definition_id] = definition
        self._template_index[template_identity] = definition.definition_id
        return definition.definition_id

    @staticmethod
    def template_identity(definition: NodeDefinition) -> str:
        return sha256_hex({"template_contract": definition.template_contract.canonical(), "definition_id": definition.definition_id})

    def instantiate(
        self,
        definition_id: str,
        *,
        parameters: Mapping[str, Any] | None = None,
        initial_state: Mapping[str, Any] | None = None,
        observer_id: str = "OBSERVER2",
        target_profile: str = "LOCAL",
        capability_grant: Sequence[str] = (),
        instance_id: str | None = None,
        lineage_parent_instance_id: str | None = None,
        attribution: Sequence[AttributionEdge] = (),
    ) -> NodeInstance:
        definition = self._definitions.get(definition_id)
        if definition is None:
            raise KeyError(f"Unknown node definition: {definition_id}")
        if definition.target_constraints and target_profile not in definition.target_constraints:
            raise ValueError(f"Target profile not permitted: {target_profile}")
        requested_grants = set(capability_grant)
        allowed_grants = set(definition.capability_requirements)
        if not requested_grants.issubset(allowed_grants):
            raise ValueError("Instance capability grant exceeds definition capability envelope")
        params = dict(parameters or {})
        allowed = set(definition.template_contract.parameter_names)
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(f"Unknown template parameters: {sorted(unknown)}")

        attributes: Dict[str, Any] = {}
        for spec in definition.attributes:
            value = params.get(spec.name, copy.deepcopy(spec.default))
            if spec.required and value is None:
                raise ValueError(f"Missing required attribute parameter: {spec.name}")
            attributes[spec.name] = value

        new_instance_id = instance_id or f"node-{uuid.uuid4()}"
        if new_instance_id in self._instances:
            raise ValueError(f"Duplicate node instance id: {new_instance_id}")

        lineage = list(definition.attribution_graph)
        lineage.extend(copy.deepcopy(list(attribution)))
        lineage.append(AttributionEdge(new_instance_id, "INSTANCE_OF", definition.definition_id))
        if lineage_parent_instance_id:
            lineage.append(AttributionEdge(new_instance_id, "DERIVED_FROM_INSTANCE", lineage_parent_instance_id))

        instance = NodeInstance(
            definition_id=definition.definition_id,
            template_identity=self.template_identity(definition),
            instance_id=new_instance_id,
            state=copy.deepcopy(dict(initial_state or {})),
            attributes=copy.deepcopy(attributes),
            observer_relation=ObserverRelation(observer_id),
            integration_edges=[],
            attribution_graph=lineage,
            definition_revision=definition.definition_revision,
            target_profile=target_profile,
            capability_grant=tuple(sorted(requested_grants)),
            lifecycle_state=definition.lifecycle[0] if definition.lifecycle else "DEFINED",
            lineage_parent_instance_id=lineage_parent_instance_id,
        )
        self._instances[new_instance_id] = instance
        return instance

    def connect(
        self,
        source_instance_id: str,
        destination_instance_id: str,
        *,
        edge_type: str,
        source_port: str,
        destination_port: str,
        attribution: Sequence[AttributionEdge] = (),
    ) -> IntegrationEdge:
        source = self._instances[source_instance_id]
        destination = self._instances[destination_instance_id]
        source_definition = self._definitions[source.definition_id]
        destination_definition = self._definitions[destination.definition_id]

        source_ports = {x.name: x for x in source_definition.outputs}
        destination_ports = {x.name: x for x in destination_definition.inputs}
        if source_port not in source_ports:
            raise ValueError(f"Unknown source output port: {source_port}")
        if destination_port not in destination_ports:
            raise ValueError(f"Unknown destination input port: {destination_port}")
        if source_ports[source_port].data_type != destination_ports[destination_port].data_type:
            raise TypeError("Integration port type mismatch")

        contract_ok = any(
            c.edge_type == edge_type
            and c.source_port == source_port
            and c.destination_port == destination_port
            and (not c.allowed_target_classes or destination_definition.capability_class.value in c.allowed_target_classes)
            for c in source_definition.integration_contracts
        )
        if not contract_ok:
            raise ValueError("Integration edge is not permitted by source node contract")

        edge_body = {
            "edge_type": edge_type,
            "source_instance_id": source_instance_id,
            "source_port": source_port,
            "destination_instance_id": destination_instance_id,
            "destination_port": destination_port,
        }
        edge = IntegrationEdge(
            edge_id=sha256_hex(edge_body),
            edge_type=edge_type,
            source_instance_id=source_instance_id,
            source_port=source_port,
            destination_instance_id=destination_instance_id,
            destination_port=destination_port,
            attribution=tuple(attribution),
        )
        source.integration_edges.append(edge)
        destination.integration_edges.append(edge)
        return edge

    def definition(self, definition_id: str) -> NodeDefinition:
        return self._definitions[definition_id]

    def instance(self, instance_id: str) -> NodeInstance:
        return self._instances[instance_id]

    def estate_snapshot(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "definitions": {key: value.canonical_definition() for key, value in sorted(self._definitions.items())},
            "instances": {key: value.snapshot() for key, value in sorted(self._instances.items())},
        })
