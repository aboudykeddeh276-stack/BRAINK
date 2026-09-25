from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Tuple

@dataclass(frozen=True)
class LiveServiceBinding:
    service: str
    provider: str
    state: str
    capabilities: Tuple[str, ...]
    authority: str
    evidence: str
    authority_class: str
    readback_required: bool
    projection_only: bool

BINDINGS: Dict[str, LiveServiceBinding] = {
    "mail": LiveServiceBinding(
        "mail", "Gmail", "BOUND_CONTROL_PLANE",
        ("search", "read", "label", "draft", "send"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Gmail connector; KEDDEH SYSTEMS/Runtime Mail namespace created",
        "EXTERNALLY_DELEGATED", True, True
    ),
    "drive": LiveServiceBinding(
        "drive", "Google Drive", "BOUND_WRITE",
        ("search", "create_folder", "create_file", "upload", "update"),
        "KEDDEH_SYSTEMS/BRAINK",
        "KEDDEH_SYSTEMS_RUNTIME_BINDINGS folder created through authenticated connector",
        "EXTERNALLY_DELEGATED", True, True
    ),
    "identity": LiveServiceBinding(
        "identity", "Google Contacts", "BOUND_READ_ONLY",
        ("search", "resolve_contact"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Contacts lookup returned resolvable identities",
        "EXTERNALLY_DELEGATED", True, True
    ),
    "calendar": LiveServiceBinding(
        "calendar", "Google Calendar", "BOUND_READ_CONTROL_PLANE",
        ("search", "read", "create", "update", "delete"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Calendar metadata readback succeeded; write requires explicit runtime action receipt",
        "EXTERNALLY_DELEGATED", True, True
    ),
    "github": LiveServiceBinding(
        "github", "GitHub", "BOUND_WRITE_READBACK",
        ("fetch", "create_file", "update_file", "branch", "pull_request", "actions_readback"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Canonical BRAINK repository accepts mutations and readback",
        "EXTERNALLY_DELEGATED", True, True
    ),
}

def registry() -> dict:
    return {k: asdict(v) for k, v in BINDINGS.items()}
