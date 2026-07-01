#!/usr/bin/env python3
"""VIRTUALISED_MEMORY integration tests for the Keddeh Matrix framework.

Confirms that Keddeh 1x1 indexing (no zero-axis) works seamlessly with
spreadsheet-style array mapping, active state management, and zero-free
memory references.

Anchor: A. KEDDEH / BRAINK / KEX / K-SYSTEMS
Status: MODEL-LOCAL
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from keddeh_matrix_core import KeddehValue, KeddehMatrix, BoundaryEvent, ObserverState


# ---------------------------------------------------------------------------
# VIRTUALISED_MEMORY: 1x1 indexed store
# ---------------------------------------------------------------------------

class VirtualisedMemory:
    """Zero-free memory store using 1-based Keddeh indexing.

    Rows and columns start at 1. Index 0 is the observer boundary —
    accessing it raises an ObserverBoundaryAccess exception.

    Supports:
    - set(row, col, value)  — store a KeddehValue
    - get(row, col)         — retrieve a KeddehValue
    - active_state()        — returns all currently set cells
    - spread_map()          — spreadsheet-style row/col dump
    """

    def __init__(self, label: str = "memory") -> None:
        self.label = label
        self._store: Dict[Tuple[int, int], KeddehValue] = {}
        self._access_log: List[dict] = []

    def set(self, row: int, col: int, value: float) -> KeddehValue:
        self._validate_index(row, col)
        kv = KeddehValue(value)
        self._store[(row, col)] = kv
        self._log("set", row, col, kv)
        return kv

    def get(self, row: int, col: int) -> Optional[KeddehValue]:
        self._validate_index(row, col)
        kv = self._store.get((row, col))
        self._log("get", row, col, kv)
        return kv

    def delete(self, row: int, col: int) -> None:
        self._validate_index(row, col)
        self._store.pop((row, col), None)
        self._log("delete", row, col, None)

    def active_state(self) -> Dict[Tuple[int, int], float]:
        """Return all currently active (set) cells with their values."""
        return {key: kv.value for key, kv in self._store.items()}

    def spread_map(self) -> List[dict]:
        """Spreadsheet-style dump: row, col, value, observer_state."""
        return [
            {
                "row": row,
                "col": col,
                "value": kv.value,
                "observer_state": kv.observer_state.value,
                "magnitude": kv.magnitude,
            }
            for (row, col), kv in sorted(self._store.items())
        ]

    def from_keddeh_matrix(self, matrix: KeddehMatrix, row_offset: int = 1, col_offset: int = 1) -> None:
        """Load a KeddehMatrix into memory starting at (row_offset, col_offset)."""
        for r in range(matrix.rows):
            for c in range(matrix.cols):
                kv = matrix.data[r][c]
                self._store[(row_offset + r, col_offset + c)] = kv

    def to_keddeh_matrix(self, row_start: int, col_start: int, rows: int, cols: int) -> KeddehMatrix:
        """Extract a region as a KeddehMatrix."""
        data = []
        for r in range(row_start, row_start + rows):
            row = []
            for c in range(col_start, col_start + cols):
                kv = self.get(r, c)
                if kv is None:
                    raise KeyError(f"No value at ({r},{c}) in VirtualisedMemory.")
                row.append(kv)
            data.append(row)
        return KeddehMatrix(rows=rows, cols=cols, data=data)

    def _validate_index(self, row: int, col: int) -> None:
        if row <= 0 or col <= 0:
            raise ObserverBoundaryAccess(
                f"Index ({row},{col}) is at or below the observer boundary. "
                "VirtualisedMemory uses 1-based Keddeh indexing — index 0 is the "
                "observer reference frame, not a valid memory address."
            )

    def _log(self, op: str, row: int, col: int, kv: Optional[KeddehValue]) -> None:
        self._access_log.append({
            "op": op,
            "row": row,
            "col": col,
            "value": kv.value if kv else None,
        })

    def __repr__(self) -> str:
        return f"VirtualisedMemory(label={self.label!r}, cells={len(self._store)})"


class ObserverBoundaryAccess(Exception):
    """Raised when code attempts to access the zero-indexed observer boundary."""


# ---------------------------------------------------------------------------
# Active state manager
# ---------------------------------------------------------------------------

@dataclass
class ActiveStateCell:
    row: int
    col: int
    value: KeddehValue
    tag: str = ""

    @property
    def is_active(self) -> bool:
        return True   # all stored cells are active; deletion removes them

    def summary(self) -> str:
        return (
            f"[{self.row},{self.col}] {self.value.value:+.4f} "
            f"({self.value.observer_state.value}) tag={self.tag!r}"
        )


class ActiveStateManager:
    """Track active cells without zero-anchored references."""

    def __init__(self, memory: VirtualisedMemory) -> None:
        self._memory = memory
        self._tags: Dict[Tuple[int, int], str] = {}

    def activate(self, row: int, col: int, value: float, tag: str = "") -> ActiveStateCell:
        kv = self._memory.set(row, col, value)
        self._tags[(row, col)] = tag
        return ActiveStateCell(row=row, col=col, value=kv, tag=tag)

    def deactivate(self, row: int, col: int) -> None:
        self._memory.delete(row, col)
        self._tags.pop((row, col), None)

    def active_cells(self) -> List[ActiveStateCell]:
        result = []
        for (row, col), kv in sorted(self._memory._store.items()):
            tag = self._tags.get((row, col), "")
            result.append(ActiveStateCell(row=row, col=col, value=kv, tag=tag))
        return result

    def state_count(self) -> int:
        return len(self._memory._store)

    def boundary_events(self) -> int:
        """Count any boundary-related operations in access log."""
        return sum(
            1 for entry in self._memory._access_log
            if entry.get("value") is None
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class VirtualisedMemoryIntegrationTest:
    """Confirm Keddeh 1x1 indexing and zero-free environment work end-to-end."""

    def run_indexing_confirmation(self) -> List[dict]:
        mem = VirtualisedMemory("indexing_test")
        results = []

        # Set values at 1-based positions
        for r in range(1, 4):
            for c in range(1, 4):
                val = float(r * 10 + c) * (1 if (r + c) % 2 == 0 else -1)
                mem.set(r, c, val)
                results.append({
                    "op": "set",
                    "row": r,
                    "col": c,
                    "value": val,
                    "status": "ok",
                })

        # Confirm zero-index access raises ObserverBoundaryAccess
        for bad_index in [(0, 1), (1, 0), (0, 0), (-1, 1)]:
            try:
                mem.get(*bad_index)
                results.append({"bad_index": bad_index, "result": "unexpected_success"})
            except ObserverBoundaryAccess as e:
                results.append({
                    "bad_index": bad_index,
                    "error": "ObserverBoundaryAccess (expected)",
                    "message": str(e)[:80],
                })

        return results

    def run_spreadsheet_mapping(self) -> List[dict]:
        """Spreadsheet-style array mapping in zero-free environment."""
        mem = VirtualisedMemory("spreadsheet")
        # Simulate a simple 3×3 spreadsheet
        spreadsheet_data = [
            (1, 1, 1.0,  "A1"),
            (1, 2, -2.0, "B1"),
            (1, 3, 3.0,  "C1"),
            (2, 1, -4.0, "A2"),
            (2, 2, 5.0,  "B2"),
            (2, 3, -6.0, "C2"),
            (3, 1, 7.0,  "A3"),
            (3, 2, -8.0, "B3"),
            (3, 3, 9.0,  "C3"),
        ]
        for r, c, v, label in spreadsheet_data:
            mem.set(r, c, v)

        return [
            {
                "cell": entry["row"] * 100 + entry["col"],
                "label": spreadsheet_data[i][3],
                **entry,
            }
            for i, entry in enumerate(mem.spread_map())
        ]

    def run_matrix_roundtrip(self) -> dict:
        """Load a KeddehMatrix into memory and extract it back."""
        original = KeddehMatrix.from_values([
            [2.0, -1.0, 3.0],
            [-4.0, 5.0, -2.0],
            [1.0, -3.0, 6.0],
        ])
        mem = VirtualisedMemory("matrix_roundtrip")
        mem.from_keddeh_matrix(original, row_offset=1, col_offset=1)

        extracted = mem.to_keddeh_matrix(row_start=1, col_start=1, rows=3, cols=3)
        match = all(
            abs(original.data[r][c].value - extracted.data[r][c].value) < 1e-12
            for r in range(3) for c in range(3)
        )
        return {
            "test": "matrix_roundtrip",
            "rows": original.rows,
            "cols": original.cols,
            "original_det": round(original.determinant(), 4),
            "extracted_det": round(extracted.determinant(), 4),
            "values_match": match,
            "status": "PASS" if match else "FAIL",
        }

    def run_active_state_management(self) -> List[dict]:
        """Validate active state without zero-anchored references."""
        mem = VirtualisedMemory("active_state")
        mgr = ActiveStateManager(mem)

        results = []
        cells = [
            (1, 1, 10.0, "sensor_A"),
            (1, 2, -5.0, "sensor_B"),
            (2, 1, 3.0,  "sensor_C"),
            (2, 2, -7.0, "sensor_D"),
            (3, 1, 15.0, "sensor_E"),
        ]
        for r, c, v, tag in cells:
            cell = mgr.activate(r, c, v, tag)
            results.append({
                "activated": cell.summary(),
                "is_active": cell.is_active,
            })

        results.append({
            "total_active": mgr.state_count(),
            "expected": len(cells),
            "match": mgr.state_count() == len(cells),
        })

        # Deactivate one
        mgr.deactivate(1, 2)
        results.append({
            "after_deactivate_(1,2)": mgr.state_count(),
            "expected": len(cells) - 1,
        })

        active_summary = [c.summary() for c in mgr.active_cells()]
        results.append({"active_cells": active_summary})
        return results

    def run_all(self) -> dict:
        return {
            "indexing_confirmation": self.run_indexing_confirmation(),
            "spreadsheet_mapping": self.run_spreadsheet_mapping(),
            "matrix_roundtrip": self.run_matrix_roundtrip(),
            "active_state_management": self.run_active_state_management(),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _run_demo() -> None:
    import json

    print("=" * 60)
    print("VIRTUALISED_MEMORY Integration — Keddeh Framework")
    print("=" * 60)

    test = VirtualisedMemoryIntegrationTest()

    print("\n--- 1. 1x1 Indexing Confirmation (no zero-axis) ---")
    for r in test.run_indexing_confirmation():
        print(" ", json.dumps(r))

    print("\n--- 2. Spreadsheet-style Array Mapping ---")
    for r in test.run_spreadsheet_mapping():
        print(" ", json.dumps(r))

    print("\n--- 3. Matrix Roundtrip ---")
    print(" ", json.dumps(test.run_matrix_roundtrip()))

    print("\n--- 4. Active State Management ---")
    for r in test.run_active_state_management():
        print(" ", json.dumps(r))

    print("\nStatus: MODEL-LOCAL")


if __name__ == "__main__":
    _run_demo()
