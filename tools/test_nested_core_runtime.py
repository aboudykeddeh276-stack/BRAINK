#!/usr/bin/env python3
"""
Comprehensive test suite for NestedCoreRuntime module.

Tests the following components:
- KeddehZeroLessMatrix: Zero-less indexing
- WiredFATFileSystem: State storage with zero-less indices
- NestedCoreRuntime: Self-bootstrapping nested systems
"""

import sys
import hashlib
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "modules"))

from NestedCoreRuntime import KeddehZeroLessMatrix, WiredFATFileSystem, NestedCoreRuntime


class TestKeddehZeroLessMatrix:
    """Test suite for KeddehZeroLessMatrix."""
    
    def test_get_signed_index_negative_mapping(self):
        """Test that logical indices 1-3 map to negative signed indices."""
        assert KeddehZeroLessMatrix.get_signed_index(1) == -1
        assert KeddehZeroLessMatrix.get_signed_index(2) == -2
        assert KeddehZeroLessMatrix.get_signed_index(3) == -3
    
    def test_get_signed_index_positive_mapping(self):
        """Test that logical indices 4+ map to positive signed indices."""
        assert KeddehZeroLessMatrix.get_signed_index(4) == 1
        assert KeddehZeroLessMatrix.get_signed_index(5) == 2
        assert KeddehZeroLessMatrix.get_signed_index(6) == 3
        assert KeddehZeroLessMatrix.get_signed_index(7) == 4
        assert KeddehZeroLessMatrix.get_signed_index(100) == 97
    
    def test_get_signed_index_rejects_zero(self):
        """Test that logical index 0 raises ValueError."""
        try:
            KeddehZeroLessMatrix.get_signed_index(0)
            assert False, "Should have raised ValueError for index 0"
        except ValueError as e:
            assert "Zero or negative logical indices strictly outlawed" in str(e)
    
    def test_get_signed_index_rejects_negative(self):
        """Test that negative logical indices raise ValueError."""
        try:
            KeddehZeroLessMatrix.get_signed_index(-1)
            assert False, "Should have raised ValueError for negative index"
        except ValueError as e:
            assert "Zero or negative logical indices strictly outlawed" in str(e)
    
    def test_no_zero_in_spectrum(self):
        """Verify that the spectrum never produces zero."""
        for logical_idx in range(1, 1000):
            signed_idx = KeddehZeroLessMatrix.get_signed_index(logical_idx)
            assert signed_idx != 0, f"Zero found in spectrum at logical index {logical_idx}"


class TestWiredFATFileSystem:
    """Test suite for WiredFATFileSystem."""
    
    def test_assign_and_fetch_state(self):
        """Test basic assign and fetch operations."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/sys/test/path", "test_data_content")
        
        state = fs.fetch_state(1)
        assert state["path"] == "/sys/test/path"
        assert state["data"] == "test_data_content"
        assert isinstance(state["hash"], str)
        assert len(state["hash"]) == 64  # SHA256 hex length
    
    def test_hash_computation(self):
        """Test that hashes are correctly computed."""
        fs = WiredFATFileSystem()
        test_data = "deterministic_test_string"
        fs.assign_state(1, "/path", test_data)
        
        expected_hash = hashlib.sha256(test_data.encode('utf-8')).hexdigest()
        state = fs.fetch_state(1)
        assert state["hash"] == expected_hash
    
    def test_fetch_nonexistent_returns_void(self):
        """Test that fetching non-existent index returns void entry."""
        fs = WiredFATFileSystem()
        state = fs.fetch_state(99)
        
        assert state["path"] == "VOID"
        assert state["data"] == ""
        assert state["hash"] == ""
    
    def test_multiple_cells_storage(self):
        """Test storing and retrieving from multiple cells."""
        fs = WiredFATFileSystem()
        
        fs.assign_state(1, "/path1", "data1")
        fs.assign_state(2, "/path2", "data2")
        fs.assign_state(3, "/path3", "data3")
        
        assert fs.fetch_state(1)["data"] == "data1"
        assert fs.fetch_state(2)["data"] == "data2"
        assert fs.fetch_state(3)["data"] == "data3"
    
    def test_overwrite_cell(self):
        """Test overwriting an existing cell."""
        fs = WiredFATFileSystem()
        
        fs.assign_state(1, "/path1", "original_data")
        fs.assign_state(1, "/path1", "updated_data")
        
        state = fs.fetch_state(1)
        assert state["data"] == "updated_data"
        assert state["path"] == "/path1"


class TestNestedCoreRuntime:
    """Test suite for NestedCoreRuntime."""
    
    def test_initialization(self):
        """Test basic system initialization."""
        system = NestedCoreRuntime("TEST_SYSTEM", 1000)
        
        assert system.name == "TEST_SYSTEM"
        assert system.capacity_tbi == 1000
        assert system.depth == 1
        assert system.inner_system is None
    
    def test_bootstrap_state_creation(self):
        """Test that bootstrap creates initial state entries."""
        system = NestedCoreRuntime("BOOT_TEST", 5000, depth=1)
        
        # Check that states are bootstrapped
        meta_state = system.fs.fetch_state(1)
        status_state = system.fs.fetch_state(2)
        
        assert "BOOT_TEST" in meta_state["data"]
        assert "5000TBi" in meta_state["data"]
        assert "BOOTED_STABLE" in status_state["data"]
    
    def test_embed_mirror(self):
        """Test embedding a nested system."""
        parent = NestedCoreRuntime("PARENT", 10000)
        parent.embed_mirror("CHILD", 5000)
        
        assert parent.inner_system is not None
        assert parent.inner_system.name == "CHILD"
        assert parent.inner_system.capacity_tbi == 5000
        assert parent.inner_system.depth == 2
        
        # Check that nested link is registered
        nested_link = parent.fs.fetch_state(3)
        assert "EMBEDDED_MIRROR_SYSTEM_IDENTIFIER:CHILD" in nested_link["data"]
    
    def test_double_capacity(self):
        """Test capacity doubling."""
        system = NestedCoreRuntime("CAPACITY_TEST", 1000)
        
        original_capacity = system.capacity_tbi
        system.double_capacity()
        
        assert system.capacity_tbi == original_capacity * 2
        assert system.capacity_tbi == 2000
    
    def test_double_capacity_updates_state(self):
        """Test that double_capacity updates the filesystem state."""
        system = NestedCoreRuntime("STATE_UPDATE_TEST", 1000)
        system.double_capacity()
        
        meta_state = system.fs.fetch_state(1)
        assert "2000TBi" in meta_state["data"]
    
    def test_double_capacity_nested(self):
        """Test that double_capacity affects nested systems."""
        parent = NestedCoreRuntime("PARENT_CAP", 10000)
        parent.embed_mirror("CHILD_CAP", 5000)
        
        parent.double_capacity()
        
        assert parent.capacity_tbi == 20000
        assert parent.inner_system.capacity_tbi == 10000
    
    def test_structural_audit_single_system(self):
        """Test structural audit on single system."""
        system = NestedCoreRuntime("AUDIT_TEST", 1000)
        audit_logs = system.run_structural_audit()
        
        assert len(audit_logs) >= 2  # At least meta and status entries
        for log in audit_logs:
            assert "AUDIT PASS" in log or "CRITICAL EXCEPTION" in log
            assert "[AUDIT_TEST]" in log
    
    def test_structural_audit_nested_systems(self):
        """Test structural audit on nested systems."""
        parent = NestedCoreRuntime("PARENT_AUDIT", 10000)
        parent.embed_mirror("CHILD_AUDIT", 5000)
        
        audit_logs = parent.run_structural_audit()
        
        # Should have entries for both parent and child
        parent_entries = [log for log in audit_logs if "[PARENT_AUDIT]" in log]
        child_entries = [log for log in audit_logs if "[CHILD_AUDIT]" in log]
        
        assert len(parent_entries) > 0
        assert len(child_entries) > 0
    
    def test_no_zero_in_audit(self):
        """Test that structural audit never encounters zero index."""
        system = NestedCoreRuntime("ZERO_TEST", 1000)
        audit_logs = system.run_structural_audit()
        
        # Verify no critical exceptions for zero
        zero_exceptions = [log for log in audit_logs if "Cartesian zero detected" in log]
        assert len(zero_exceptions) == 0


class TestIntegrationScenarios:
    """Integration tests for complete workflow scenarios."""
    
    def test_complete_workflow_scenario(self):
        """
        Test the complete workflow from the issue description.
        
        1. Establish Master System at 10,000 TBi baseline
        2. Embed the nested system running within at 5,000 TBi baseline
        3. Capture Initial State Details
        4. Execute the command to test capacity and then DOUBLE it
        5. Capture Post-Expansion State Details
        6. Run the complete integer structural audit
        """
        # 1. Establish Master System at 10,000 TBi baseline
        master_system = NestedCoreRuntime("HOST_PARENT_CORE_A", base_capacity_tbi=10000)
        
        # 2. Embed the nested system running within at 5,000 TBi baseline
        master_system.embed_mirror("NESTED_CHILD_CORE_B", inner_capacity_tbi=5000)
        
        # 3. Capture Initial State Details
        initial_parent_meta = master_system.fs.fetch_state(1)["data"]
        initial_child_meta = master_system.inner_system.fs.fetch_state(1)["data"]
        
        assert "10000TBi" in initial_parent_meta
        assert "5000TBi" in initial_child_meta
        
        # 4. Execute the command to test capacity and then DOUBLE it
        master_system.double_capacity()
        
        # 5. Capture Post-Expansion State Details
        post_parent_meta = master_system.fs.fetch_state(1)["data"]
        post_child_meta = master_system.inner_system.fs.fetch_state(1)["data"]
        
        assert "20000TBi" in post_parent_meta
        assert "10000TBi" in post_child_meta
        
        # 6. Run the complete integer structural audit
        audit_results = master_system.run_structural_audit()
        
        assert len(audit_results) > 0
        # Verify no cartesian zero errors
        zero_errors = [r for r in audit_results if "CRITICAL EXCEPTION" in r]
        assert len(zero_errors) == 0
        
        print(f"\n✓ Complete workflow scenario passed")
        print(f"  - Initial Parent:  {initial_parent_meta}")
        print(f"  - Initial Child:   {initial_child_meta}")
        print(f"  - Post Parent:     {post_parent_meta}")
        print(f"  - Post Child:      {post_child_meta}")
        print(f"  - Audit entries:   {len(audit_results)}")


def run_all_tests():
    """Run all test classes and report results."""
    test_classes = [
        TestKeddehZeroLessMatrix,
        TestWiredFATFileSystem,
        TestNestedCoreRuntime,
        TestIntegrationScenarios,
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    print("\n" + "="*70)
    print("NESTED CORE RUNTIME - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        print("-" * 70)
        
        test_instance = test_class()
        test_methods = [m for m in dir(test_instance) if m.startswith("test_")]
        
        for test_method in test_methods:
            total_tests += 1
            try:
                getattr(test_instance, test_method)()
                print(f"  ✓ {test_method}")
                passed_tests += 1
            except Exception as e:
                print(f"  ✗ {test_method}: {str(e)}")
                failed_tests += 1
    
    print("\n" + "="*70)
    print(f"TEST RESULTS: {passed_tests}/{total_tests} passed, {failed_tests} failed")
    print("="*70 + "\n")
    
    return failed_tests == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
