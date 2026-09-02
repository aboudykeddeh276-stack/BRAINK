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

BINDINGS: Dict[str, LiveServiceBinding] = {
    "mail": LiveServiceBinding(
        "mail", "Gmail", "BOUND_CONTROL_PLANE",
        ("search", "read", "label", "draft", "send"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Gmail connector; KEDDEH SYSTEMS/Runtime Mail namespace created"
    ),
    "drive": LiveServiceBinding(
        "drive", "Google Drive", "BOUND_WRITE",
        ("search", "create_folder", "create_file", "upload", "update"),
        "KEDDEH_SYSTEMS/BRAINK",
        "KEDDEH_SYSTEMS_RUNTIME_BINDINGS folder created through authenticated connector"
    ),
    "identity": LiveServiceBinding(
        "identity", "Google Contacts", "BOUND_READ_ONLY",
        ("search", "resolve_contact"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Contacts lookup returned resolvable identities"
    ),
    "calendar": LiveServiceBinding(
        "calendar", "Google Calendar", "BOUND_READ_CONTROL_PLANE",
        ("search", "read", "create", "update", "delete"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Authenticated Calendar metadata readback succeeded; write requires explicit runtime action receipt"
    ),
    "github": LiveServiceBinding(
        "github", "GitHub", "BOUND_WRITE_READBACK",
        ("fetch", "create_file", "update_file", "branch", "pull_request", "actions_readback"),
        "KEDDEH_SYSTEMS/BRAINK",
        "Canonical BRAINK repository accepts mutations and readback"
    ),
}

def registry() -> dict:
    return {k: asdict(v) for k, v in BINDINGS.items()}
