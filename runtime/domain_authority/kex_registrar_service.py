import sqlite3
import os
import json
import hashlib
from pathlib import Path

LEDGER_PATH = Path(__file__).parent / "substrate_ledger" / "keddeh_registrar.sqlite"


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def init_registrar_db():
    os.makedirs(LEDGER_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(LEDGER_PATH)
    cursor = conn.cursor()

    # Legacy carrier routing ledger. Preserved for existing DNS/IP consumers.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_routing (
            domain TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            port INTEGER,
            owner_hash TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')

    # BRAINK semantic authority ledger. Identity/routing authority is not reduced to IP.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS semantic_bindings (
            domain TEXT PRIMARY KEY,
            canonical_id TEXT NOT NULL,
            braink_id TEXT NOT NULL,
            lineage_id TEXT NOT NULL,
            lexical_id TEXT NOT NULL,
            vector_id TEXT NOT NULL,
            service_route TEXT NOT NULL,
            storage_route TEXT,
            adapter_id TEXT,
            state TEXT DEFAULT 'ACTIVE',
            proof_sha256 TEXT NOT NULL
        )
    ''')

    # Licensing / Accounts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commercial_licenses (
            license_id TEXT PRIMARY KEY,
            owner_email TEXT,
            auth_provider TEXT, -- 'google' or 'github'
            tier TEXT, -- 'FREE', 'PLUS', 'ENTERPRISE'
            payment_status TEXT
        )
    ''')

    # Seed default carrier routes.
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('os.keddeh', '127.0.0.1', 8081)")
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('api.keddeh', '127.0.0.1', 8081)")
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('market.keddeh', '127.0.0.1', 8082)")

    conn.commit()
    conn.close()
    print(f"[REGISTRAR] Storage Substrate Initialized at {LEDGER_PATH}")


def resolve_domain(domain: str) -> str:
    """Legacy carrier resolver: returns IP if a carrier route exists, else None."""
    try:
        conn = sqlite3.connect(LEDGER_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ip_address FROM global_routing WHERE domain=?", (domain,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def register_domain(domain: str, ip: str, port: int, owner: str):
    """Legacy carrier registration. Preserved for DNS A-record compatibility."""
    conn = sqlite3.connect(LEDGER_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO global_routing (domain, ip_address, port, owner_hash) VALUES (?, ?, ?, ?)",
        (domain, ip, port, owner),
    )
    conn.commit()
    conn.close()
    return True


def register_semantic_domain(domain: str, binding: dict):
    """
    Register the BRAINK canonical domain object independently of carrier/IP state.
    Required fields are identity/routing coordinates, not a host address.
    """
    required = (
        "canonical_id",
        "braink_id",
        "lineage_id",
        "lexical_id",
        "vector_id",
        "service_route",
    )
    missing = [key for key in required if not binding.get(key)]
    if missing:
        raise ValueError(f"E_SEMANTIC_BINDING_MISSING:{','.join(missing)}")
    if binding["canonical_id"] != f"LEX://DOMAIN/{domain}":
        raise ValueError("E_CANONICAL_DOMAIN_MISMATCH")
    if binding["lexical_id"] != binding["canonical_id"]:
        raise ValueError("E_LEXICAL_CANONICAL_MISMATCH")

    proof_payload = {
        "domain": domain,
        "canonical_id": binding["canonical_id"],
        "braink_id": binding["braink_id"],
        "lineage_id": binding["lineage_id"],
        "lexical_id": binding["lexical_id"],
        "vector_id": binding["vector_id"],
        "service_route": binding["service_route"],
        "storage_route": binding.get("storage_route"),
        "adapter_id": binding.get("adapter_id"),
        "state": binding.get("state", "ACTIVE"),
    }
    proof_sha256 = hashlib.sha256(_canonical_json(proof_payload).encode()).hexdigest()

    conn = sqlite3.connect(LEDGER_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT OR REPLACE INTO semantic_bindings
        (domain, canonical_id, braink_id, lineage_id, lexical_id, vector_id,
         service_route, storage_route, adapter_id, state, proof_sha256)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            domain,
            proof_payload["canonical_id"],
            proof_payload["braink_id"],
            proof_payload["lineage_id"],
            proof_payload["lexical_id"],
            proof_payload["vector_id"],
            proof_payload["service_route"],
            proof_payload["storage_route"],
            proof_payload["adapter_id"],
            proof_payload["state"],
            proof_sha256,
        ),
    )
    conn.commit()
    conn.close()
    return proof_sha256


def resolve_semantic_domain(domain: str):
    """Return the canonical BRAINK binding without requiring a carrier/IP route."""
    try:
        conn = sqlite3.connect(LEDGER_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT domain, canonical_id, braink_id, lineage_id, lexical_id,
                   vector_id, service_route, storage_route, adapter_id, state,
                   proof_sha256
            FROM semantic_bindings WHERE domain=?
            ''',
            (domain,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


if __name__ == "__main__":
    init_registrar_db()
