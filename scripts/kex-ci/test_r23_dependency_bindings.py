from pathlib import Path
import tempfile

from enterprise.foundry_closure_r23 import DurableStore
from enterprise.r23_dependency_bindings import R23DependencyResolver, ResearchProvenanceRuntime, authorship_receipt
from enterprise.governance.authorship_guard import classify


class FakeFabric:
    def __init__(self):
        self.resources = {
            "customer_services_mail": {
                "resource_id": "EXT-mail-1",
                "service": "customer_services_mail",
                "provider": "Gmail",
                "external_ref": "label://customer-services",
                "state": "BOUND_CONTROL_PLANE",
            }
        }

    def resolve_resource(self, service):
        return self.resources.get(service)

    def create_service_instance(self, business_id, service):
        resource = self.resolve_resource(service)
        if not resource:
            return {"state": "HELD_RESOURCE_HOLE", "business_id": business_id, "service": service}
        return {
            "instance_id": "SVC-test-mail",
            "business_id": business_id,
            "service": service,
            "resource_id": resource["resource_id"],
            "state": "ACTIVE",
            "receipt": {"status": "PASS"},
        }


with tempfile.TemporaryDirectory() as td:
    store = DurableStore(Path(td) / "state.json")
    fabric = FakeFabric()
    resolver = R23DependencyResolver(store, fabric)

    mail = resolver.bind_mail_control_plane("casepath")
    assert mail["status"] == "EXECUTED"
    assert mail["effect"]["claim_boundary"] == "GMAIL_CONTROL_PLANE_BOUND_NOT_SMTP_DELIVERY_PROVEN"

    domain = resolver.resolve_publication_actuator()
    assert domain.state == "TYPED_HOLE"
    assert domain.capability == "domain.public_activation"

    research = ResearchProvenanceRuntime(store)
    qualified = research.evaluate(
        "research://qualified",
        [{"claim": "bounded"}],
        [{"source": "library://evidence/1", "sha256": "a" * 64, "observed": True}],
        [{"status": "PASS"}, {"status": "PASS"}],
        "verifier://independent",
    )
    assert qualified.status == "EXECUTED"
    assert qualified.effect["state"] == "PROMOTED_PROVENANCE_QUALIFIED"
    assert qualified.effect["provenance_score"] == 1.0

    held = research.evaluate(
        "research://held",
        [{"claim": "bounded"}],
        [{"source": "library://evidence/2", "observed": True}],
        [{"status": "PASS"}],
        "verifier://independent",
    )
    assert held.effect["state"] == "REVIEW_REQUIRED"
    assert held.effect["provenance_score"] < 1.0

    authored = authorship_receipt(
        "service://r23/dependency-bindings",
        "deployment://r23/dependency-bindings/r1",
        "b" * 64,
        "2026-09-02T04:20:00Z",
        "R23",
    )
    status = classify(authored, known_predecessors={"R23"})
    assert status.status == "AKD_AUTHORED"

    reloaded = DurableStore(Path(td) / "state.json")
    assert reloaded.state["state_root"] == store.state["state_root"]
    assert len(reloaded.state["receipts"]) >= 4

print("R23_DEPENDENCY_BINDINGS_PASS")
