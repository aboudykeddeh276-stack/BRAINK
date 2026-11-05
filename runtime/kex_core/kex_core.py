#!/usr/bin/env python3
"""KEX deterministic execution prototype. Local SQLite; not hardware proof."""
from __future__ import annotations
import argparse
import decimal
import hashlib
import json
import sqlite3
from pathlib import Path

D = decimal.Decimal

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def dec(s):
    value = D(s)
    if not value.is_finite():
        raise ValueError("nonfinite number")
    return format(value.normalize(), "f")

def compile_instruction(source):
    parts = source.strip().split()
    if len(parts) != 3 or parts[0].upper() != "BALANCE":
        raise ValueError("only BALANCE a b is supported")
    a, b = D(parts[1]), D(parts[2])
    value = a + b
    if not all(x.is_finite() for x in (a, b, value)):
        raise ValueError("nonfinite number")
    return {"version": 1, "instruction": "BALANCE", "source": source,
            "inputs": [dec(parts[1]), dec(parts[2])],
            "result": {"existence": 1, "magnitude": dec(str(value)),
                       "status": "Cancelled" if value == 0 else "Active"},
            "semantics": "exact-decimal"}

def assemble(block):
    data = canonical(block)
    instruction_byte = hashlib.sha256(data).digest()[0]
    high, low = instruction_byte >> 4, instruction_byte & 15
    return {"instruction_byte": instruction_byte, "high": high, "low": low,
            "fold": (high * low + (high ^ low)) % 16,
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "fold_kind": "KEX_F_j(j=0)"}

class Engine:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS ledger("
                        "seq INTEGER PRIMARY KEY, parent TEXT NOT NULL, block TEXT NOT NULL,"
                        "assembly TEXT NOT NULL, record_hash TEXT UNIQUE NOT NULL)")
        self.db.commit()

    def execute(self, source):
        block = compile_instruction(source)
        assembly = assemble(block)
        row = self.db.execute("SELECT seq,record_hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        seq = 1 if row is None else row[0] + 1
        parent = "0" * 64 if row is None else row[1]
        record = {"sequence": seq, "parent": parent, "block": block, "assembly": assembly}
        h = sha(record)
        self.db.execute("INSERT INTO ledger VALUES(?,?,?,?,?)",
                        (seq, parent, canonical(block).decode(), canonical(assembly).decode(), h))
        self.db.commit()
        return {"state_id": f"state_coord_{seq}", "hash": h, "block": block, "assembly": assembly}

    def verify(self):
        parent, count = "0" * 64, 0
        for seq, p, b, a, h in self.db.execute(
            "SELECT seq,parent,block,assembly,record_hash FROM ledger ORDER BY seq"
        ):
            block, assembly = json.loads(b), json.loads(a)
            if (seq != count + 1 or p != parent or assemble(block) != assembly or
                sha({"sequence": seq, "parent": p, "block": block, "assembly": assembly}) != h):
                return False, count
            parent, count = h, count + 1
        return True, count

    def export(self, destination):
        valid, count = self.verify()
        if not valid:
            raise ValueError(f"ledger failed verification after {count} records")
        rows = [{"seq": seq, "parent": p, "block": json.loads(b),
                 "assembly": json.loads(a), "record_hash": h}
                for seq, p, b, a, h in self.db.execute(
                    "SELECT seq,parent,block,assembly,record_hash FROM ledger ORDER BY seq")]
        output = Path(destination)
        output.write_bytes(canonical({"schema": "kex-ledger-export-v1", "rows": rows}) + b"\n")
        return {"rows": len(rows), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}

def field(n):
    if not 1 <= n <= 1024:
        raise ValueError("grid must be 1..1024")
    counts = [0] * 16
    for x in range(1, n + 1):
        for y in range(1, n + 1):
            counts[(x * y) % 16] += 1
    return {"grid_size": n, "cells": n*n, "address_origin": [1,1],
            "potential_histogram": counts, "epsilon_invariant": 1,
            "physical_energy_joules": None, "physical_energy_status": "UNMEASURED"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, help="Writable SQLite ledger location")
    parser.add_argument("--balance", nargs=2, metavar=("A","B"))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--export")
    parser.add_argument("--grid", type=int)
    args = parser.parse_args()
    engine = Engine(args.database)
    output = {}
    if args.balance:
        output["execution"] = engine.execute("BALANCE " + " ".join(args.balance))
    if args.verify or args.balance or args.export:
        valid, count = engine.verify()
        output["verification"] = {"valid": valid, "rows": count}
        if not valid:
            raise RuntimeError("ledger verification failed")
    if args.export:
        output["export"] = engine.export(args.export)
    if args.grid is not None:
        output["field"] = field(args.grid)
    print(json.dumps(output, sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
