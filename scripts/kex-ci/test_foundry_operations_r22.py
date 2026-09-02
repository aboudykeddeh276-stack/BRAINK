from __future__ import annotations
from pathlib import Path
import tempfile

from enterprise.foundry_operations_r22 import FoundaryOperationsRuntime


def run():
    with tempfile.TemporaryDirectory(prefix="braink-r22-") as td:
        state = Path(td) / "foundaries.json"
        rt = FoundaryOperationsRuntime(state)

        rt.business.create_undertaking(
            "undertaking://casepath",
            "Operate a legal-service undertaking with reusable enterprise infrastructure.",
            ["genome://legal-service"],
            ["operations", "research", "customer-service", "publishing"],
            ["South Australia"],
        )
        rt.hr.register_team(
            "team://casepath/core",
            "undertaking://casepath",
            ["runtime", "research", "publishing", "customer-service"],
            ["agent.dispatch", "workspace.manage", "publish.stage", "customer.file"],
            ["undertaking://casepath", "vfs://casepath/", "frontage://casepath/"],
        )
        room = rt.servers.materialize_room(
            "room://casepath/production",
            "undertaking://casepath",
            {"HR_SERVER_SET": 1, "AGENTIC_AI_SERVER_SET": 2, "RUNTIME_SERVER_SET": 2, "STORAGE_SERVER_SET": 2, "WEB_SERVER_SET": 2, "PROOF_SERVER_SET": 2},
            {"AGENTIC_AI_SERVER_SET": ["HR_SERVER_SET", "STORAGE_SERVER_SET"], "WEB_SERVER_SET": ["RUNTIME_SERVER_SET"]},
        )
        assert room.effect["instance_count"] == 11

        rt.workspace.create("workspace://casepath/main", "undertaking://casepath", "team://casepath/core")
        f = rt.files.write(
            "vfs://casepath/pages/your-data",
            {"page": "your-data", "patch": "CP-TC-20260727-C01", "state": "COMMITTED"},
            "workspace://casepath/main",
        )
        assert len(f.effect["object_root"]) == 64

        customer = "customer://casepath/demo-001"
        authority = "team://casepath/core"
        created = rt.customers.create_customer_file(
            customer,
            "undertaking://casepath",
            {"privacy_notice": "accepted"},
            {"matter_state": "INTAKE"},
        )
        assert created.effect["revision"] == 1
        updated = rt.customers.update_service_state(customer, {"matter_state": "PREPARATION"}, authority)
        assert updated.effect["revision"] == 2
        attached = rt.customers.attach_document(customer, "vfs://casepath/pages/your-data", "SOURCE_DOCUMENT", authority)
        assert attached.effect["object_root"] == f.effect["object_root"]
        communicated = rt.customers.record_communication(customer, "WEB", "INBOUND", "Customer submitted structured intake", authority)
        assert len(communicated.effect["communication_root"]) == 64
        billed = rt.customers.record_billing_event(customer, "ENTITLEMENT_RECORDED", 14900, "AUD", "local-test-reference", authority)
        assert len(billed.effect["billing_root"]) == 64
        exported = rt.customers.export_manifest(customer, "export://casepath/demo-001/r1", authority)
        assert len(exported.effect["export_root"]) == 64
        closed = rt.customers.close_customer_file(customer, "COMPLETED", {"policy": "retain-by-governed-policy", "deletion_state": "NOT_EXECUTED"}, authority)
        assert closed.effect["state"] == "CLOSED"
        assert rt.store.state["customers"][customer]["revision"] == 7
        assert len(rt.store.state["customers"][customer]["audit"]) == 6

        try:
            rt.customers.update_service_state(customer, {"matter_state": "ILLEGAL_REOPEN"}, authority)
            raise AssertionError("closed customer file accepted service mutation")
        except ValueError as exc:
            assert str(exc) == "CUSTOMER_FILE_NOT_ACTIVE"

        rt.frontages.register_frontage(
            "frontage://casepath/public",
            "undertaking://casepath",
            "casepath.com.au",
            {"/": "service://casepath/root", "/your-data.html": "vfs://casepath/pages/your-data"},
            ["mesh://alpha", "mesh://beta"],
        )
        rt.hci.register_surface(
            "hci://casepath/customer",
            "undertaking://casepath",
            [{"control": "begin", "command": "casepath.intake.begin"}, {"control": "export", "command": "casepath.export"}],
            {"keyboard": True, "labels": True, "errors": "recoverable"},
        )
        lp = rt.landing.manufacture(
            "landing://casepath/main",
            "undertaking://casepath",
            "frontage://casepath/public",
            "Case preparation and source discovery",
            [{"type": "hero"}, {"type": "intake"}, {"type": "trust"}],
            ["BEGIN_INTAKE", "BOOK_CLARITY_SESSION"],
        )
        assert len(lp.effect["page_root"]) == 64

        svg = rt.svg.register_svg(
            "svg://casepath/runtime-map",
            "undertaking://casepath",
            [{"id": "frontage"}, {"id": "runtime"}, {"id": "vfs"}],
            [{"from": "frontage", "to": "runtime"}, {"from": "runtime", "to": "vfs"}],
            {"carrier": "R22", "observer": "UNREAD"},
        )
        assert svg.effect["node_count"] == 3

        rt.research.register_case_study(
            "research://casepath/service-readiness",
            "undertaking://casepath",
            [{"claim": "service workflow is addressable", "state": "VERIFIED"}],
            [{"source": "BRAINK repository", "type": "resident-code"}],
            {"replayable": True, "independent_promotion": False},
        )
        rt.agentics.dispatch(
            "task://casepath/review-publication",
            "undertaking://casepath",
            "team://casepath/core",
            {"instruction": "Review staged release against proof and frontage contracts", "acceptance": ["artifact roots exist", "approval exists"]},
            "PUBLISHING_MASTERY_FOUNDARY",
        )
        rt.software.register_product(
            "software://casepath/runtime",
            "undertaking://casepath",
            ["deployment/braink_runtime_service.py"],
            ["scripts/kex-ci/test_foundry_operations_r22.py"],
            {"container": "deployment/Dockerfile", "systemd": "deployment/braink-runtime.service"},
            {"health": "/health", "state": "/state"},
        )
        rel = rt.publishing.stage_release(
            "release://casepath/r22-demo",
            "undertaking://casepath",
            ["vfs://casepath/pages/your-data", "landing://casepath/main", "svg://casepath/runtime-map"],
            "frontage://casepath/public",
            [{"authority": "team://casepath/core", "decision": "APPROVE_INTERNAL_STAGE"}],
        )
        assert rel.effect["state"] == "STAGED_INTERNAL"

        summary = rt.process.process_summary()
        assert summary["receipt_count"] == 20
        before_root = summary["state_root"]

        rt2 = FoundaryOperationsRuntime(state)
        assert rt2.process.process_summary()["state_root"] == before_root
        assert "undertaking://casepath" in rt2.store.state["undertakings"]
        assert "release://casepath/r22-demo" in rt2.store.state["publications"]
        restored_customer = rt2.store.state["customers"][customer]
        assert restored_customer["state"] == "CLOSED"
        assert restored_customer["revision"] == 7
        assert len(restored_customer["documents"]) == 1
        assert len(restored_customer["communications"]) == 1
        assert len(restored_customer["billing"]) == 1
        assert len(restored_customer["exports"]) == 1

        print("R22_FOUNDRY_OPERATIONS_PASS")
        print("R22_CUSTOMER_FILE_LIFECYCLE_PASS")
        print(f"state_root={before_root}")
        print(f"receipt_count={summary['receipt_count']}")


if __name__ == "__main__":
    run()
