from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence
import copy
import hashlib
import json
import re

SCHEMA = "braink.node-template.r40/v1"
CAPABILITY_CLASSES = {"DUMB_NODE", "SMART_NODE", "AGENTIC_NODE", "SYSTEM_NODE"}
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,127}$")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"TEMPLATE_{name.upper()}_OBJECT_REQUIRED")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"TEMPLATE_{name.upper()}_LIST_REQUIRED")
    return value


def _validate_port_list(items: Any, name: str) -> None:
    ports = _require_list(items, name)
    seen: set[str] = set()
    for item in ports:
        port = _require_mapping(item, name + "_port")
        port_name = str(port.get("name", "")).strip()
        port_type = str(port.get("type", "")).strip()
        if not _NAME.fullmatch(port_name):
            raise ValueError(f"TEMPLATE_{name.upper()}_PORT_NAME_INVALID")
        if not port_type:
            raise ValueError(f"TEMPLATE_{name.upper()}_PORT_TYPE_REQUIRED")
        if port_name in seen:
            raise ValueError(f"TEMPLATE_{name.upper()}_PORT_DUPLICATE:{port_name}")
        seen.add(port_name)


def validate_template(template: Mapping[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(dict(_require_mapping(template, "root")))
    required = {
        "definition", "typed_io", "attributes", "capability_class",
        "attribution_graph", "integration_edges", "template_contract",
    }
    missing = sorted(required - set(body))
    if missing:
        raise ValueError("TEMPLATE_FIELDS_MISSING:" + ",".join(missing))

    definition = _require_mapping(body["definition"], "definition")
    template_contract = _require_mapping(body["template_contract"], "contract")
    typed_io = _require_mapping(body["typed_io"], "typed_io")
    capability = _require_mapping(body["capability_class"], "capability_class")
    attribution = _require_mapping(body["attribution_graph"], "attribution_graph")
    integration = _require_mapping(body["integration_edges"], "integration_edges")

    node_id = str(definition.get("node_id", "")).strip()
    version = str(definition.get("version", "")).strip()
    authority = str(definition.get("authority", "")).strip()
    template_id = str(template_contract.get("template_id", "")).strip()
    if not _NAME.fullmatch(node_id):
        raise ValueError("TEMPLATE_NODE_ID_INVALID")
    if not _SEGMENT.fullmatch(version):
        raise ValueError("TEMPLATE_VERSION_INVALID")
    if not authority:
        raise ValueError("TEMPLATE_AUTHORITY_REQUIRED")
    if not _NAME.fullmatch(template_id):
        raise ValueError("TEMPLATE_ID_INVALID")

    claimed_definition_hash = str(definition.get("definition_hash", "")).strip().lower()
    definition_body = dict(definition)
    definition_body.pop("definition_hash", None)
    computed_definition_hash = root(definition_body)
    if claimed_definition_hash != computed_definition_hash:
        raise ValueError("TEMPLATE_DEFINITION_HASH_MISMATCH")

    capability_class = str(capability.get("class", "")).strip()
    if capability_class not in CAPABILITY_CLASSES:
        raise ValueError("TEMPLATE_CAPABILITY_CLASS_INVALID")
    allowed = _require_list(capability.get("allowed_actions"), "allowed_actions")
    blocked = _require_list(capability.get("blocked_actions"), "blocked_actions")
    if "copy_markup_as_identity" not in blocked:
        raise ValueError("TEMPLATE_NON_COPY_POLICY_UNENFORCED")
    if set(map(str, allowed)) & set(map(str, blocked)):
        raise ValueError("TEMPLATE_CAPABILITY_ALLOW_BLOCK_CONFLICT")

    _validate_port_list(typed_io.get("inputs"), "inputs")
    _validate_port_list(typed_io.get("outputs"), "outputs")
    _require_list(typed_io.get("contracts"), "typed_io_contracts")
    _require_list(attribution.get("derived_from"), "derived_from")
    _require_list(attribution.get("credit_edges"), "credit_edges")
    for edge_group in ("inbound", "outbound", "event_edges"):
        _require_list(integration.get(edge_group), "integration_" + edge_group)

    if str(attribution.get("author", "")).strip() != authority:
        raise ValueError("TEMPLATE_ATTRIBUTION_AUTHORITY_MISMATCH")
    if str(attribution.get("source_template", "")).strip() != template_id:
        raise ValueError("TEMPLATE_ATTRIBUTION_SOURCE_MISMATCH")

    return body


@dataclass(frozen=True)
class NodeTemplateIdentity:
    schema: str
    template_id: str
    stable_definition_id: str
    definition_hash: str
    template_root: str
    capability_class: str
    typed_io_root: str
    attributes_root: str
    instance_lineage_id: str
    observer_relation_id: str
    attribution_root: str
    integration_root: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NodeTemplateMaterialization:
    identity: NodeTemplateIdentity
    template: dict[str, Any]
    instance_attribution_graph: dict[str, Any]
    instance_integration_edges: dict[str, Any]
    state_seed_root: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "template": copy.deepcopy(self.template),
            "instance_attribution_graph": copy.deepcopy(self.instance_attribution_graph),
            "instance_integration_edges": copy.deepcopy(self.instance_integration_edges),
            "state_seed_root": self.state_seed_root,
        }


def materialize_template(
    template: Mapping[str, Any],
    *,
    parent_lineage: Sequence[str],
    instance_key: str,
    initial_state: Mapping[str, Any] | None = None,
    observer_context: str | None = None,
) -> NodeTemplateMaterialization:
    body = validate_template(template)
    instance_key = str(instance_key).strip()
    if not _SEGMENT.fullmatch(instance_key):
        raise ValueError("TEMPLATE_INSTANCE_KEY_INVALID")
    lineage = tuple(str(x) for x in parent_lineage)
    if not lineage or any(not _SEGMENT.fullmatch(x) for x in lineage):
        raise ValueError("TEMPLATE_PARENT_LINEAGE_INVALID")

    definition = body["definition"]
    contract = body["template_contract"]
    state_seed_root = root(dict(initial_state or {}))
    observer = str(observer_context or ("OBSERVER2://BRAINK/R26/" + "/".join(lineage + (instance_key,))))

    seed = {
        "template_id": contract["template_id"],
        "definition_hash": definition["definition_hash"],
        "parent_lineage": list(lineage),
        "instance_key": instance_key,
        "state_seed_root": state_seed_root,
        "observer_relation": observer,
    }
    instance_lineage_id = root(seed)

    def materialize_edges(items: list[Any], direction: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for index, raw in enumerate(items, start=1):
            edge = copy.deepcopy(dict(_require_mapping(raw, "integration_edge")))
            edge["edge_id"] = f"{direction.upper()}_{index}_{root({'lineage': instance_lineage_id, 'edge': edge})[:16].upper()}"
            out.append(edge)
        return out

    template_edges = body["integration_edges"]
    instance_edges = {
        "inbound": materialize_edges(template_edges["inbound"], "in"),
        "outbound": materialize_edges(template_edges["outbound"], "out"),
        "event_edges": materialize_edges(template_edges["event_edges"], "event"),
    }

    attribution = copy.deepcopy(body["attribution_graph"])
    attribution["instance_credit_edge"] = {
        "from": contract["template_id"],
        "to": instance_key,
        "relation": "INSTANTIATED_AS",
        "instance_lineage_id": instance_lineage_id,
    }

    identity = NodeTemplateIdentity(
        schema=SCHEMA,
        template_id=contract["template_id"],
        stable_definition_id=definition["node_id"],
        definition_hash=definition["definition_hash"],
        template_root=root(body),
        capability_class=body["capability_class"]["class"],
        typed_io_root=root(body["typed_io"]),
        attributes_root=root(body["attributes"]),
        instance_lineage_id=instance_lineage_id,
        observer_relation_id=observer,
        attribution_root=root(attribution),
        integration_root=root(instance_edges),
    )
    return NodeTemplateMaterialization(identity, body, attribution, instance_edges, state_seed_root)


def legacy_recursive_template() -> dict[str, Any]:
    definition = {
        "authority": "A.KEDDEH",
        "description": "Resident recursive BRAINK/KEX computer node.",
        "name": "KEX Recursive Computer",
        "node_id": "KEX_RECURSIVE_COMPUTER",
        "version": "r26",
    }
    definition["definition_hash"] = root(definition)
    return {
        "definition": definition,
        "typed_io": {
            "inputs": [{"name": "command", "type": "KEXCommandPacket", "required": True}],
            "outputs": [{"name": "proof_event", "type": "LedgerEvent", "required": True}],
            "contracts": ["Mutation authority remains with the resident KEX runtime."],
        },
        "attributes": {
            "runtime": {"stateful": True, "recursive": True},
            "proof": {"ledger_required": True},
            "security": {"observer2_governed": True},
            "visual": {"projection_only": True},
        },
        "capability_class": {
            "class": "SYSTEM_NODE",
            "allowed_actions": ["instantiate", "state.write", "memory.write", "readback"],
            "blocked_actions": ["copy_markup_as_identity"],
        },
        "attribution_graph": {
            "author": "A.KEDDEH",
            "source_template": "TPL_KEX_RECURSIVE_COMPUTER_R26",
            "derived_from": ["BRAINK", "KEX", "IL-LLM", "Observer2"],
            "credit_edges": [{"from": "A.KEDDEH", "to": "TPL_KEX_RECURSIVE_COMPUTER_R26", "relation": "PRIMARY_AUTHOR"}],
        },
        "integration_edges": {
            "inbound": [{"from": "IL_LLM", "to": "command", "type": "authority_edge"}],
            "outbound": [{"from": "proof_event", "to": "LEDGER", "type": "proof_edge"}],
            "event_edges": [{"event": "NODE_INSTANTIATED", "route": "template->instance->ledger"}],
        },
        "template_contract": {
            "template_id": "TPL_KEX_RECURSIVE_COMPUTER_R26",
            "instantiation_policy": "Materialize through RecursiveComputer constructor authority.",
            "lineage_policy": "Preserve recursive lineage and template lineage.",
            "non_copy_policy": "Rendered projections are never node identity.",
            "state_policy": "Each instance owns independent state, Observer2 relation, integration-edge ids and attribution root.",
        },
    }
