from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping, Optional
import hashlib
import json
import os
import tempfile
import time
import uuid


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_root(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class OperationReceipt:
    foundary: str
    operation: str
    subject: str
    status: str
    generation: int
    effect: Mapping[str, Any]
    predecessor_root: Optional[str]
    produced_at_ns: int

    @property
    def receipt_root(self) -> str:
        return content_root(asdict(self))


class PersistentFoundaryStore:
    """Single-node durable state carrier for R22 foundary operations.

    This is intentionally a local durability mechanism. It does not claim distributed
    consensus or multi-host replication.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.state = json.loads(self.path.read_text("utf-8"))
        else:
            self.state = {
                "schema": "braink.foundary-operations-state.r22/v1",
                "generation": 0,
                "undertakings": {},
                "teams": {},
                "server_rooms": {},
                "workspaces": {},
                "files": {},
                "customers": {},
                "frontages": {},
                "domains": {},
                "publications": {},
                "research": {},
                "agent_tasks": {},
                "software_products": {},
                "hci_surfaces": {},
                "landing_pages": {},
                "svg_assets": {},
                "receipts": [],
            }

    def commit(self, foundary: str, operation: str, subject: str, mutate) -> OperationReceipt:
        predecessor = self.state.get("state_root")
        next_state = json.loads(json.dumps(self.state))
        effect = dict(mutate(next_state) or {})
        next_state["generation"] += 1
        receipt = OperationReceipt(
            foundary=foundary,
            operation=operation,
            subject=subject,
            status="COMMITTED",
            generation=next_state["generation"],
            effect=effect,
            predecessor_root=predecessor,
            produced_at_ns=time.time_ns(),
        )
        next_state["receipts"].append({**asdict(receipt), "receipt_root": receipt.receipt_root})
        next_state["state_root"] = content_root({k: v for k, v in next_state.items() if k != "state_root"})
        encoded = canonical(next_state)
        with tempfile.NamedTemporaryFile("wb", dir=self.path.parent, delete=False, prefix=".braink-r22-", suffix=".tmp") as f:
            tmp = Path(f.name)
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        dfd = os.open(str(self.path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        self.state = next_state
        return receipt


class BusinessEnterpriseStructureFoundary:
    NAME = "BUSINESS_AND_ENTERPRISE_STRUCTURE_FOUNDARY"
    def __init__(self, store): self.store = store
    def create_undertaking(self, undertaking_id: str, purpose: str, service_genomes: list[str], business_units: list[str], market_targets: list[str]):
        def mutate(s):
            obj = {"undertaking_id": undertaking_id, "purpose": purpose, "service_genomes": service_genomes, "business_units": business_units, "market_targets": market_targets, "state": "ACTIVE"}
            s["undertakings"][undertaking_id] = obj
            return obj
        return self.store.commit(self.NAME, "CREATE_UNDERTAKING", undertaking_id, mutate)


class HRAndAllTeamServicesFoundary:
    NAME = "HR_AND_ALL_TEAM_SERVICES_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_team(self, team_id: str, undertaking_id: str, roles: list[str], capabilities: list[str], authority_roots: list[str]):
        if undertaking_id not in self.store.state["undertakings"]:
            raise KeyError("UNDERTAKING_NOT_FOUND")
        def mutate(s):
            obj = {"team_id": team_id, "undertaking_id": undertaking_id, "roles": roles, "capabilities": capabilities, "authority_roots": authority_roots, "members": [], "state": "ACTIVE"}
            s["teams"][team_id] = obj
            return obj
        return self.store.commit(self.NAME, "REGISTER_TEAM", team_id, mutate)


class ServerFoundary:
    NAME = "SERVER_FOUNDARY"
    def __init__(self, store): self.store = store
    def materialize_room(self, room_id: str, undertaking_id: str, server_sets: Mapping[str, int], dependencies: Mapping[str, list[str]]):
        if undertaking_id not in self.store.state["undertakings"]:
            raise KeyError("UNDERTAKING_NOT_FOUND")
        def mutate(s):
            instances = []
            for server_class, replicas in sorted(server_sets.items()):
                for ordinal in range(1, int(replicas) + 1):
                    instances.append({"server_id": f"server://{room_id}/{server_class}/{ordinal}", "class": server_class, "ordinal": ordinal, "state": "MATERIALIZED"})
            obj = {"room_id": room_id, "undertaking_id": undertaking_id, "server_sets": dict(server_sets), "dependencies": dict(dependencies), "instances": instances, "topology_root": content_root({"server_sets": server_sets, "dependencies": dependencies})}
            s["server_rooms"][room_id] = obj
            return {"room_id": room_id, "instance_count": len(instances), "topology_root": obj["topology_root"]}
        return self.store.commit(self.NAME, "MATERIALIZE_AI_SERVER_ROOM", room_id, mutate)


class WorkspaceFoundary:
    NAME = "WORKSPACE_FOUNDARY"
    def __init__(self, store): self.store = store
    def create(self, workspace_id: str, undertaking_id: str, owner_team: str):
        if owner_team not in self.store.state["teams"]: raise KeyError("TEAM_NOT_FOUND")
        def mutate(s):
            obj = {"workspace_id": workspace_id, "undertaking_id": undertaking_id, "owner_team": owner_team, "tasks": [], "artifacts": [], "sessions": [], "state": "ACTIVE"}
            s["workspaces"][workspace_id] = obj
            return obj
        return self.store.commit(self.NAME, "CREATE_WORKSPACE", workspace_id, mutate)


class FileSystemFoundary:
    NAME = "FILE_SYSTEM_FOUNDARY"
    def __init__(self, store): self.store = store
    def write(self, address: str, payload: Mapping[str, Any], workspace_id: Optional[str] = None):
        prior = self.store.state["files"].get(address)
        prior_root = prior.get("object_root") if prior else None
        def mutate(s):
            generation = (prior.get("generation", 0) if prior else 0) + 1
            obj = {"address": address, "generation": generation, "payload": dict(payload), "workspace_id": workspace_id, "predecessor_root": prior_root}
            obj["object_root"] = content_root(obj)
            s["files"][address] = obj
            if workspace_id and workspace_id in s["workspaces"] and address not in s["workspaces"][workspace_id]["artifacts"]:
                s["workspaces"][workspace_id]["artifacts"].append(address)
            return {"address": address, "generation": generation, "object_root": obj["object_root"]}
        return self.store.commit(self.NAME, "WRITE_FILE_OBJECT", address, mutate)


class CustomerFileBaseSoftwareFoundary:
    NAME = "CUSTOMER_FILE_BASE_SOFTWARE_FOUNDARY"
    def __init__(self, store): self.store = store
    def create_customer_file(self, customer_id: str, undertaking_id: str, consent: Mapping[str, Any], service_state: Mapping[str, Any]):
        def mutate(s):
            obj = {"customer_id": customer_id, "undertaking_id": undertaking_id, "consent": dict(consent), "service_state": dict(service_state), "documents": [], "communications": [], "billing": [], "audit": [], "state": "ACTIVE"}
            s["customers"][customer_id] = obj
            return {"customer_id": customer_id, "state": "ACTIVE"}
        return self.store.commit(self.NAME, "CREATE_CUSTOMER_FILE", customer_id, mutate)


class FrontagesServicesGrowingMeshWebsitesDomainMasteryFoundary:
    NAME = "FRONTAGES_SERVICES_GROWING_MESH_WEBSITES_DOMAIN_MASTERY_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_frontage(self, frontage_id: str, undertaking_id: str, hostname: str, routes: Mapping[str, str], mesh_targets: list[str]):
        def mutate(s):
            obj = {"frontage_id": frontage_id, "undertaking_id": undertaking_id, "hostname": hostname, "routes": dict(routes), "mesh_targets": list(mesh_targets), "publication_state": "INTERNAL_BOUND", "observer_state": "UNREAD"}
            s["frontages"][frontage_id] = obj
            s["domains"].setdefault(hostname, {"hostname": hostname, "ownership_state": "DECLARED", "dns_state": "UNBOUND", "tls_state": "UNBOUND", "frontages": []})["frontages"].append(frontage_id)
            return {"frontage_id": frontage_id, "hostname": hostname, "route_root": content_root(routes)}
        return self.store.commit(self.NAME, "REGISTER_FRONTAGE", frontage_id, mutate)


class HCIFoundary:
    NAME = "HCI_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_surface(self, surface_id: str, undertaking_id: str, controls: list[Mapping[str, Any]], accessibility_contract: Mapping[str, Any]):
        def mutate(s):
            obj = {"surface_id": surface_id, "undertaking_id": undertaking_id, "controls": list(controls), "accessibility_contract": dict(accessibility_contract), "control_root": content_root(controls)}
            s["hci_surfaces"][surface_id] = obj
            return {"surface_id": surface_id, "control_count": len(controls), "control_root": obj["control_root"]}
        return self.store.commit(self.NAME, "REGISTER_HCI_SURFACE", surface_id, mutate)


class LandingPageFoundary:
    NAME = "LANDING_PAGE_FOUNDARY"
    def __init__(self, store): self.store = store
    def manufacture(self, page_id: str, undertaking_id: str, frontage_id: str, proposition: str, sections: list[Mapping[str, Any]], conversion_actions: list[str]):
        if frontage_id not in self.store.state["frontages"]: raise KeyError("FRONTAGE_NOT_FOUND")
        def mutate(s):
            obj = {"page_id": page_id, "undertaking_id": undertaking_id, "frontage_id": frontage_id, "proposition": proposition, "sections": list(sections), "conversion_actions": list(conversion_actions), "release_state": "MANUFACTURED", "page_root": content_root({"proposition": proposition, "sections": sections, "conversion_actions": conversion_actions})}
            s["landing_pages"][page_id] = obj
            return {"page_id": page_id, "page_root": obj["page_root"]}
        return self.store.commit(self.NAME, "MANUFACTURE_LANDING_PAGE", page_id, mutate)


class SVGFoundary:
    NAME = "SVG_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_svg(self, svg_id: str, undertaking_id: str, graph_nodes: list[Mapping[str, Any]], graph_edges: list[Mapping[str, Any]], metadata: Mapping[str, Any]):
        def mutate(s):
            obj = {"svg_id": svg_id, "undertaking_id": undertaking_id, "graph_nodes": list(graph_nodes), "graph_edges": list(graph_edges), "metadata": dict(metadata)}
            obj["carrier_root"] = content_root(obj)
            s["svg_assets"][svg_id] = obj
            return {"svg_id": svg_id, "carrier_root": obj["carrier_root"], "node_count": len(graph_nodes), "edge_count": len(graph_edges)}
        return self.store.commit(self.NAME, "REGISTER_SVG_RUNTIME_CARRIER", svg_id, mutate)


class ResearchMasteryFoundary:
    NAME = "RESEARCH_MASTERY_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_case_study(self, research_id: str, undertaking_id: str, claims: list[Mapping[str, Any]], sources: list[Mapping[str, Any]], reproducibility: Mapping[str, Any]):
        def mutate(s):
            obj = {"research_id": research_id, "undertaking_id": undertaking_id, "claims": list(claims), "sources": list(sources), "reproducibility": dict(reproducibility), "evidence_root": content_root({"claims": claims, "sources": sources, "reproducibility": reproducibility}), "promotion_state": "REVIEW_REQUIRED"}
            s["research"][research_id] = obj
            return {"research_id": research_id, "evidence_root": obj["evidence_root"], "promotion_state": obj["promotion_state"]}
        return self.store.commit(self.NAME, "REGISTER_CASE_STUDY", research_id, mutate)


class AgenticsFoundary:
    NAME = "AGENTICS_FOUNDARY"
    def __init__(self, store): self.store = store
    def dispatch(self, task_id: str, undertaking_id: str, team_id: str, work_module: Mapping[str, Any], target_foundary: str):
        if team_id not in self.store.state["teams"]: raise KeyError("TEAM_NOT_FOUND")
        def mutate(s):
            obj = {"task_id": task_id, "undertaking_id": undertaking_id, "team_id": team_id, "target_foundary": target_foundary, "work_module": dict(work_module), "state": "DISPATCHED", "work_root": content_root(work_module)}
            s["agent_tasks"][task_id] = obj
            if undertaking_id in s["undertakings"]:
                s["undertakings"][undertaking_id].setdefault("agent_tasks", []).append(task_id)
            return {"task_id": task_id, "state": "DISPATCHED", "work_root": obj["work_root"]}
        return self.store.commit(self.NAME, "DISPATCH_WORK_MODULE", task_id, mutate)


class RealActualUseableSoftwareFoundary:
    NAME = "REAL_ACTUAL_USEABLE_SOFTWARE_FOUNDARY"
    def __init__(self, store): self.store = store
    def register_product(self, product_id: str, undertaking_id: str, entrypoints: list[str], tests: list[str], packaging: Mapping[str, Any], runtime_contract: Mapping[str, Any]):
        def mutate(s):
            obj = {"product_id": product_id, "undertaking_id": undertaking_id, "entrypoints": list(entrypoints), "tests": list(tests), "packaging": dict(packaging), "runtime_contract": dict(runtime_contract), "qualification_state": "IMPLEMENTED" if tests else "INCOMPLETE"}
            obj["product_root"] = content_root(obj)
            s["software_products"][product_id] = obj
            return {"product_id": product_id, "qualification_state": obj["qualification_state"], "product_root": obj["product_root"]}
        return self.store.commit(self.NAME, "REGISTER_SOFTWARE_PRODUCT", product_id, mutate)


class PublishingMasteryFoundary:
    NAME = "PUBLISHING_MASTERY_FOUNDARY"
    def __init__(self, store): self.store = store
    def stage_release(self, release_id: str, undertaking_id: str, artifacts: list[str], frontage_id: str, approvals: list[Mapping[str, Any]]):
        missing = [a for a in artifacts if a not in self.store.state["files"] and a not in self.store.state["landing_pages"] and a not in self.store.state["svg_assets"]]
        if missing: raise KeyError(f"ARTIFACTS_NOT_FOUND:{missing}")
        if frontage_id not in self.store.state["frontages"]: raise KeyError("FRONTAGE_NOT_FOUND")
        def mutate(s):
            obj = {"release_id": release_id, "undertaking_id": undertaking_id, "artifacts": list(artifacts), "frontage_id": frontage_id, "approvals": list(approvals), "state": "STAGED_INTERNAL", "release_root": content_root({"artifacts": artifacts, "frontage_id": frontage_id, "approvals": approvals})}
            s["publications"][release_id] = obj
            return {"release_id": release_id, "state": "STAGED_INTERNAL", "release_root": obj["release_root"]}
        return self.store.commit(self.NAME, "STAGE_RELEASE", release_id, mutate)


class ProcessMasteryFoundary:
    NAME = "PROCESS_MASTERY_FOUNDARY"
    def __init__(self, store): self.store = store
    def process_summary(self) -> Mapping[str, Any]:
        return {
            "generation": self.store.state["generation"],
            "state_root": self.store.state.get("state_root"),
            "receipt_count": len(self.store.state["receipts"]),
            "active_objects": {k: len(v) for k, v in self.store.state.items() if isinstance(v, dict) and k not in {"schema"}},
        }


class FoundaryOperationsRuntime:
    def __init__(self, state_path: str | Path):
        self.store = PersistentFoundaryStore(state_path)
        self.business = BusinessEnterpriseStructureFoundary(self.store)
        self.hr = HRAndAllTeamServicesFoundary(self.store)
        self.servers = ServerFoundary(self.store)
        self.workspace = WorkspaceFoundary(self.store)
        self.files = FileSystemFoundary(self.store)
        self.customers = CustomerFileBaseSoftwareFoundary(self.store)
        self.frontages = FrontagesServicesGrowingMeshWebsitesDomainMasteryFoundary(self.store)
        self.hci = HCIFoundary(self.store)
        self.landing = LandingPageFoundary(self.store)
        self.svg = SVGFoundary(self.store)
        self.research = ResearchMasteryFoundary(self.store)
        self.agentics = AgenticsFoundary(self.store)
        self.software = RealActualUseableSoftwareFoundary(self.store)
        self.publishing = PublishingMasteryFoundary(self.store)
        self.process = ProcessMasteryFoundary(self.store)
