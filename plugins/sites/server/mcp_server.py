#!/usr/bin/env python3
"""@Sites MCP server: ChatGPT/Codex tool surface for BRAINK × KEX Sites.

R8 authority law: Sites is a projection/execution surface. Mutating operations
must consume a signed AUTHORITATIVELY_COMMITTED DomainState projection envelope.
Legacy mutators are fenced rather than allowed to become a second truth system.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNTIME = HERE.parent.parent / "owner-control" / "sites-runtime"
NATIVE = HERE.parent / "native"
CAPS = HERE.parent / "CAPABILITY_REGISTRY.json"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(RUNTIME))

from app import S
from enterprise.orchestration.committed_projection_bridge_r8 import (
    CallableProjectionAdapter,
    CommittedProjectionBridge,
    ProjectionEnvelope,
    ProjectionReceiptLedger,
    ProjectionSigner,
    Surface,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit("Install dependency: pip install 'mcp>=1.0'") from exc


mcp = FastMCP(
    "@Sites",
    instructions=(
        "Owner-controlled Sites projection surface. Read tools may inspect Sites state directly. "
        "Mutating tools require a signed committed DomainState projection through "
        "sites_apply_committed_projection. Never equate repository, domain, version, "
        "deployment, or readback identity. Never promote provider success without readback evidence."
    ),
)


def governed_required(operation: str) -> dict[str, Any]:
    return {
        "status": "GOVERNED_DOMAINSTATE_REQUIRED",
        "operation": operation,
        "use_tool": "sites_apply_committed_projection",
    }


def _projection_bridge() -> CommittedProjectionBridge:
    raw = os.environ.get("BRAINK_PROJECTION_HMAC_KEY_HEX", "")
    if not raw:
        raise RuntimeError("BRAINK_PROJECTION_HMAC_KEY_HEX must be configured")
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError("BRAINK_PROJECTION_HMAC_KEY_HEX must be valid hex") from exc
    if len(key) < 32:
        raise RuntimeError("BRAINK_PROJECTION_HMAC_KEY_HEX must decode to at least 32 bytes")
    ledger = ProjectionReceiptLedger(RUNTIME / "state" / "sites_projection_receipts.sqlite3")
    return CommittedProjectionBridge(ProjectionSigner(key), ledger)


def _estate_import_impl() -> dict[str, Any]:
    index = json.loads((RUNTIME.parent / "COMPLETE_SITE_ESTATE_INDEX.json").read_text())
    created: list[str] = []
    bound: list[str] = []
    native = index.get("recovered_native_site_inventory", {}).get("sites", [])
    envs = index.get("domain_environment_fabric", {}).get("environments", [])
    for item in native:
        slug = item["slug"]
        if not S.site(slug):
            ids = item.get("project_ids_conflicting_historical") or []
            S.create_site(
                {
                    "slug": slug,
                    "name": slug.replace("-", " ").title(),
                    "kind": "CHATGPT_SITE",
                    "state": "RECOVERED",
                    "external_id": ids[0] if len(ids) == 1 else None,
                }
            )
            created.append(slug)
        host = item.get("url", "").replace("https://", "").rstrip("/")
        if host and not any(x["hostname"] == host for x in S.site(slug)["domains"]):
            S.domain(slug, {"hostname": host, "kind": "NATIVE_CHATGPT_SITE", "state": "RECOVERED"})
            bound.append(host)
    for item in envs:
        slug = item["slug"]
        if not S.site(slug):
            S.create_site(
                {
                    "slug": slug,
                    "name": slug.replace("-", " ").title(),
                    "kind": "DOMAIN_ENVIRONMENT",
                    "state": "RECOVERED",
                }
            )
            created.append(slug)
        host = item.get("domain")
        if host and not any(x["hostname"] == host for x in S.site(slug)["domains"]):
            S.domain(slug, {"hostname": host, "kind": "CUSTOM", "state": "HISTORICAL_PASS"})
            bound.append(host)
    return {
        "created": created,
        "domains_bound": bound,
        "site_count": len(S.sites()),
        "ledger": S.verify(),
    }


def _native_casepath_impl(
    action: str,
    *,
    origin: str | None = None,
    apply: bool = False,
    expected_marker: str | None = None,
) -> dict[str, Any]:
    path = NATIVE / "casepath_cp_pub_bridge_v50.py"
    spec = importlib.util.spec_from_file_location("casepath_cp_pub_bridge_v50", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("CASEPATH_NATIVE_BRIDGE_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mapping = {"discover": "CP-PUB-001", "publish": "CP-PUB-002", "readback": "CP-PUB-003"}
    if action not in mapping:
        return {"state": "FAIL_CLOSED_ACTION_NOT_ALLOWLISTED", "action": action}
    result = module.handle(
        mapping[action],
        apply=apply,
        origin=origin,
        expected_marker=expected_marker,
    )
    site = S.site("casepath-legal")
    S.event(
        "NATIVE_CASEPATH_" + action.upper(),
        result.get("state", "UNKNOWN"),
        result,
        site["id"] if site else None,
    )
    return result


def _apply_sites_projection(envelope: ProjectionEnvelope) -> dict[str, Any]:
    payload = dict(envelope.payload)
    operation = envelope.operation

    if operation == "site.create":
        result = S.create_site(payload)
    elif operation == "site.domain_bind":
        site = str(payload.pop("site"))
        result = S.domain(site, payload)
    elif operation == "site.version_create":
        site = str(payload.pop("site"))
        result = S.version(site, payload)
    elif operation == "site.deploy":
        site = str(payload.pop("site"))
        adapter = str(payload.get("adapter", "local"))
        if adapter != "local":
            raise RuntimeError("SITES_EXTERNAL_DEPLOY_REQUIRES_CONNECTOR_PROJECTION")
        result = S.deploy(site, payload)
    elif operation == "site.estate_import":
        if payload:
            raise ValueError("site.estate_import accepts no payload fields")
        result = _estate_import_impl()
    elif operation == "site.native_casepath":
        result = _native_casepath_impl(
            str(payload["action"]),
            origin=payload.get("origin"),
            apply=bool(payload.get("apply", False)),
            expected_marker=payload.get("expected_marker"),
        )
    else:
        raise ValueError(f"SITES_PROJECTION_OPERATION_NOT_REGISTERED:{operation}")

    return {
        "source_event_hash": envelope.event_hash,
        "producer_truth_hash": envelope.producer_truth_hash,
        "operation": operation,
        "result": result,
    }


def _readback_sites_projection(
    envelope: ProjectionEnvelope,
    result: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(envelope.payload)
    site_id = payload.get("site")
    if envelope.operation == "site.create":
        created = result.get("result") or {}
        site_id = created.get("id") or created.get("slug")
    observed = S.site(str(site_id)) if site_id else None
    return {
        "source_event_hash": envelope.event_hash,
        "producer_truth_hash": envelope.producer_truth_hash,
        "operation": envelope.operation,
        "site": observed,
        "ledger": S.verify(),
    }


@mcp.tool()
def sites_list() -> dict:
    """List persistent Site identities and states."""
    return {"sites": S.sites(), "ledger": S.verify()}


@mcp.tool()
def site_get(site_id_or_slug: str) -> dict:
    """Read one Site with domains, immutable versions and deployment receipts."""
    site = S.site(site_id_or_slug)
    return site or {"error": "SITE_NOT_FOUND", "site": site_id_or_slug}


@mcp.tool()
def sites_apply_committed_projection(envelope: dict[str, Any]) -> dict[str, Any]:
    """Apply one signed committed DomainState projection to the Sites runtime."""
    projection = ProjectionEnvelope.from_mapping(envelope)
    adapter = CallableProjectionAdapter(
        adapter_id="BRAINK_SITES_PLUGIN",
        surface=Surface.PLUGIN,
        apply_fn=_apply_sites_projection,
        readback_fn=_readback_sites_projection,
        mutating=True,
        readback_required=True,
    )
    return _projection_bridge().project(projection, adapter)


@mcp.tool()
def sites_projection_reconciliation_debt() -> dict[str, Any]:
    """Read Sites projection debt without altering authoritative DomainState."""
    bridge = _projection_bridge()
    return {"debt": bridge.ledger.debt(), "ledger": bridge.ledger.verify_chain()}


@mcp.tool()
def site_create(slug: str, name: str, kind: str = "SITE", external_id: str | None = None) -> dict:
    """Legacy direct mutation is fenced; use sites_apply_committed_projection."""
    return governed_required("site.create")


@mcp.tool()
def domain_bind(site_id_or_slug: str, hostname: str, kind: str = "CUSTOM", state: str = "RECORDED") -> dict:
    """Legacy direct mutation is fenced; use sites_apply_committed_projection."""
    return governed_required("site.domain_bind")


@mcp.tool()
def version_create(site_id_or_slug: str, files: dict[str, str], message: str = "") -> dict:
    """Legacy direct mutation is fenced; use sites_apply_committed_projection."""
    return governed_required("site.version_create")


@mcp.tool()
def deploy(site_id_or_slug: str, version_id: str | None = None, adapter: str = "local", target: str | None = None) -> dict:
    """Legacy direct mutation is fenced; use sites_apply_committed_projection."""
    return governed_required("site.deploy")


@mcp.tool()
def public_readback(site_id_or_slug: str, url: str, timeout: float = 10) -> dict:
    """Perform outside-in HTTP readback and ledger the observed response."""
    return S.readback(site_id_or_slug, {"url": url, "timeout": timeout})


@mcp.tool()
def capability_index() -> dict:
    """Return recovered BRAINK/KEX runtimes, native actuators, agent fleet and execution invariants."""
    return json.loads(CAPS.read_text())


@mcp.tool()
def native_casepath(
    action: str,
    origin: str | None = None,
    apply: bool = False,
    expected_marker: str | None = None,
) -> dict:
    """Read-only native CasePath discover/readback is direct; mutation requires committed projection."""
    if apply:
        return governed_required("site.native_casepath")
    return _native_casepath_impl(
        action,
        origin=origin,
        apply=False,
        expected_marker=expected_marker,
    )


@mcp.tool()
def ledger_verify() -> dict:
    """Verify the hash-chained @Sites event ledger."""
    return S.verify()


@mcp.tool()
def estate_import() -> dict:
    """Legacy direct estate import is fenced; use sites_apply_committed_projection."""
    return governed_required("site.estate_import")


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("SITES_MCP_TRANSPORT", "streamable-http"))
