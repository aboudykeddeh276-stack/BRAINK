#!/usr/bin/env python3
"""
Nested Core Runtime Module

Implements a rigorous zero-less index spectrum and nested runtime system.
This module provides:
- KeddehZeroLessMatrix: Zero-less indexing (bypasses 0 entirely) with bidirectional and shift arithmetic
- WiredFATFileSystem: Uncompressed state database with integrity verification
- NestedCoreRuntime: Self-bootstrapping nested runtime system with arbitrary tree nesting and snapshotting

Closes issue: aboudykeddeh276-stack/BRAINK#13
"""

import hashlib
import sys
from typing import Dict, Any, List, Optional


class KeddehZeroLessMatrix:
    """
    Implements a rigorous zero-less index spectrum: ... -2, -1, 1, 2, ...
    Bypasses standard 0-indexing entirely.
    
    The mapping follows the pattern:
    - logical index 1 -> signed index -1
    - logical index 2 -> signed index -2
    - logical index 3 -> signed index -3
    - logical index 4 -> signed index 1
    - logical index 5 -> signed index 2
    - logical index 6 -> signed index 3
    """
    
    HALFWAY = 3
        
    @staticmethod
    def get_signed_index(logical_idx: int) -> int:
        """
        Convert logical index to signed index in zero-less spectrum.
        
        Args:
            logical_idx: Positive integer logical index (1, 2, 3, ...)
            
        Returns:
            Signed index avoiding zero: -3, -2, -1, 1, 2, 3, ...
            
        Raises:
            ValueError: If logical_idx <= 0
        """
        if logical_idx <= 0:
            raise ValueError("Zero or negative logical indices strictly outlawed in Keddeh Matrix input.")
        
        # Bypasses 0: 1->-1, 2->-2, 3->-3, 4->1, 5->2, 6->3, etc.
        if logical_idx <= KeddehZeroLessMatrix.HALFWAY:
            return -logical_idx
        else:
            return (logical_idx - KeddehZeroLessMatrix.HALFWAY)

    @staticmethod
    def get_logical_index(signed_idx: int) -> int:
        """
        Convert signed zero-less index back to logical index.
        
        Args:
            signed_idx: Signed index (non-zero integer)
            
        Returns:
            Positive integer logical index.
            
        Raises:
            ValueError: If signed_idx is zero or out of bounds.
        """
        if signed_idx == 0:
            raise ValueError("Cartesian zero detected. Zero-less spectrum does not contain zero index.")
        
        if signed_idx < 0:
            if signed_idx < -KeddehZeroLessMatrix.HALFWAY:
                raise ValueError(f"Signed index {signed_idx} is out of bounds for the defined zero-less spectrum.")
            return -signed_idx
        else:
            return signed_idx + KeddehZeroLessMatrix.HALFWAY

    @staticmethod
    def shift_index(signed_idx: int, steps: int) -> int:
        """
        Shift a signed index by a given number of steps in the zero-less spectrum,
        safely bypassing Cartesian zero.
        
        Args:
            signed_idx: Starting signed index (non-zero integer)
            steps: Number of steps to shift (integer, can be positive or negative)
            
        Returns:
            New signed index in the zero-less spectrum.
            
        Raises:
            ValueError: If starting signed_idx is zero.
        """
        if signed_idx == 0:
            raise ValueError("Cannot shift from Cartesian zero index.")
        
        if steps == 0:
            return signed_idx
            
        # Map signed_idx to continuous integer space where:
        # negative indices remain negative, positive indices shift left by 1.
        # e.g. -1 -> -1, 1 -> 0, 2 -> 1, etc.
        seq = signed_idx if signed_idx < 0 else signed_idx - 1
        new_seq = seq + steps
        
        # Map back from continuous space to zero-less space
        if new_seq >= 0:
            return new_seq + 1
        else:
            return new_seq


class WiredFATFileSystem:
    """
    A literal uncompressed string database mapped via zero-less indices.
    
    Stores state data as uncompressed literal text blocks, with each
    storage cell indexed using the Keddeh zero-less matrix.
    """
    
    def __init__(self):
        self.storage_cells: Dict[int, Dict[str, str]] = {}
    
    def assign_state(self, logical_idx: int, path: str, state_literal: str) -> None:
        """
        Assign state to a storage cell.
        
        Args:
            logical_idx: Logical index (positive integer)
            path: File path/location identifier
            state_literal: Uncompressed state data as string
        """
        signed_idx = KeddehZeroLessMatrix.get_signed_index(logical_idx)
        # Store as uncompressed literal text data block
        self.storage_cells[signed_idx] = {
            "path": path,
            "data": state_literal,
            "hash": hashlib.sha256(state_literal.encode('utf-8')).hexdigest()
        }
    
    def fetch_state(self, logical_idx: int) -> Dict[str, str]:
        """
        Fetch state from a storage cell.
        
        Args:
            logical_idx: Logical index (positive integer)
            
        Returns:
            Dictionary containing path, data, and hash. Returns void entry if not found.
        """
        signed_idx = KeddehZeroLessMatrix.get_signed_index(logical_idx)
        return self.storage_cells.get(signed_idx, {"path": "VOID", "data": "", "hash": ""})

    def delete_state(self, logical_idx: int) -> None:
        """
        Delete state from a storage cell.
        
        Args:
            logical_idx: Logical index (positive integer)
        """
        signed_idx = KeddehZeroLessMatrix.get_signed_index(logical_idx)
        if signed_idx in self.storage_cells:
            del self.storage_cells[signed_idx]

    def list_states(self) -> List[Dict[str, Any]]:
        """
        List all active storage states, sorted by signed index.
        
        Returns:
            List of state cell dictionaries.
        """
        return [
            {
                "signed_index": idx,
                "path": self.storage_cells[idx]["path"],
                "data": self.storage_cells[idx]["data"],
                "hash": self.storage_cells[idx]["hash"]
            }
            for idx in sorted(self.storage_cells.keys())
        ]

    def verify_integrity(self) -> bool:
        """
        Verify the SHA256 hash integrity of all stored cells.
        
        Returns:
            True if all cells are integral, False otherwise.
        """
        for cell in self.storage_cells.values():
            expected = cell["hash"]
            actual = hashlib.sha256(cell["data"].encode('utf-8')).hexdigest()
            if expected != actual:
                return False
        return True

    def export_state_manifest(self) -> Dict[str, Any]:
        """
        Export a structural manifest of all stored states.
        
        Returns:
            Dictionary mapping signed indices to metadata.
        """
        return {
            str(idx): {
                "path": cell["path"],
                "hash": cell["hash"],
                "size_bytes": len(cell["data"])
            }
            for idx, cell in self.storage_cells.items()
        }

    def clear_state(self) -> None:
        """Clear all active storage cells."""
        self.storage_cells.clear()


class NestedCoreRuntime:
    """
    The complete running system that contains a running booted state system
    of itself running within, executing actual integer operations.
    
    Features:
    - Self-bootstrapping into zero-less space
    - Nested layer runtime initialization supporting multiple concurrent mirrors
    - Capacity doubling/scaling with state updates
    - Recursive structural audit of the system hierarchy
    - Deep recursive state snapshotting and restoration
    """
    
    def __init__(self, name: str, base_capacity_tbi: int, depth: int = 1):
        """
        Initialize a NestedCoreRuntime system.
        
        Args:
            name: System identifier name
            base_capacity_tbi: Base capacity in TBi (tebi-bits)
            depth: Nesting depth level (default 1 for root)
        """
        self.name = name
        self.capacity_tbi = base_capacity_tbi
        self.depth = depth
        self.fs = WiredFATFileSystem()
        self.mirrors: Dict[str, 'NestedCoreRuntime'] = {}
        
        # Self-bootstrap the state into the zero-less space
        self.fs.assign_state(
            1,
            f"/sys/{self.name.lower()}/meta",
            f"SYSTEM_NAME:{self.name}|CAPACITY:{self.capacity_tbi}TBi|DEPTH:{self.depth}"
        )
        self.fs.assign_state(
            2,
            f"/sys/{self.name.lower()}/status",
            "BOOTED_STABLE"
        )

    @property
    def inner_system(self) -> Optional['NestedCoreRuntime']:
        """
        Backward compatible access to the first embedded mirror.
        
        Returns:
            The first NestedCoreRuntime mirror system if any exist, else None.
        """
        if not self.mirrors:
            return None
        return next(iter(self.mirrors.values()))

    @inner_system.setter
    def inner_system(self, value: Optional['NestedCoreRuntime']) -> None:
        """
        Backward compatible setter for the first embedded mirror.
        
        Args:
            value: A NestedCoreRuntime system to set as primary mirror or None to clear all.
        """
        if value is None:
            self.mirrors.clear()
        else:
            self.mirrors[value.name] = value
    
    def embed_mirror(self, inner_name: str, inner_capacity_tbi: int) -> None:
        """
        Embed a nested runtime system within this system.
        
        Args:
            inner_name: Name of the inner system
            inner_capacity_tbi: Capacity of the inner system in TBi
        """
        # Nested layer runtime initialization
        child = NestedCoreRuntime(inner_name, inner_capacity_tbi, depth=self.depth + 1)
        self.mirrors[inner_name] = child
        
        # Register the child system state string into the parent's uncompressed filesystem
        # First child goes to logical index 3 for exact backward compatibility
        logical_idx = 3 + len(self.mirrors) - 1
        child_meta = f"EMBEDDED_MIRROR_SYSTEM_IDENTIFIER:{inner_name}|ALLOCATION:{inner_capacity_tbi}TBi"
        self.fs.assign_state(logical_idx, f"/sys/{self.name.lower()}/nested_link/{inner_name.lower()}", child_meta)
    
    def scale_capacity(self, factor: float) -> None:
        """
        Scale system capacity recursively across all nested layers.
        
        Args:
            factor: Positive scaling factor (e.g. 2.0 to double)
            
        Raises:
            ValueError: If factor <= 0
        """
        if factor <= 0:
            raise ValueError("Capacity scaling factor must be strictly positive.")
            
        self.capacity_tbi = int(self.capacity_tbi * factor)
        # Re-verify and write back updated literal state without standard variable compression
        self.fs.assign_state(
            1,
            f"/sys/{self.name.lower()}/meta",
            f"SYSTEM_NAME:{self.name}|CAPACITY:{self.capacity_tbi}TBi|DEPTH:{self.depth}"
        )
        for mirror in self.mirrors.values():
            mirror.scale_capacity(factor)

    def double_capacity(self) -> None:
        """
        Double the system capacity and recursively update nested systems.
        
        Re-verifies and writes back updated literal state without standard
        variable compression. Recursively doubles nested systems if present.
        """
        self.scale_capacity(2.0)
    
    def run_structural_audit(self) -> List[str]:
        """
        Run a complete structural audit of the system and nested layers.
        
        Returns:
            List of audit log entries for this system and nested systems.
            Checks that no cartesian zero exists in cell alignment.
        """
        logs: List[str] = []
        # Audit parent layer
        for signed_idx, cell in self.fs.storage_cells.items():
            if signed_idx == 0:
                logs.append(
                    f"[{self.name}] CRITICAL EXCEPTION: Cartesian zero detected in cell alignment."
                )
            else:
                logs.append(
                    f"[{self.name}] AUDIT PASS -> Relational Index ({signed_idx}) maps safely to path '{cell['path']}'."
                )
        
        # Recursively audit child layer
        for mirror in self.mirrors.values():
            logs.extend(mirror.run_structural_audit())
        return logs

    def get_system_report(self) -> Dict[str, Any]:
        """
        Generate a complete deep recursive status report of the hierarchy.
        
        Returns:
            Dictionary containing nested runtime structural status.
        """
        return {
            "name": self.name,
            "capacity_tbi": self.capacity_tbi,
            "depth": self.depth,
            "status": self.fs.fetch_state(2).get("data", "UNKNOWN"),
            "filesystem_integrity": self.fs.verify_integrity(),
            "active_cells_count": len(self.fs.storage_cells),
            "mirrors": {name: mirror.get_system_report() for name, mirror in self.mirrors.items()}
        }

    def capture_snapshot(self) -> Dict[str, Any]:
        """
        Capture a deep, recursive state snapshot of the entire runtime tree.
        
        Returns:
            A snapshot dictionary ready for backup or serialization.
        """
        return {
            "name": self.name,
            "capacity_tbi": self.capacity_tbi,
            "depth": self.depth,
            "storage_cells": {
                str(idx): {
                    "path": cell["path"],
                    "data": cell["data"],
                    "hash": cell["hash"]
                }
                for idx, cell in self.fs.storage_cells.items()
            },
            "mirrors": {name: mirror.capture_snapshot() for name, mirror in self.mirrors.items()}
        }

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Deeply restore the entire runtime tree state from a captured snapshot,
        re-verifying integrity of all cell hashes.
        
        Args:
            snapshot: Snapshot dictionary previously generated by capture_snapshot.
            
        Raises:
            ValueError: If integrity verification fails on restoration or structure mismatch.
        """
        if snapshot.get("name") != self.name:
            raise ValueError(f"Snapshot name mismatch. Expected '{self.name}', got '{snapshot.get('name')}'")
            
        self.capacity_tbi = snapshot["capacity_tbi"]
        self.depth = snapshot["depth"]
        
        # Re-populate filesystem
        self.fs.clear_state()
        for idx_str, cell_data in snapshot["storage_cells"].items():
            idx = int(idx_str)
            # Re-compute hash to verify integrity
            computed_hash = hashlib.sha256(cell_data["data"].encode('utf-8')).hexdigest()
            if computed_hash != cell_data["hash"]:
                raise ValueError(f"Integrity check failed during snapshot restore for cell {idx}. Data has been corrupted.")
            
            self.fs.storage_cells[idx] = {
                "path": cell_data["path"],
                "data": cell_data["data"],
                "hash": cell_data["hash"]
            }
            
        # Re-populate and restore mirrors
        snapshot_mirrors = snapshot.get("mirrors", {})
        # Clear mirrors that are not in snapshot
        self.mirrors = {name: m for name, m in self.mirrors.items() if name in snapshot_mirrors}
        
        for name, mirror_snapshot in snapshot_mirrors.items():
            if name not in self.mirrors:
                # Create a temporary empty mirror shell and let it restore itself
                self.mirrors[name] = NestedCoreRuntime(name, mirror_snapshot["capacity_tbi"], depth=mirror_snapshot["depth"])
            self.mirrors[name].restore_snapshot(mirror_snapshot)
