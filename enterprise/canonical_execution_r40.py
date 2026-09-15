from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import hashlib
import json

from enterprise.capability_deployment_runtime import CapabilityDeploymentRuntime
from enterprise.data_class_registry_r40 import DataClassRegistry
from enterprise.global_illlm_r40 import VersionedGlobalKnowledge
from enterprise.illlm_authority import ILLLMAuthority
from enterprise.market_services.service_broker import MarketServiceBroker
from enterprise.node_vfs_r40 import NodeVFS
from enterprise.runtime.resource_scheduler_r40 import PhysicalResourceScheduler, ResourceRequirement, ResourceVector


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _vector(body: dict[str, Any]) -> ResourceVector:
    return ResourceVector(
        cpu_units=int(body.get("cpu_units", 0)), memory_bytes=int(body.get("memory_bytes", 0)),
        storage_bytes=int(body.get("storage_bytes", 0)), gpu_units=int(body.get("gpu_units", 0)),
        network_mbps=int(body.get("network_mbps", 0)),
    )


def resource_requirement(body: dict[str, Any]) -> ResourceRequirement:
    if not isinstance(body, dict):
        raise ValueError("RESOURCE_REQUIREMENT_REQUIRED")
    return ResourceRequirement(
        minimum=_vector(body.get("minimum", {})), target=_vector(body.get("target", {})), maximum=_vector(body.get("maximum", {})),
        priority=int(body.get("priority", 50)), latency_class=str(body.get("latency_class", "STANDARD")),
        persistence_required=bool(body.get("persistence_required", True)),
    )


def _collect_authority_ids(packet: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            identifier = value.get("id")
            if isinstance(identifier, str) and (identifier.startswith("authority://") or identifier.startswith("runtime://")):
                out.add(identifier)
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(packet)
    return out


class CanonicalExecutionR40:
    """Thin coordinator. Resident BRAINK/KEX components retain their own mutation authority."""

    REQUIRED_ACTIVE_PROMOTION = (
        "CLASSIFIED", "VALIDATED", "MATERIALIZED", "AGENT_BOUND", "VFS_BOUND", "NETWORK_BOUND",
        "RUNTIME_CONSTRUCTED", "RUNTIME_RUNNING", "LOCAL_VERIFIED", "MESH_REGISTERED",
        "SERVER_REGISTERED", "SUBSCRIBED", "IL_LLM_REGISTERED",
    )

    def __init__(self, runtime_host: Any, state_root: str | Path, fabric_admission: Any | None = None):
        self.host = runtime_host
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.data_classes = DataClassRegistry()
        self.illlm = ILLLMAuthority(self.state_root / "control" / "illlm-execution-ledger-r40.json")
        self.global_knowledge = VersionedGlobalKnowledge(self.state_root / "control" / "global-illlm-r40.json")
        self.scheduler = PhysicalResourceScheduler.probe_host(self.state_root)
        self.fabric_admission = fabric_admission
        repo_root = Path(__file__).resolve().parents[1]
        catalog = json.loads((repo_root / "enterprise" / "SERVICE_GENOME_CATALOG_R16.json").read_text(encoding="utf-8"))
        bindings = json.loads((repo_root / "enterprise" / "R18_CAPABILITY_BINDINGS.json").read_text(encoding="utf-8"))
        self.capability_runtime = CapabilityDeploymentRuntime(catalog, bindings)
        self.authority_control = json.loads((repo_root / "control" / "AUTHORITY_CONTROL_R34.json").read_text(encoding="utf-8"))
        self.authority_ids = _collect_authority_ids(self.authority_control)
        self.operator_ledger_path = self.state_root / "control" / "canonical-operator-authority-r40.sqlite"
        self.operator_ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _block(self, reason: str, stages: list[str], detail: Any = None, promotion: list[str] | None = None) -> dict[str, Any]:
        out = {"status": f"BLOCKED:{reason}", "stages": stages, "promotion": list(promotion or [])}
        if detail is not None: out["detail"] = detail
        return out

    @staticmethod
    def _ledger_reference(node: Any) -> str:
        events = getattr(node.ledger, "events", ())
        return events[-1].event_id if events else "ledger://empty"

    def register_operator(self, agent_id: str, scope: str = "CANONICAL_EXECUTION") -> dict[str, Any]:
        broker = MarketServiceBroker(self.operator_ledger_path)
        return broker.execute("agent_control", "register_agent", {"agent_id": str(agent_id), "scope": str(scope)}, authority_scope="CANONICAL_EXECUTION")

    def _authorize_operator(self, operator: Any) -> dict[str, Any]:
        if operator is None:
            return {"status": "AUTHORITY_SCOPE_ONLY", "decision": "ALLOW"}
        if not isinstance(operator, dict) or not operator.get("agent_id"):
            return {"status": "REJECTED", "reason": "OPERATOR_AGENT_ID_REQUIRED"}
        payload = {
            "agent_id": str(operator["agent_id"]),
            "required_scope": str(operator.get("required_scope", "CANONICAL_EXECUTION")),
        }
        if operator.get("expected_epoch") is not None:
            payload["expected_epoch"] = int(operator["expected_epoch"])
        broker = MarketServiceBroker(self.operator_ledger_path)
        receipt = broker.execute("agent_control", "authorize_action", payload, authority_scope="CANONICAL_EXECUTION")
        result = receipt.get("result", {})
        return {"status": receipt.get("status"), "decision": result.get("decision", "DENY"), "receipt": receipt}

    def _resolve_capabilities(self, command: dict[str, Any], stages: list[str], promotion: list[str]) -> tuple[list[str] | None, dict[str, Any] | None]:
        capabilities = sorted(set(str(x).strip() for x in command.get("capabilities", []) if str(x).strip()))
        resolution = self.capability_runtime.resolve_many(capabilities)
        if resolution["status"] == "CAPABILITY_MANIFEST_REQUIRED":
            return None, self._block("CAPABILITY_MANIFEST_REQUIRED", stages, resolution, promotion)
        if resolution["status"] != "RESOLVED":
            first = resolution["blocked"][0]
            reason = first["status"] + ":" + first.get("capability", first.get("name", "UNKNOWN"))
            return None, self._block(reason, stages, resolution, promotion)
        return capabilities, None

    def _duplicate_correction(self, node: Any, command_root: str) -> dict[str, Any] | None:
        receipts = node.readback().get("memory", {}).get("canonical_correction_receipts", {})
        receipt = receipts.get(command_root) if isinstance(receipts, dict) else None
        if receipt is None: return None
        return {"status": "DUPLICATE_CORRECTION", "command_root": command_root, "receipt": receipt, "readback": self.host.snapshot(node)}

    def _record_correction(self, node: Any, command_root: str, classified: Any, execution_result: Any) -> None:
        lineage = "/".join(node.identity.lineage)
        memory = node.readback().get("memory", {})
        receipts = dict(memory.get("canonical_correction_receipts", {}))
        receipts[command_root] = {
            "command_root": command_root,
            "data_id": classified.data_id,
            "result_root": root(execution_result),
            "ledger_reference_before_receipt": self._ledger_reference(node),
        }
        self.host.write_memory(lineage, "canonical_correction_receipts", receipts)

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(command, dict): return self._block("MALFORMED_COMMAND", [])
        stages = ["INGESTED", "MEMORY_IN_MOMENT"]
        promotion: list[str] = []
        command_root = root(command)
        observation = {"command_root": command_root, "source": command.get("source")}

        try:
            classified = self.data_classes.classify(
                source=command.get("source", ""), data_class=command.get("data_class", ""), payload=command.get("payload", {}),
                schema_version=command.get("schema_version", "1"), sector=command.get("sector"),
            )
        except Exception as exc:
            return self._block("DATA_CLASS", stages, str(exc), promotion)
        stages += ["CLASSIFIED", "SCHEMA_VALIDATED"]
        promotion.append("CLASSIFIED")

        authority = str(command.get("authority", "")).strip()
        if authority not in self.authority_ids:
            return self._block("AUTHORITY_UNRESOLVED:" + (authority or "MISSING"), stages, {"allowed": sorted(self.authority_ids)}, promotion)
        stages.append("AUTHORITY_VALIDATED")

        illlm_request = command.get("illlm")
        if not isinstance(illlm_request, dict): return self._block("IL_LLM_REQUEST", stages, promotion=promotion)
        try:
            normalized, binding = self.illlm.resolve(illlm_request)
        except Exception as exc:
            return self._block("IL_LLM_RESOLUTION", stages, str(exc), promotion)
        stages += ["IL_LLM_RESOLVED", "LOGICAL_IDENTITY_RESOLVED"]

        try:
            target_node = self.host.resolve(normalized["lineage"]); target_exists = True
        except Exception:
            target_node = None; target_exists = False

        operator_authority = self._authorize_operator(command.get("operator"))
        if operator_authority.get("decision") != "ALLOW":
            return self._block("BRAINK_OPERATOR_AUTHORITY", stages, operator_authority, promotion)
        stages.append("BRAINK_OPERATOR_AUTHORIZED")

        capabilities, capability_block = self._resolve_capabilities(command, stages, promotion)
        if capability_block is not None: return capability_block
        stages.append("CAPABILITIES_RESOLVED")
        promotion.append("VALIDATED")

        if classified.data_class == "CORRECTION" and target_exists:
            duplicate = self._duplicate_correction(target_node, command_root)
            if duplicate is not None:
                duplicate["stages"] = stages + ["EXISTING_NODE_RESOLVED", "FIXED_POINT", "QUIESCED"]
                duplicate["promotion"] = promotion
                return duplicate

        envelope = None; node_created = False; vfs_root = None; runtime_snapshot = None
        network_id: str | None = None

        if binding.intent == "computer.instantiate":
            if not classified.node_eligible:
                return self._block("DATA_CLASS_NOT_NODE_ELIGIBLE", stages, classified.to_dict(), promotion)
            try: self.host.resolve(normalized["lineage"])
            except Exception as exc: return self._block("PARENT_NODE_RESOLUTION", stages, str(exc), promotion)
            child_id = normalized["child_id"]
            child_lineage = normalized["lineage"].rstrip("/") + "/" + child_id
            try:
                existing = self.host.resolve(child_lineage)
                return {"status": "ROUTED_EXISTING_NODE", "stages": stages + ["EXISTING_NODE_RESOLVED", "FIXED_POINT", "QUIESCED"],
                        "promotion": promotion, "data_class": classified.to_dict(), "node": self.host.snapshot(existing), "observation": observation}
            except Exception: pass
            try:
                envelope = self.scheduler.allocate(child_id, resource_requirement(command.get("resources")))
            except Exception as exc:
                return self._block("RESOURCE_SCHEDULER", stages, str(exc), promotion)
            stages.append("RESOURCE_ENVELOPE_GRANTED")
            try:
                result = self.illlm.execute(illlm_request, self.host)
            except Exception as exc:
                self.scheduler.release(child_id)
                return self._block("RUNTIME_EXECUTION", stages, str(exc), promotion)
            node_created = True
            target_node = self.host.resolve(child_lineage)
            stages += ["NODE_MATERIALIZED", "RUNTIME_EXECUTED"]
            promotion.append("MATERIALIZED")

            agent_id = f"agent://braink/{classified.data_class.lower()}/{child_id}"
            self.host.write_memory(child_lineage, "braink_agent", {"agent_id": agent_id, "authority": authority, "sector": classified.sector})
            self.host.write_memory(child_lineage, "resource_envelope", envelope.to_dict())
            self.host.write_memory(child_lineage, "data_class", classified.to_dict())
            stages += ["BRAINK_AGENT_BOUND", "NODE_MEMORY_BOUND"]
            promotion.append("AGENT_BOUND")

            vfs = NodeVFS(target_node.runtime, target_node.state_root / "node-vfs")
            identity_write = vfs.write(child_id, "identity.json", {
                "node_id": child_id, "logical_identity": classified.logical_identity,
                "agent_id": agent_id, "resource_envelope": envelope.to_dict(),
            })
            vfs_root = identity_write["logical"].rsplit("/", 1)[0]
            stages.append("NODE_VFS_BOUND")
            promotion.append("VFS_BOUND")

            network_id = str(command.get("network_id", f"network://local/{child_id}"))
            self.host.write_memory(child_lineage, "network_identity", {"network_id": network_id, "authority": authority})
            network_check = self.host.snapshot(target_node)["memory"].get("network_identity", {}).get("network_id")
            if network_check != network_id:
                return self._block("NETWORK_IDENTITY_READBACK", stages, promotion=promotion)
            stages.append("NETWORK_BOUND")
            promotion.append("NETWORK_BOUND")

            if getattr(target_node, "runtime", None) is None:
                return self._block("RUNTIME_CONSTRUCTION", stages, promotion=promotion)
            promotion.append("RUNTIME_CONSTRUCTED")
            runtime_snapshot = target_node.runtime.snapshot()
            if not isinstance(runtime_snapshot, dict):
                return self._block("RUNTIME_LAUNCH_READBACK", stages, promotion=promotion)
            stages.append("RUNTIME_RUNNING")
            promotion.append("RUNTIME_RUNNING")
        else:
            if not target_exists: return self._block("EXISTING_NODE_REQUIRED", stages, normalized["lineage"], promotion)
            if not classified.execution_eligible and binding.mutating:
                return self._block("DATA_CLASS_NOT_EXECUTION_ELIGIBLE", stages, classified.to_dict(), promotion)
            try:
                result = self.illlm.execute(illlm_request, self.host)
            except Exception as exc:
                return self._block("RUNTIME_EXECUTION", stages, str(exc), promotion)
            stages += ["EXISTING_NODE_RESOLVED", "RUNTIME_EXECUTED"]

        post = self.host.snapshot(target_node)
        if not post.get("ledger_verified"):
            return self._block("LOCAL_LEDGER_VERIFICATION", stages, promotion=promotion)
        stages += ["READBACK", "LOCAL_VERIFIED", "LEDGER_PROOF_BOUND"]
        if node_created: promotion.append("LOCAL_VERIFIED")
        ledger_ref = self._ledger_reference(target_node)
        node_id = target_node.identity.computer_id
        network_id = network_id or str(command.get("network_id", f"network://local/{node_id}"))

        mesh_result = None; server_result = None; subscription_result = None
        if self.fabric_admission is not None:
            identity_body = {
                "node_id": node_id, "lineage": list(target_node.identity.lineage), "state_root": post["state_root"],
                "network_id": network_id, "vfs_root": vfs_root or f"vfs://node/{node_id}", "ledger_reference": ledger_ref,
            }
            identity_proof = {"body": identity_body, "proof": root(identity_body)}
            mesh_result = self.fabric_admission.register_local_node(
                node_id=node_id, lineage=list(target_node.identity.lineage), state_root=post["state_root"], capabilities=capabilities or [],
                authority=authority, network_id=network_id, vfs_root=vfs_root or f"vfs://node/{node_id}",
                local_verified=True, reachable=True, identity_proof=identity_proof,
            )
            if mesh_result.get("status") == "MESH_REGISTERED":
                stages.append("MESH_REGISTERED")
                if node_created: promotion.append("MESH_REGISTERED")
            elif node_created:
                return self._block(mesh_result.get("status", "MESH_ADMISSION_FAILURE").removeprefix("BLOCKED:"), stages, mesh_result, promotion)

            if command.get("server_registration"):
                server_result = self.fabric_admission.register_server(command["server_registration"])
                if server_result.get("status") == "SERVER_REGISTERED":
                    stages.append("SERVER_REGISTERED")
                    if node_created: promotion.append("SERVER_REGISTERED")
                elif node_created:
                    return self._block(server_result.get("status", "SERVER_REGISTRATION_FAILURE").removeprefix("BLOCKED:"), stages, server_result, promotion)
            elif node_created:
                return self._block("SERVER_REGISTRATION_REQUIRED", stages, promotion=promotion)

            topics = command.get("subscriptions", [])
            if topics:
                subscription_result = self.fabric_admission.subscribe_node(node_id, topics)
                self.global_knowledge.subscribe(node_id, topics)
                if subscription_result.get("status") == "SUBSCRIBED":
                    stages.append("SUBSCRIBED")
                    if node_created: promotion.append("SUBSCRIBED")
                elif node_created:
                    return self._block("SUBSCRIPTION_FAILURE", stages, subscription_result, promotion)
            elif node_created:
                return self._block("SUBSCRIPTIONS_REQUIRED", stages, promotion=promotion)
        elif node_created:
            return self._block("MESH_ADMISSION_AUTHORITY_NOT_BOUND", stages, promotion=promotion)
        else:
            mesh_result = {"status": "BLOCKED:MESH_ADMISSION_AUTHORITY_NOT_BOUND"}

        global_result = None
        if command.get("global_delta") is not None:
            delta = command["global_delta"]; snap = self.global_knowledge.snapshot()
            try:
                global_result = self.global_knowledge.apply_delta(
                    source_node=node_id, source_event=ledger_ref, data_class=classified.data_class,
                    previous_version=int(delta.get("previous_version", snap["version"])), relation_delta=delta.get("relation_delta", {}),
                    provenance={"data_id": classified.data_id, "command_root": observation["command_root"]}, authority=authority,
                    validation={"status": "VALIDATED", "local_ledger_verified": True}, ledger_reference=ledger_ref,
                )
            except Exception as exc:
                return self._block("GLOBAL_IL_LLM_DELTA", stages, str(exc), promotion)
            self.host.write_memory("/".join(target_node.identity.lineage), "global_illlm_version", global_result["version"])
            check = self.host.snapshot(target_node)["memory"].get("global_illlm_version")
            if check != global_result["version"]:
                return self._block("GLOBAL_VERSION_READBACK", stages, promotion=promotion)
            stages += ["GLOBAL_IL_LLM_REGISTERED", "SUBSCRIBER_RESOLUTION"]
            if node_created: promotion.append("IL_LLM_REGISTERED")
        elif node_created:
            return self._block("IL_LLM_DELTA_REQUIRED_FOR_ACTIVE_PROMOTION", stages, promotion=promotion)

        if classified.data_class == "CORRECTION":
            self._record_correction(target_node, command_root, classified, result)
            stages.append("CORRECTION_RECEIPT_BOUND")

        active = node_created and tuple(promotion) == self.REQUIRED_ACTIVE_PROMOTION
        if active:
            promotion.append("ACTIVE")
            stages.append("ACTIVE")
        changed = bool(binding.mutating or node_created or global_result or server_result or subscription_result or (mesh_result and mesh_result.get("status") == "MESH_REGISTERED"))
        stages.append("CONTINUE" if changed else "FIXED_POINT")
        if not changed: stages.append("QUIESCED")
        final_readback = self.host.snapshot(target_node)
        ledger_ref = self._ledger_reference(target_node)
        distributed_ok = bool(mesh_result and mesh_result.get("status") == "MESH_REGISTERED")
        status = "ACTIVE" if active else ("EXECUTED_DISTRIBUTED_REGISTERED" if distributed_ok else "EXECUTED_LOCAL_VERIFIED")
        return {
            "status": status, "stages": stages, "promotion": promotion, "observation": observation,
            "data_class": classified.to_dict(), "operator_authority": operator_authority,
            "capability_resolution": self.capability_runtime.resolve_many(capabilities or []),
            "il_llm": {"normalized": normalized, "binding": asdict(binding)}, "result": result,
            "readback": final_readback, "runtime_readback": runtime_snapshot, "ledger_reference": ledger_ref,
            "global_delta": global_result, "mesh_state": mesh_result,
            "server_state": server_result or {"status": "BLOCKED:SERVER_REGISTRATION_NOT_REQUESTED"},
            "subscription_state": subscription_result or {"status": "BLOCKED:SUBSCRIPTIONS_NOT_REQUESTED"},
            "resource_envelope": None if envelope is None else envelope.to_dict(), "fixed_point": not changed,
        }
