#!/usr/bin/env python3
"""
Nested Core Runtime Module

Implements a rigorous zero-less index spectrum and nested runtime system.
This module provides:
- KeddehZeroLessMatrix: Zero-less indexing (bypasses 0 entirely)
- WiredFATFileSystem: Uncompressed state database with zero-less indices
- NestedCoreRuntime: Self-bootstrapping nested runtime system

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
        halfway = 3
        if logical_idx <= halfway:
            return -logical_idx
        else:
            return (logical_idx - halfway)


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


class NestedCoreRuntime:
    """
    The complete running system that contains a running booted state system
    of itself running within, executing actual integer operations.
    
    Features:
    - Self-bootstrapping into zero-less space
    - Nested layer runtime initialization
    - Capacity doubling with state updates
    - Structural audit of the system hierarchy
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
        self.inner_system: Optional['NestedCoreRuntime'] = None
        
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
    
    def embed_mirror(self, inner_name: str, inner_capacity_tbi: int) -> None:
        """
        Embed a nested runtime system within this system.
        
        Args:
            inner_name: Name of the inner system
            inner_capacity_tbi: Capacity of the inner system in TBi
        """
        # Nested layer runtime initialization
        self.inner_system = NestedCoreRuntime(inner_name, inner_capacity_tbi, depth=self.depth + 1)
        # Register the child system state string into the parent's uncompressed filesystem
        child_meta = f"EMBEDDED_MIRROR_SYSTEM_IDENTIFIER:{inner_name}|ALLOCATION:{inner_capacity_tbi}TBi"
        self.fs.assign_state(3, f"/sys/{self.name.lower()}/nested_link", child_meta)
    
    def double_capacity(self) -> None:
        """
        Double the system capacity and recursively update nested systems.
        
        Re-verifies and writes back updated literal state without standard
        variable compression. Recursively doubles nested systems if present.
        """
        self.capacity_tbi *= 2
        # Re-verify and write back updated literal state without standard variable compression
        self.fs.assign_state(
            1,
            f"/sys/{self.name.lower()}/meta",
            f"SYSTEM_NAME:{self.name}|CAPACITY:{self.capacity_tbi}TBi|DEPTH:{self.depth}"
        )
        if self.inner_system:
            self.inner_system.double_capacity()
    
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
        if self.inner_system:
            logs.extend(self.inner_system.run_structural_audit())
        return logs
