from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import hashlib
import json

from enterprise.data_class_registry_r40 import DataClassRegistry
from enterprise.global_illlm_r40 import VersionedGlobalKnowledge
from enterprise.illlm_authority import ILLLMAuthority
from enterprise.node_vfs_r40 import NodeVFS
from enterprise.runtime.resource_scheduler_r40 import PhysicalResourceScheduler, ResourceRequirement, ResourceVector


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def root(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _vector(body: dict[str, Any]) -> ResourceVector:
    return ResourceVector(
        cpu_units=int(body.get("cpu_units", 0)),
        memory_bytes=int(body.get("memory_bytes", 0)),
        storage_bytes=int(body.get("storage_bytes", 0)),
        gpu_units=int(body.get("gpu_units", 0)),
        network_mbps=int(body.get("network_mbps", 0)),
    )


def resource_requirement(body: dict[str, Any]) -> ResourceRequirement:
    if not isinstance(body, dict):
        raise ValueError("RESOURCE_REQUIREMENT_REQUIRED")
    return ResourceRequirement(
        minimum=_vector(body.get("minimum", {})),
        target=_vector(body.get("target", {})),
        maximum=_vector(body.get("maximum", {})),
        priority=int(body.get("priority", 50)),
        latency_class=str(body.get("latency_class", "STANDARD")),
        persistence_required=bool(body.get("persistence_required", True)),
    )


class CanonicalExecutionR40:
    """Coordinator only: resident components retain mutation authority."""

    def __init__(self, runtime_host: Any, state_root: str | Path):
        self.host = runtime_host
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.data_classes = DataClassRegistry()
        self.illlm = ILLLMAuthority(self.state_root / "control" / "illlm-execution-ledger-r40.json")
        self.global_knowledge = VersionedGlobalKnowledge(self.state_root / "control" / "global-illlm-r40.json")
        self.scheduler = PhysicalResourceScheduler.probe_host(self.state_root)

    def _root_node(self):
        node = getattr(self.host, "computer", None) or getattr(self.host, "root", None)
        if node is None:
            raise RuntimeError("RUNTIME_HOST_ROOT_UNRESOLVED")
        return node

    def _block(self, reason: str, stages: list[str], detail: Any = None) -> dict[str, Any]:
        out = {"status": f"BLOCKED:{reason}", "stages": stages}
        if detail is not None: out["detail"] = detail
        return out

    @staticmethod
    def _ledger_reference(node: Any) -> str:
        events = getattr(node.ledger, "events", ())
        return events[-1].event_id if events else "ledger://empty"

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(command, dict):
            return self._block("MALFORMED_COMMAND", [])
        stages = ["INGESTED", "MEMORY_IN_MOMENT"]
        observation = {"command_root": root(command), "source": command.get("source")}

        try:
            classified = self.data_classes.classify(
                source=command.get("source", ""),
                data_class=command.get("data_class", ""),
                payload=command.get("payload", {}),
                schema_version=command.get("schema_version", "1"),
                sector=command.get("sector"),
            )
        except Exception as exc:
            return self._block("DATA_CLASS", stages, str(exc))
        stages += ["CLASSIFIED", "SCHEMA_VALIDATED"]

        authority = str(command.get("authority", "")).strip()
        if not authority.startswith("authority://"):
            return self._block("AUTHORITY", stages, "AUTHORITY_URI_REQUIRED")
        stages.append("AUTHORITY_VALIDATED")

        illlm_request = command.get("illlm")
        if not isinstance(illlm_request, dict):
            return self._block("IL_LLM_REQUEST", stages)
        try:
            normalized, binding = self.illlm.resolve(illlm_request)
        except Exception as exc:
            return self._block("IL_LLM_RESOLUTION", stages, str(exc))
        stages += ["IL_LLM_RESOLVED", "LOGICAL_IDENTITY_RESOLVED"]

        try:
            target_node = self.host.resolve(normalized["lineage"])
            target_exists = True
        except Exception:
            target_node = None
            target_exists = False

        envelope = None
        node_created = False
        result: dict[str, Any]

        if binding.intent == "computer.instantiate":
            if not classified.node_eligible:
                return self._block("DATA_CLASS_NOT_NODE_ELIGIBLE", stages, classified.to_dict())
            try:
                parent = self.host.resolve(normalized["lineage"])
            except Exception as exc:
                return self._block("PARENT_NODE_RESOLUTION", stages, str(exc))
            child_id = normalized["child_id"]
            child_lineage = normalized["lineage"].rstrip("/") + "/" + child_id
            try:
                existing = self.host.resolve(child_lineage)
                return {
                    "status": "ROUTED_EXISTING_NODE",
                    "stages": stages + ["EXISTING_NODE_RESOLVED", "QUIESCED"],
                    "data_class": classified.to_dict(),
                    "node": self.host.snapshot(existing),
                    "observation": observation,
                }
            except Exception:
                pass
            try:
                requirement = resource_requirement(command.get("resources"))
                envelope = self.scheduler.allocate(child_id, requirement)
            except Exception as exc:
                return self._block("RESOURCE_SCHEDULER", stages, str(exc))
            stages.append("RESOURCE_ENVELOPE_GRANTED")
            try:
                executed = self.illlm.execute(illlm_request, self.host)
            except Exception as exc:
                self.scheduler.release(child_id)
                return self._block("RUNTIME_EXECUTION", stages, str(exc))
            result = executed
            node_created = True
            stages += ["NODE_MATERIALIZED", "RUNTIME_EXECUTED"]
            target_node = self.host.resolve(child_lineage)
            agent_id = f"agent://braink/{classified.data_class.lower()}/{child_id}"
            self.host.write_memory(child_lineage, "braink_agent", {"agent_id": agent_id, "authority": authority, "sector": classified.sector})
            self.host.write_memory(child_lineage, "resource_envelope", envelope.to_dict())
            self.host.write_memory(child_lineage, "data_class", classified.to_dict())
            stages += ["BRAINK_AGENT_BOUND", "NODE_MEMORY_BOUND"]
            vfs = NodeVFS(target_node.runtime, target_node.state_root / "node-vfs")
            vfs.write(child_id, "identity.json", {
                "node_id": child_id,
                "logical_identity": classified.logical_identity,
                "agent_id": agent_id,
                "resource_envelope": envelope.to_dict(),
            })
            stages.append("NODE_VFS_BOUND")
        else:
            if not target_exists:
                return self._block("EXISTING_NODE_REQUIRED", stages, normalized["lineage"])
            if not classified.execution_eligible and binding.mutating:
                return self._block("DATA_CLASS_NOT_EXECUTION_ELIGIBLE", stages, classified.to_dict())
            try:
                result = self.illlm.execute(illlm_request, self.host)
            except Exception as exc:
                return self._block("RUNTIME_EXECUTION", stages, str(exc))
            stages += ["EXISTING_NODE_RESOLVED", "RUNTIME_EXECUTED"]

        post = self.host.snapshot(target_node)
        if not post.get("ledger_verified"):
            return self._block("LOCAL_LEDGER_VERIFICATION", stages)
        stages += ["READBACK", "LOCAL_VERIFIED", "LEDGER_PROOF_BOUND"]

        ledger_ref = self._ledger_reference(target_node)
        global_result = None
        if command.get("global_delta") is not None:
            delta = command["global_delta"]
            snap = self.global_knowledge.snapshot()
            try:
                global_result = self.global_knowledge.apply_delta(
                    source_node=target_node.identity.computer_id,
                    source_event=ledger_ref,
                    data_class=classified.data_class,
                    previous_version=int(delta.get("previous_version", snap["version"])),
                    relation_delta=delta.get("relation_delta", {}),
                    provenance={"data_id": classified.data_id, "command_root": observation["command_root"]},
                    authority=authority,
                    validation={"status": "VALIDATED", "local_ledger_verified": True},
                    ledger_reference=ledger_ref,
                )
            except Exception as exc:
                return self._block("GLOBAL_IL_LLM_DELTA", stages, str(exc))
            self.host.write_memory("/".join(target_node.identity.lineage), "global_illlm_version", global_result["version"])
            stages += ["GLOBAL_IL_LLM_REGISTERED", "SUBSCRIBER_RESOLUTION"]

        mesh_state = "BLOCKED:MESH_ADMISSION_NOT_REQUESTED_OR_BOUND"
        server_state = "BLOCKED:SERVER_REGISTRATION_NOT_REQUESTED_OR_BOUND"
        subscription_state = "BLOCKED:SUBSCRIPTION_REGISTRY_NOT_REQUESTED_OR_BOUND"

        changed = bool(binding.mutating or node_created or global_result)
        stages.append("CONTINUE" if changed else "FIXED_POINT")
        if not changed: stages.append("QUIESCED")

        return {
            "status": "EXECUTED_LOCAL_VERIFIED",
            "stages": stages,
            "observation": observation,
            "data_class": classified.to_dict(),
            "il_llm": {"normalized": normalized, "binding": asdict(binding)},
            "result": result,
            "readback": post,
            "ledger_reference": ledger_ref,
            "global_delta": global_result,
            "mesh_state": mesh_state,
            "server_state": server_state,
            "subscription_state": subscription_state,
            "resource_envelope": None if envelope is None else envelope.to_dict(),
            "fixed_point": not changed,
        }
