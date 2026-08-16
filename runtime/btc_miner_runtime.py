from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from btc_consensus import (
    assemble_block,
    build_coinbase,
    compact_target,
    dsha256,
    segwit_scriptpubkey,
    serialize_header,
    transaction_merkle_root,
)
from btc_workload_substrate import (
    LEDGER_DIR,
    LIVE_CANDIDATE_PATH,
    LIVE_TEMPLATE_PATH,
    check_rpc,
    request_template,
    save_json,
    utc_now,
    validate_and_submit,
)

SUPPORTED_NETWORKS = {"mainnet", "testnet", "signet", "regtest"}
CORE_CHAIN_NAMES = {
    "mainnet": "main",
    "testnet": "test",
    "signet": "signet",
    "regtest": "regtest",
}
NETWORK_HRPS = {
    "mainnet": "bc",
    "testnet": "tb",
    "signet": "tb",
    "regtest": "bcrt",
}
UINT32_SPACE = 1 << 32
UINT64_SPACE = 1 << 64
WORK_ALLOCATOR_DB = "miner_work_allocator.sqlite3"


def core_chain_name(network: str) -> str:
    try:
        return CORE_CHAIN_NAMES[network]
    except KeyError as exc:
        raise ValueError(f"unsupported Bitcoin network: {network!r}") from exc


def network_hrp(network: str) -> str:
    try:
        return NETWORK_HRPS[network]
    except KeyError as exc:
        raise ValueError(f"unsupported Bitcoin network: {network!r}") from exc


def parse_bounded_int(raw: str, name: str, minimum: int, maximum_exclusive: int) -> int:
    try:
        value = int(raw, 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value < maximum_exclusive:
        raise ValueError(f"{name} must be in [{minimum}, {maximum_exclusive})")
    return value


def template_work_descriptor(template: dict[str, Any]) -> dict[str, Any]:
    """Return the exact nonce/extranonce-invariant template coordinates used for allocation."""
    transactions = list(template.get("transactions") or [])
    tx_refs = [
        {
            "txid": str(tx.get("txid") or ""),
            "hash": str(tx.get("hash") or ""),
        }
        for tx in transactions
    ]
    return {
        "version": int(template["version"]),
        "previousblockhash": str(template["previousblockhash"]).lower(),
        "bits": str(template["bits"]).lower(),
        "curtime": int(template["curtime"]),
        "height": int(template["height"]),
        "coinbasevalue": int(template["coinbasevalue"]),
        "workid": None if template.get("workid") is None else str(template.get("workid")),
        "default_witness_commitment": template.get("default_witness_commitment"),
        "transactions": tx_refs,
    }


def template_work_key(template: dict[str, Any]) -> tuple[str, str]:
    descriptor_json = json.dumps(
        template_work_descriptor(template),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    # This digest is only a compact lookup/custody key for the canonical descriptor.
    # The descriptor itself remains stored and compared; the digest is not functional proof.
    return hashlib.sha256(descriptor_json.encode("utf-8")).hexdigest(), descriptor_json


def allocate_work_window(template: dict[str, Any], requested_hashes: int) -> dict[str, Any]:
    """Atomically allocate a disjoint nonce interval for an exact template.

    SQLite BEGIN IMMEDIATE serializes concurrent allocators across processes. The row stores
    the next nonce/extranonce cursor and every allocation is retained in an append-only table.
    """
    if requested_hashes <= 0:
        raise ValueError("requested_hashes must be positive")
    requested_hashes = min(int(requested_hashes), UINT32_SPACE)
    work_key, descriptor_json = template_work_key(template)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    db_path = LEDGER_DIR / WORK_ALLOCATOR_DB
    connection = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    try:
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS work_cursor (
                work_key TEXT PRIMARY KEY,
                descriptor_json TEXT NOT NULL,
                next_extranonce INTEGER NOT NULL,
                next_nonce INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS work_allocation (
                allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_key TEXT NOT NULL,
                descriptor_json TEXT NOT NULL,
                extranonce INTEGER NOT NULL,
                nonce_start INTEGER NOT NULL,
                nonce_count INTEGER NOT NULL,
                allocated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS work_allocation_key_idx ON work_allocation(work_key, extranonce, nonce_start)"
        )
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT descriptor_json, next_extranonce, next_nonce FROM work_cursor WHERE work_key = ?",
            (work_key,),
        ).fetchone()
        if row is None:
            extranonce = 0
            nonce_start = 0
            connection.execute(
                "INSERT INTO work_cursor(work_key, descriptor_json, next_extranonce, next_nonce, updated_at) VALUES (?, ?, 0, 0, ?)",
                (work_key, descriptor_json, utc_now()),
            )
        else:
            stored_descriptor, extranonce, nonce_start = row
            if stored_descriptor != descriptor_json:
                raise RuntimeError("work allocator key collision: descriptor mismatch")
            extranonce = int(extranonce)
            nonce_start = int(nonce_start)

        if not 0 <= extranonce < UINT64_SPACE:
            raise OverflowError("work allocator extranonce exhausted")
        if not 0 <= nonce_start < UINT32_SPACE:
            raise RuntimeError("work allocator nonce cursor is invalid")

        nonce_count = min(requested_hashes, UINT32_SPACE - nonce_start)
        if nonce_count <= 0:
            raise RuntimeError("work allocator produced an empty nonce interval")

        allocated_at = utc_now()
        connection.execute(
            "INSERT INTO work_allocation(work_key, descriptor_json, extranonce, nonce_start, nonce_count, allocated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (work_key, descriptor_json, extranonce, nonce_start, nonce_count, allocated_at),
        )

        next_nonce = nonce_start + nonce_count
        next_extranonce = extranonce
        if next_nonce == UINT32_SPACE:
            next_nonce = 0
            next_extranonce += 1
            if next_extranonce >= UINT64_SPACE:
                raise OverflowError("work allocator exhausted the extranonce domain")

        connection.execute(
            "UPDATE work_cursor SET next_extranonce = ?, next_nonce = ?, updated_at = ? WHERE work_key = ?",
            (next_extranonce, next_nonce, allocated_at, work_key),
        )
        connection.execute("COMMIT")
        return {
            "mode": "AUTO_PERSISTENT_SQLITE",
            "work_key": work_key,
            "extranonce": extranonce,
            "nonce_start": nonce_start,
            "nonce_count": nonce_count,
            "allocated_at": allocated_at,
            "allocator_db": str(db_path),
        }
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()


def resolve_work_allocation(template: dict[str, Any], requested_hashes: int) -> dict[str, Any]:
    """Use safe persistent allocation by default; explicit coordinates are operator-managed."""
    mode = os.environ.get("KEX_WORK_ALLOCATION_MODE", "auto").strip().lower()
    explicit_extranonce = os.environ.get("KEX_EXTRANONCE")
    explicit_nonce_start = os.environ.get("KEX_NONCE_START")

    # Preserve an intentional historical KEX_EXTRANONCE override, but classify it explicitly.
    if mode == "explicit" or explicit_extranonce is not None or explicit_nonce_start is not None:
        if explicit_extranonce is None:
            raise ValueError("KEX_EXTRANONCE is required for explicit work allocation")
        extranonce = parse_bounded_int(explicit_extranonce, "KEX_EXTRANONCE", 0, UINT64_SPACE)
        nonce_start = parse_bounded_int(explicit_nonce_start or "0", "KEX_NONCE_START", 0, UINT32_SPACE)
        nonce_count = min(requested_hashes, UINT32_SPACE - nonce_start)
        if nonce_count <= 0:
            raise ValueError("explicit work allocation has no remaining nonce space")
        work_key, _ = template_work_key(template)
        return {
            "mode": "EXPLICIT_OPERATOR_MANAGED",
            "work_key": work_key,
            "extranonce": extranonce,
            "nonce_start": nonce_start,
            "nonce_count": nonce_count,
            "allocated_at": utc_now(),
            "allocator_db": None,
        }
    if mode != "auto":
        raise ValueError("KEX_WORK_ALLOCATION_MODE must be 'auto' or 'explicit'")
    return allocate_work_window(template, requested_hashes)


def prepare_work(template: dict[str, Any], payout_address: str, extranonce: bytes, network: str) -> dict[str, Any]:
    """Build the nonce-invariant portion of a Bitcoin mining job exactly once."""
    transactions = list(template.get("transactions") or [])
    payout_script = segwit_scriptpubkey(payout_address, network_hrp(network))
    coinbase = build_coinbase(template, payout_script, extranonce)
    merkle_internal = transaction_merkle_root(coinbase.txid_internal, transactions)
    target = compact_target(str(template["bits"]))
    return {
        "transactions": transactions,
        "coinbase": coinbase,
        "merkle_internal": merkle_internal,
        "target": target,
        "ntime": int(template["curtime"]),
        "extranonce": extranonce,
    }


def candidate_from_hit(
    template: dict[str, Any], prepared: dict[str, Any], header: bytes, digest: bytes, nonce: int
) -> dict[str, Any]:
    """Assemble the expensive full block only after the 80-byte header satisfies target."""
    coinbase = prepared["coinbase"]
    block = assemble_block(header, coinbase, prepared["transactions"])
    return {
        "block_hex": block.hex(),
        "header_hex": header.hex(),
        "block_hash": digest[::-1].hex(),
        "hash_integer": int.from_bytes(digest, "little"),
        "target": prepared["target"],
        "target_valid": True,
        "merkle_root": prepared["merkle_internal"][::-1].hex(),
        "coinbase_txid": coinbase.txid_internal[::-1].hex(),
        "coinbase_hex": coinbase.full.hex(),
        "witness_commitment": coinbase.witness_commitment.hex() if coinbase.witness_commitment else None,
        "nonce": nonce,
        "ntime": prepared["ntime"],
        "extranonce": prepared["extranonce"].hex(),
        "workid": template.get("workid"),
        "construction_mode": "PREPARED_INVARIANTS_HEADER_SCAN_ASSEMBLE_ON_HIT",
    }


def scan_prepared_work(
    template: dict[str, Any], prepared: dict[str, Any], nonce_start: int, nonce_count: int
) -> tuple[dict[str, Any] | None, dict[str, Any], int]:
    """Hash only candidate headers in the allocated hot-loop interval and retain the best hash."""
    if not 0 <= nonce_start < UINT32_SPACE:
        raise ValueError("nonce_start outside uint32 domain")
    if nonce_count <= 0 or nonce_start + nonce_count > UINT32_SPACE:
        raise ValueError("nonce allocation outside uint32 domain")
    best: dict[str, Any] | None = None
    for nonce in range(nonce_start, nonce_start + nonce_count):
        header = serialize_header(
            template,
            prepared["merkle_internal"],
            nonce,
            prepared["ntime"],
        )
        digest = dsha256(header)
        hash_integer = int.from_bytes(digest, "little")
        block_hash = digest[::-1].hex()
        if best is None or hash_integer < best["hash_integer"]:
            best = {
                "block_hash": block_hash,
                "hash_integer": hash_integer,
                "nonce": nonce,
            }
        if hash_integer <= prepared["target"]:
            hashes_tested = nonce - nonce_start + 1
            return candidate_from_hit(template, prepared, header, digest, nonce), best, hashes_tested
    return None, best or {}, nonce_count


def execute() -> dict[str, Any]:
    network = os.environ.get("BTC_NETWORK", "mainnet").strip().lower()
    if network not in SUPPORTED_NETWORKS:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "BTC_NETWORK is unsupported",
            "network": network,
            "supported_networks": sorted(SUPPORTED_NETWORKS),
        }

    payout = os.environ.get("BTC_PAYOUT_ADDRESS", "").strip()
    if not payout:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "BTC_PAYOUT_ADDRESS is required",
            "network": network,
        }

    connected, chain = check_rpc()
    if not connected:
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core RPC unavailable; synthetic mainnet work is forbidden",
            "network": network,
            "rpc": chain,
        }

    observed_chain = str(chain.get("chain", ""))
    expected_chain = core_chain_name(network)
    if observed_chain != expected_chain:
        return {
            "state": "QUIESCED",
            "reason": "configured network does not match Bitcoin Core chain",
            "network": network,
            "expected_core_chain": expected_chain,
            "chain": observed_chain,
        }
    if chain.get("initialblockdownload") is True:
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core is in initial block download",
            "network": network,
        }
    verification = float(chain.get("verificationprogress", 0.0))
    try:
        minimum_verification = float(os.environ.get("BTC_MIN_VERIFICATION_PROGRESS", "0.999"))
    except ValueError:
        return {
            "state": "CONFIGURATION_BLOCKED",
            "reason": "BTC_MIN_VERIFICATION_PROGRESS must be numeric",
            "network": network,
        }
    if verification < minimum_verification:
        return {
            "state": "QUIESCED",
            "reason": "Bitcoin Core verification progress below mining gate",
            "verificationprogress": verification,
        }

    ok, template = request_template()
    if not ok:
        return {
            "state": "QUIESCED",
            "reason": "getblocktemplate failed",
            "template_result": template,
        }
    required = (
        "version",
        "previousblockhash",
        "bits",
        "curtime",
        "height",
        "coinbasevalue",
        "transactions",
    )
    missing = [key for key in required if key not in template]
    if missing:
        return {
            "state": "TEMPLATE_REJECTED",
            "reason": "missing required getblocktemplate fields",
            "missing": missing,
        }
    save_json(LIVE_TEMPLATE_PATH, template)

    try:
        max_hashes = parse_bounded_int(
            os.environ.get("KEX_MAX_HASHES_PER_JOB", "100000"),
            "KEX_MAX_HASHES_PER_JOB",
            1,
            UINT32_SPACE + 1,
        )
        allocation = resolve_work_allocation(template, max_hashes)
        extranonce = int(allocation["extranonce"]).to_bytes(8, "little", signed=False)
        prepared = prepare_work(template, payout, extranonce, network)
        candidate, best, hashes_tested = scan_prepared_work(
            template,
            prepared,
            int(allocation["nonce_start"]),
            int(allocation["nonce_count"]),
        )
    except (KeyError, TypeError, ValueError, RuntimeError, OverflowError, sqlite3.Error) as exc:
        return {
            "state": "WORK_REJECTED",
            "reason": str(exc),
            "network": network,
            "template_height": template.get("height"),
        }

    allocation_receipt = {
        key: allocation[key]
        for key in (
            "mode",
            "work_key",
            "extranonce",
            "nonce_start",
            "nonce_count",
            "allocated_at",
        )
    }

    if candidate is not None:
        save_json(LIVE_CANDIDATE_PATH, candidate)
        submission = validate_and_submit(candidate, template)
        return {
            "state": "NETWORK_TARGET_HIT" if not submission.get("accepted") else "ACCEPTED_BY_NODE",
            "network": network,
            "hashes_tested": hashes_tested,
            "construction_mode": candidate["construction_mode"],
            "work_allocation": allocation_receipt,
            "candidate": {
                key: candidate[key]
                for key in (
                    "block_hash",
                    "nonce",
                    "ntime",
                    "extranonce",
                    "merkle_root",
                    "coinbase_txid",
                )
            },
            "submission": submission,
            "completed_at": utc_now(),
        }

    return {
        "state": "SEARCH_WINDOW_EXHAUSTED",
        "network": network,
        "hashes_tested": hashes_tested,
        "construction_mode": "PREPARED_INVARIANTS_HEADER_SCAN_ASSEMBLE_ON_HIT",
        "work_allocation": allocation_receipt,
        "best_hash": best.get("block_hash"),
        "best_hash_integer": best.get("hash_integer"),
        "best_nonce": best.get("nonce"),
        "target": prepared["target"],
        "template_height": template["height"],
        "merkle_root": prepared["merkle_internal"][::-1].hex(),
        "coinbase_txid": prepared["coinbase"].txid_internal[::-1].hex(),
        "completed_at": utc_now(),
    }


if __name__ == "__main__":
    print(json.dumps(execute(), indent=2, sort_keys=True))
