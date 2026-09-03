import sqlite3
import os
import json
from pathlib import Path

LEDGER_PATH = Path(__file__).parent / "substrate_ledger" / "keddeh_registrar.sqlite"

def init_registrar_db():
    os.makedirs(LEDGER_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(LEDGER_PATH)
    cursor = conn.cursor()
    
    # DNS Ledger
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_routing (
            domain TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            port INTEGER,
            owner_hash TEXT,
            status TEXT DEFAULT 'ACTIVE'
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
    
    # Seed default routes
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('os.keddeh', '127.0.0.1', 8081)")
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('api.keddeh', '127.0.0.1', 8081)")
    cursor.execute("INSERT OR IGNORE INTO global_routing (domain, ip_address, port) VALUES ('market.keddeh', '127.0.0.1', 8082)")
    
    conn.commit()
    conn.close()
    print(f"[REGISTRAR] Storage Substrate Initialized at {LEDGER_PATH}")

def resolve_domain(domain: str) -> str:
    """Returns IP if domain exists, else None"""
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
    conn = sqlite3.connect(LEDGER_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_routing (domain, ip_address, port, owner_hash) VALUES (?, ?, ?, ?)", 
                   (domain, ip, port, owner))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_registrar_db()
