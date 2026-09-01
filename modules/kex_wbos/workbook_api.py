#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[2]
WORKBOOK_ROOT = BASE / "workbooks"
UPLOAD_ROOT = BASE / "runtime" / "workbooks"

DATASETS = {
    "core-lattice": "CORE_LATTICE",
    "flow-territories": "FLOW_TERRITORIES",
    "genome-store": "GENOME_STORE",
    "kex-dna": "KEX_DNA",
    "substrate-grid": "SUBSTRATE_GRID",
    "system-state": "SYSTEM_STATE",
    "work-log": "WORK_LOG",
    "global-index": "GLOBAL_INDEX",
    "root-matrix": "ROOT_MATRIX",
    "benchmarks": "BENCHMARKS",
    "hyper-cores": "HYPER_CORES",
    "servers": "SERVERS",
    "storage-devices": "STORAGE_DEVICES",
    "logs": "LOGS",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_workbooks() -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for root in (WORKBOOK_ROOT, UPLOAD_ROOT):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".xlsx", ".xlsm"}:
                files.append({
                    "path": path.relative_to(BASE).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                })
    return files


def source_not_resident(dataset: str) -> dict[str, Any]:
    return {
        "state": "SOURCE_NOT_RESIDENT",
        "dataset": dataset,
        "rows": [],
        "workbooks_discovered": discover_workbooks(),
        "claim_boundary": "The API route is resident, but no workbook source containing the requested sheet has been resolved in the repository/runtime workbook mount. No rows are invented from narrative descriptions.",
    }


def dataset_response(dataset: str) -> dict[str, Any]:
    # Parsing is intentionally separated from route existence. Until an actual workbook
    # is resident and a sheet parser is bound, this endpoint exposes the unresolved source state.
    return source_not_resident(dataset)


def root_matrix_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[float] = []
    for row in rows:
        for value in row.get("values", []):
            if isinstance(value, (int, float)):
                values.append(float(value))
    if not values:
        return {"count": 0, "mean": None, "min": None, "max": None, "state": "SOURCE_NOT_RESIDENT"}
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "state": "COMPUTED_FROM_RESIDENT_ROWS",
    }


def storage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state": "SOURCE_NOT_RESIDENT" if not rows else "COMPUTED_FROM_RESIDENT_ROWS",
        "categories": [],
        "source_row_count": len(rows),
    }


def system_summary(hyper_cores: list[dict[str, Any]], servers: list[dict[str, Any]], storage: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state": "SOURCE_NOT_RESIDENT" if not (hyper_cores or servers or storage) else "COMPUTED_FROM_RESIDENT_ROWS",
        "hyper_cores": len(hyper_cores),
        "servers": len(servers),
        "storage_devices": len(storage),
    }


def virtualization_metrics() -> dict[str, Any]:
    return {
        "state": "UNMEASURED",
        "cpuOverheadPct": None,
        "memoryOverheadPct": None,
        "storageOverheadPct": None,
        "networkOverheadPct": None,
        "measured_at": None,
        "claim_boundary": "No virtualization benchmark receipt is resident; numeric overhead values are therefore not fabricated.",
    }


def activation_receipt(filename: str, payload: bytes) -> dict[str, Any]:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    safe = Path(filename).name
    target = UPLOAD_ROOT / safe
    target.write_bytes(payload)
    return {
        "signal": "WORKBOOK_STORED_FOR_RESOLUTION",
        "asyncJobId": None,
        "path": target.relative_to(BASE).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "timestamp": time.time(),
        "claim_boundary": "Storage/activation receipt proves the workbook bytes were accepted by this runtime path. It does not prove every sheet was parsed or executed.",
    }
