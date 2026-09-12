from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class NodeStackProfile:
    profile_id: str
    role: str
    capabilities: tuple[str, ...]
    state_store: str
    receipt_surface: str


PROFILES: Final[dict[str, NodeStackProfile]] = {
    "SOFTWARE_PROCESSOR": NodeStackProfile(
        "STACK-SWPROC-001",
        "SOFTWARE_PROCESSOR",
        ("PARSE", "PLAN", "COMPILE", "TEST", "PACKAGE"),
        "ARRAY_INSTANCE_REGISTRY",
        "READBACK_RECEIPTS",
    ),
    "LOGIC_PROCESSOR": NodeStackProfile(
        "STACK-LOGIC-001",
        "LOGIC_PROCESSOR",
        ("EVALUATE", "ROUTE", "VERIFY", "REDUCE"),
        "00_OCCD_MASTER",
        "READBACK_RECEIPTS",
    ),
    "COMPUTE_SUBSTRATE": NodeStackProfile(
        "STACK-COMPUTE-001",
        "COMPUTE_SUBSTRATE",
        ("DISPATCH", "EXECUTE", "COLLECT", "RECONCILE"),
        "ARRAY_ACTIVATION_STATE",
        "ACTIVATION_RECEIPT_LEDGER",
    ),
    "VFS_SUBSTRATE": NodeStackProfile(
        "STACK-VFS-001",
        "VFS_SUBSTRATE",
        ("READ", "WRITE", "APPEND", "SNAPSHOT", "RESTORE"),
        "SHEET_AND_LEDGER_STATE",
        "READBACK_RECEIPTS",
    ),
    "SERVER_STACK": NodeStackProfile(
        "STACK-SERVER-001",
        "SERVER_STACK",
        ("BIND", "SERVE", "PROBE", "RESTART", "FAILOVER"),
        "CONNECTED_NODE_REGISTRY",
        "READBACK_RECEIPTS",
    ),
    "SOFTWARE_CREATION_NODE": NodeStackProfile(
        "STACK-COMPOSITE-001",
        "SOFTWARE_CREATION_NODE",
        ("INGEST", "PLAN", "GENERATE", "COMPILE_TEST", "PACKAGE_STORE", "SERVE"),
        "ALL_BOUND_REGISTRIES",
        "READBACK_RECEIPTS",
    ),
}


def resolve_profile(name: str) -> NodeStackProfile:
    key = name.strip().upper()
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"UNKNOWN_NODE_STACK_PROFILE:{key}") from exc


def capability_allowed(profile_name: str, capability: str) -> bool:
    profile = resolve_profile(profile_name)
    return capability.strip().upper() in profile.capabilities


def describe_profile(profile_name: str) -> dict[str, object]:
    p = resolve_profile(profile_name)
    return {
        "profile_id": p.profile_id,
        "role": p.role,
        "capabilities": list(p.capabilities),
        "state_store": p.state_store,
        "receipt_surface": p.receipt_surface,
        "authority": "BRAINK_CORE",
        "execution_role": "BOUNDED_NODE_SUBSTRATE",
        "promotion_authority": "BRAINK_CORE_ONLY",
    }
