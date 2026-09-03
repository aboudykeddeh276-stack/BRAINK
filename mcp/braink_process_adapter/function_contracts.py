from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


class FunctionContractError(ValueError):
    pass


@dataclass(frozen=True)
class AgentFunctionContract:
    capability_id: str
    function_name: str
    description: str
    parameters: dict[str, Any]


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _string(description: str, *, default: str | None = None, enum: list[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "string", "description": description}
    if default is not None:
        out["default"] = default
    if enum is not None:
        out["enum"] = enum
    return out


def _integer(description: str, *, default: int | None = None, minimum: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "integer", "description": description}
    if default is not None:
        out["default"] = default
    if minimum is not None:
        out["minimum"] = minimum
    return out


FUNCTION_CONTRACTS: dict[str, AgentFunctionContract] = {
    "identity.resolve": AgentFunctionContract(
        "identity.resolve", "braink_identity_resolve",
        "Resolve canonical legal and operating identity.",
        _obj({}),
    ),
    "domain.observe": AgentFunctionContract(
        "domain.observe", "braink_domain_observe",
        "Read resident BRAINK domain-authority state.",
        _obj({"domain": _string("Domain name to observe.")}, ["domain"]),
    ),
    "domain.provision": AgentFunctionContract(
        "domain.provision", "braink_domain_provision",
        "Atomically provision resident control-plane domain, zone and A-record state.",
        _obj({
            "tx_id": _string("Caller-supplied transaction identifier."),
            "domain": _string("Domain name to provision."),
            "ip": _string("Carrier IPv4/IPv6 address written into the resident A/AAAA-facing authority model."),
            "owner_scope": _string("BRAINK owner scope.", default="KEDDEH_SYSTEMS"),
        }, ["tx_id", "domain", "ip"]),
    ),
    "checkpoint.read": AgentFunctionContract(
        "checkpoint.read", "braink_checkpoint_read",
        "Read and verify a signed logical checkpoint.",
        _obj({"work_id": _string("Work identifier.")}, ["work_id"]),
    ),
    "checkpoint.write": AgentFunctionContract(
        "checkpoint.write", "braink_checkpoint_write",
        "Persist a signed logical checkpoint.",
        _obj({
            "work_id": _string("Work identifier."),
            "state": {"type": "object", "description": "State to checkpoint."},
        }, ["work_id", "state"]),
    ),
    "server.probe": AgentFunctionContract(
        "server.probe", "braink_server_probe",
        "Probe the resident server actuator bridge.",
        _obj({}),
    ),
    "server.validate_origin": AgentFunctionContract(
        "server.validate_origin", "braink_server_validate_origin",
        "Validate a server origin before mutation/release.",
        _obj({
            "origin": _string("Origin identifier or endpoint."),
            "target": _string("Optional target identifier."),
        }, ["origin"]),
    ),
    "server.readback": AgentFunctionContract(
        "server.readback", "braink_server_readback",
        "Read back resident server state after an operation.",
        _obj({
            "origin": _string("Origin identifier or endpoint."),
            "release_id": _string("Optional release identifier."),
        }, ["origin"]),
    ),
    "server.amend": AgentFunctionContract(
        "server.amend", "braink_server_amend",
        "Apply a governed server amendment. Approval is enforced by the capability runtime.",
        _obj({
            "origin": _string("Origin identifier or endpoint."),
            "target": _string("Target identifier."),
            "patch_id": _string("Patch/amendment identifier."),
        }, ["origin", "target", "patch_id"]),
    ),
    "server.release": AgentFunctionContract(
        "server.release", "braink_server_release",
        "Execute a governed destructive server release. Approval is mandatory.",
        _obj({
            "origin": _string("Origin identifier or endpoint."),
            "release_id": _string("Release identifier."),
        }, ["origin", "release_id"]),
    ),
    "vfs.bind": AgentFunctionContract(
        "vfs.bind", "braink_vfs_bind",
        "Bind a BRAINK logical address to a verified backing through the VFS resolver.",
        _obj({
            "logical": _string("Logical BRAINK/VFS address."),
            "backing": _string("Backing locator such as file:// or sqlite://."),
        }, ["logical", "backing"]),
    ),
    "vfs.read": AgentFunctionContract(
        "vfs.read", "braink_vfs_read",
        "Read a logical VFS value through its bound backing.",
        _obj({
            "logical": _string("Logical BRAINK/VFS address."),
            "backing": _string("Backing locator."),
        }, ["logical", "backing"]),
    ),
    "vfs.write": AgentFunctionContract(
        "vfs.write", "braink_vfs_write",
        "Write JSON state through a governed VFS binding.",
        _obj({
            "logical": _string("Logical BRAINK/VFS address."),
            "backing": _string("Backing locator."),
            "payload": {"type": "object", "description": "JSON payload to persist."},
        }, ["logical", "backing", "payload"]),
    ),
    "vfs.migrate": AgentFunctionContract(
        "vfs.migrate", "braink_vfs_migrate",
        "Migrate a logical value between backings after write/readback verification. Approval is mandatory.",
        _obj({
            "logical": _string("Logical BRAINK/VFS address."),
            "current_backing": _string("Current backing locator."),
            "new_backing": _string("Destination backing locator."),
        }, ["logical", "current_backing", "new_backing"]),
    ),
}


def manifest(capability_manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project governed capability contracts into an agent function-call manifest.

    Function selection remains separate from execution: every returned function carries
    `invoke_via=braink_invoke_capability` and never points directly at a resident mutator.
    """
    by_id = {row["capability_id"]: row for row in capability_manifest}
    out: list[dict[str, Any]] = []
    for capability_id, contract in FUNCTION_CONTRACTS.items():
        authority = by_id.get(capability_id)
        if authority is None:
            continue
        row = asdict(contract)
        row["authority"] = authority
        row["invoke_via"] = "braink_invoke_capability"
        out.append(row)
    return out


def validate_payload(capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    contract = FUNCTION_CONTRACTS.get(capability_id)
    if contract is None:
        raise FunctionContractError(f"no typed function contract for {capability_id}")
    if not isinstance(payload, dict):
        raise FunctionContractError("payload must be an object")

    schema = contract.parameters
    props = schema.get("properties", {})
    required = schema.get("required", [])
    missing = [name for name in required if name not in payload]
    if missing:
        raise FunctionContractError(f"missing required parameters: {missing}")

    if schema.get("additionalProperties") is False:
        unknown = sorted(set(payload) - set(props))
        if unknown:
            raise FunctionContractError(f"unknown parameters: {unknown}")

    normalized = dict(payload)
    for name, spec in props.items():
        if name not in normalized and "default" in spec:
            normalized[name] = spec["default"]
        if name not in normalized:
            continue
        value = normalized[name]
        typ = spec.get("type")
        if typ == "string" and not isinstance(value, str):
            raise FunctionContractError(f"{name} must be string")
        if typ == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise FunctionContractError(f"{name} must be integer")
        if typ == "object" and not isinstance(value, dict):
            raise FunctionContractError(f"{name} must be object")
        if "enum" in spec and value not in spec["enum"]:
            raise FunctionContractError(f"{name} must be one of {spec['enum']}")
        if "minimum" in spec and value < spec["minimum"]:
            raise FunctionContractError(f"{name} must be >= {spec['minimum']}")
    return normalized
