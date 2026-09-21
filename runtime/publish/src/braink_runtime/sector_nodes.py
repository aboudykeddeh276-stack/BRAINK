from __future__ import annotations

from .node_identity import Attribution, IntegrationEdge, NodeTemplate, TypedPort, validate_instance

SECTOR_TEMPLATE = NodeTemplate(
    template_id="KEX-NODE-SIP-02-SECTOR",
    definition_version="2",
    stable_definition="Reusable KEX/BRAINK sector node identity contract",
    capability_class="DUMB_OR_SMART_BY_BOUND_CAPABILITY",
    inputs=(
        TypedPort("request", "SectorRequest"),
        TypedPort("context", "AddressableContext"),
    ),
    outputs=(
        TypedPort("result", "SectorResult"),
        TypedPort("evidence", "RuntimeEvidence"),
    ),
    attributes={
        "contract": "KEX-NODE-SIP-02",
        "reuse_rule": "TEMPLATE_NOT_COPIED_MARKUP",
    },
    attribution=Attribution(authored_by="KEX-NODE-SIP-02"),
)


def _instance(
    instance_id: str,
    sector: str,
    target_context: str,
    observer: str,
    edges: tuple[IntegrationEdge, ...],
    authority: str,
    validator: str,
):
    node = SECTOR_TEMPLATE.instantiate(
        instance_id=instance_id,
        local_state="READY",
        observer_relation=observer,
        attribution=Attribution(
            provisioned_by="KEX-NODE-SIP-02",
            routed_by="BRAINK",
        ),
        integration_edges=edges,
        authority_binding=authority,
        validator_binding=validator,
        attributes={
            **SECTOR_TEMPLATE.attributes,
            "sector": sector,
        },
        target_context=target_context,
    )
    validate_instance(SECTOR_TEMPLATE, node)
    return node


SECTOR_INSTANCES = {
    "CASEPATH": _instance(
        "KEX-SECTOR-CASEPATH-01",
        "CASEPATH",
        "app://casepath",
        "observer://casepath/node-identity",
        (
            IntegrationEdge("casepath-saas", "USES", "adapter://saas/casepath"),
            IntegrationEdge("casepath-storage", "REQUIRES", "required://storage/durable"),
        ),
        "CASEPATH_BUSINESS_RUNTIME_BY_CAPABILITY",
        "CASEPATH_BOUND_VALIDATOR",
    ),
    "MATHEMATICS_SCIENCE": _instance(
        "KEX-SECTOR-MATHSCI-01",
        "MATHEMATICS_SCIENCE",
        "KEX::AKD_KEX_NATIVE_RUNTIME::SCIENCE::06::K::maths",
        "observer://kex/science",
        (),
        "DNTG_RESEARCH_BY_CAPABILITY",
        "SCIENCE_BOUND_VALIDATOR",
    ),
    "LAW": _instance(
        "KEX-SECTOR-LAW-01",
        "LAW",
        "app://casepath",
        "observer://casepath/legal-semantics",
        (
            IntegrationEdge("law-casepath", "EXECUTES_WITHIN", "app://casepath"),
        ),
        "CASEPATH_LEGAL_SEMANTICS_BY_CAPABILITY",
        "LEGAL_DOMAIN_VALIDATOR",
    ),
    "GOOGLE_PLATFORM_SERVICES": _instance(
        "KEX-SECTOR-GOOGLE-01",
        "GOOGLE_PLATFORM_SERVICES",
        "runtime/publish/src/braink_runtime/google_adapter.py",
        "observer://braink/google-adapter",
        (),
        "USER_OPERATOR_OAUTH_AUTHORITY",
        "GOOGLE_ADAPTER_READBACK_VALIDATOR",
    ),
    "MESH_INFRASTRUCTURE": _instance(
        "KEX-SECTOR-MESH-01",
        "MESH_INFRASTRUCTURE",
        "mesh://braink/infrastructure",
        "observer://braink/mesh",
        (
            IntegrationEdge("mesh-ingress", "REQUIRES", "required://network/ingress"),
            IntegrationEdge("mesh-trust", "REQUIRES", "required://security/trust-registry"),
            IntegrationEdge("mesh-observe", "REQUIRES", "required://operations/observability"),
        ),
        "MESH_CAPABILITY_AUTHORITY",
        "MESH_ADMISSION_VALIDATOR",
    ),
    "HCI": _instance(
        "KEX-SECTOR-HCI-01",
        "HCI",
        "tool://IL-LLM-HCI",
        "observer://illlm/hci",
        (
            IntegrationEdge("hci-ledger", "REQUIRES", "runtime://ledger"),
        ),
        "HCI_CAPABILITY_AUTHORITY",
        "HCI_READBACK_VALIDATOR",
    ),
    "STORAGE": _instance(
        "KEX-SECTOR-STORAGE-01",
        "STORAGE",
        "required://storage/durable",
        "observer://kex/storage",
        (
            IntegrationEdge("storage-vfs", "SERVES", "app://braink/workbook"),
        ),
        "STORAGE_CAPABILITY_AUTHORITY",
        "STORAGE_DURABILITY_VALIDATOR",
    ),
    "NETWORKING": _instance(
        "KEX-SECTOR-NETWORK-01",
        "NETWORKING",
        "required://network/ingress",
        "observer://kex/network",
        (
            IntegrationEdge("network-mesh", "SERVES", "mesh://braink/infrastructure"),
        ),
        "NETWORK_CAPABILITY_AUTHORITY",
        "NETWORK_READBACK_VALIDATOR",
    ),
    "RUNTIME": _instance(
        "KEX-SECTOR-RUNTIME-01",
        "RUNTIME",
        "braink://local/orchestrator",
        "observer://braink/runtime",
        (
            IntegrationEdge("runtime-vfs", "USES", "app://braink/workbook"),
        ),
        "BRAINK_RUNTIME_CAPABILITY_AUTHORITY",
        "RUNTIME_RECEIPT_VALIDATOR",
    ),
}


def describe_sector_instances() -> list[dict[str, object]]:
    return [node.describe() for node in SECTOR_INSTANCES.values()]


def validate_sector_instances() -> dict[str, object]:
    nodes = list(SECTOR_INSTANCES.values())
    for node in nodes:
        validate_instance(SECTOR_TEMPLATE, node)
    instance_ids = {n.instance_id for n in nodes}
    observers = {n.observer_relation for n in nodes}
    sectors = {n.attributes["sector"] for n in nodes}
    fingerprints = {n.definition_fingerprint for n in nodes}
    return {
        "schema": "kex.node.sector-deployment.v1",
        "status": "PASS",
        "count": len(nodes),
        "unique_instance_ids": len(instance_ids),
        "unique_observers": len(observers),
        "unique_sectors": len(sectors),
        "definition_fingerprints": list(fingerprints),
        "same_template_definition": len(fingerprints) == 1,
        "no_instance_identity_collision": len(instance_ids) == len(nodes),
        "no_observer_collision": len(observers) == len(nodes),
    }
