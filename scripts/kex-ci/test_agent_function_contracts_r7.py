from __future__ import annotations

from mcp.braink_process_adapter.function_contracts import (
    FUNCTION_CONTRACTS,
    FunctionContractError,
    manifest,
    validate_payload,
)


def main() -> None:
    assert len(FUNCTION_CONTRACTS) == 14
    assert len({c.function_name for c in FUNCTION_CONTRACTS.values()}) == 14

    authority = []
    for capability_id in FUNCTION_CONTRACTS:
        authority.append({
            "capability_id": capability_id,
            "sector": "TEST",
            "owner_repo": "BRAINK",
            "operation": "TEST",
            "risk": "READ",
            "required_scopes": [],
            "idempotent": True,
            "requires_approval": False,
        })

    projected = manifest(authority)
    assert len(projected) == 14
    assert all(row["invoke_via"] == "braink_invoke_capability" for row in projected)
    assert all("parameters" in row for row in projected)
    assert all(row["authority"]["capability_id"] == row["capability_id"] for row in projected)

    normalized = validate_payload("domain.provision", {
        "tx_id": "TX-R7",
        "domain": "example.keddeh",
        "ip": "127.0.0.1",
    })
    assert normalized["owner_scope"] == "KEDDEH_SYSTEMS"

    try:
        validate_payload("domain.provision", {"domain": "example.keddeh", "ip": "127.0.0.1"})
    except FunctionContractError as exc:
        assert "missing required parameters" in str(exc)
    else:
        raise AssertionError("missing required parameter accepted")

    try:
        validate_payload("vfs.read", {"logical": "KEX://A", "backing": "file:///tmp/a", "surprise": True})
    except FunctionContractError as exc:
        assert "unknown parameters" in str(exc)
    else:
        raise AssertionError("unknown payload parameter accepted")

    try:
        validate_payload("vfs.write", {"logical": "KEX://A", "backing": "file:///tmp/a", "payload": "not-an-object"})
    except FunctionContractError as exc:
        assert "payload must be object" in str(exc)
    else:
        raise AssertionError("invalid payload type accepted")

    print("R7_AGENT_FUNCTION_CONTRACTS_PASS")


if __name__ == "__main__":
    main()
