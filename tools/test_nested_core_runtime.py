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
            
    def test_get_logical_index_mapping(self):
        """Test conversion from signed index back to logical index."""
        assert KeddehZeroLessMatrix.get_logical_index(-1) == 1
        assert KeddehZeroLessMatrix.get_logical_index(-2) == 2
        assert KeddehZeroLessMatrix.get_logical_index(-3) == 3
        assert KeddehZeroLessMatrix.get_logical_index(1) == 4
        assert KeddehZeroLessMatrix.get_logical_index(2) == 5
        assert KeddehZeroLessMatrix.get_logical_index(97) == 100

    def test_get_logical_index_rejects_zero(self):
        """Test that get_logical_index raises ValueError for 0."""
        try:
            KeddehZeroLessMatrix.get_logical_index(0)
            assert False, "Should have raised ValueError for signed index 0"
        except ValueError as e:
            assert "Cartesian zero detected" in str(e)

    def test_get_logical_index_rejects_out_of_bounds(self):
        """Test that get_logical_index rejects negative indices smaller than -3."""
        try:
            KeddehZeroLessMatrix.get_logical_index(-4)
            assert False, "Should have raised ValueError for -4"
        except ValueError as e:
            assert "out of bounds" in str(e)

    def test_get_logical_index_unbounded_positive(self):
        """Test that get_logical_index has no upper limit on positive signed indices."""
        # Confirming positive spectrum supports arbitrarily large integer indices
        large_signed = 1000000
        expected_logical = large_signed + 3
        assert KeddehZeroLessMatrix.get_logical_index(large_signed) == expected_logical

    def test_shift_index_bypasses_zero(self):
        """Test index shifting with step-aware bypassing of 0."""
        # Shift from negative to negative (no zero crossing)
        assert KeddehZeroLessMatrix.shift_index(-3, 1) == -2
        assert KeddehZeroLessMatrix.shift_index(-2, -1) == -3
        
        # Shift with zero crossing
        assert KeddehZeroLessMatrix.shift_index(-1, 1) == 1
        assert KeddehZeroLessMatrix.shift_index(1, -1) == -1
        assert KeddehZeroLessMatrix.shift_index(-2, 3) == 2
        assert KeddehZeroLessMatrix.shift_index(2, -3) == -2
        
        # Zero steps
        assert KeddehZeroLessMatrix.shift_index(5, 0) == 5

    def test_shift_index_rejects_zero(self):
        """Test that shifting from zero index raises ValueError."""
        try:
            KeddehZeroLessMatrix.shift_index(0, 1)
            assert False, "Should raise error starting from zero"
        except ValueError as e:
            assert "Cannot shift from Cartesian zero" in str(e)


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

    def test_delete_state(self):
        """Test deleting a state cell."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/path1", "data1")
        assert fs.fetch_state(1)["data"] == "data1"
        
        fs.delete_state(1)
        assert fs.fetch_state(1)["data"] == ""
        assert fs.fetch_state(1)["path"] == "VOID"

    def test_list_states(self):
        """Test listing all states in sorted signed index order."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/path1", "data1")
        fs.assign_state(4, "/path4", "data4")
        fs.assign_state(2, "/path2", "data2")
        
        states = fs.list_states()
        assert len(states) == 3
        # Sorted signed indices: -2, -1, 1
        assert states[0]["signed_index"] == -2
        assert states[1]["signed_index"] == -1
        assert states[2]["signed_index"] == 1

    def test_verify_integrity(self):
        """Test integrity validation on storage cells."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/path1", "data1")
        assert fs.verify_integrity() is True
        
        # Manually corrupt data
        fs.storage_cells[-1]["data"] = "corrupted_data"
        assert fs.verify_integrity() is False

    def test_export_state_manifest(self):
        """Test exporting manifest metadata."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/path1", "data1")
        
        manifest = fs.export_state_manifest()
        assert "-1" in manifest
        assert manifest["-1"]["path"] == "/path1"
        assert manifest["-1"]["size_bytes"] == 5

    def test_clear_state(self):
        """Test clearing the filesystem cells."""
        fs = WiredFATFileSystem()
        fs.assign_state(1, "/path1", "data1")
        fs.assign_state(2, "/path2", "data2")
        assert len(fs.storage_cells) == 2
        
        fs.clear_state()
        assert len(fs.storage_cells) == 0


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
        system = NestedCoreRuntime("BOOT_TEST", base_capacity_tbi=5000)
        
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

    def test_multiple_mirrors(self):
        """Test embedding multiple concurrent nested mirror systems."""
        parent = NestedCoreRuntime("PARENT_MULTI", 10000)
        parent.embed_mirror("CHILD_X", 3000)
        parent.embed_mirror("CHILD_Y", 4000)
        
        assert len(parent.mirrors) == 2
        assert "CHILD_X" in parent.mirrors
        assert "CHILD_Y" in parent.mirrors
        assert parent.inner_system.name == "CHILD_X"  # first mirror is inner_system for backward compatibility
        
        # Verify both are registered with unique paths and correct indexing in parent filesystem
        state_x = parent.fs.fetch_state(3)
        state_y = parent.fs.fetch_state(4)
        assert state_x["path"] == "/sys/parent_multi/nested_link/child_x"
        assert state_y["path"] == "/sys/parent_multi/nested_link/child_y"
        assert "CHILD_X" in state_x["data"]
        assert "CHILD_Y" in state_y["data"]

    def test_scale_capacity(self):
        """Test recursive capacity scaling with custom floating factors."""
        parent = NestedCoreRuntime("PARENT_SCALE", 10000)
        parent.embed_mirror("CHILD_SCALE", 5000)
        
        parent.scale_capacity(1.5)
        assert parent.capacity_tbi == 15000
        assert parent.inner_system.capacity_tbi == 7500
        
        try:
            parent.scale_capacity(-1.0)
            assert False, "Should reject negative scaling factor"
        except ValueError as e:
            assert "strictly positive" in str(e)

    def test_get_system_report(self):
        """Test generating deep recursive health and status reports."""
        parent = NestedCoreRuntime("PARENT_REP", 10000)
        parent.embed_mirror("CHILD_REP", 5000)
        
        report = parent.get_system_report()
        assert report["name"] == "PARENT_REP"
        assert report["capacity_tbi"] == 10000
        assert report["filesystem_integrity"] is True
        assert "CHILD_REP" in report["mirrors"]
        assert report["mirrors"]["CHILD_REP"]["capacity_tbi"] == 5000

    def test_capture_and_restore_snapshot(self):
        """Test capturing and restoring deep system state snapshots."""
        parent = NestedCoreRuntime("PARENT_SNAP", 10000)
        parent.embed_mirror("CHILD_SNAP", 5000)
        
        # Write some extra states
        parent.fs.assign_state(4, "/extra/parent", "parent_custom_state")
        parent.inner_system.fs.assign_state(4, "/extra/child", "child_custom_state")
        
        # Capture snapshot
        snapshot = parent.capture_snapshot()
        
        # Perform some modifications/updates
        parent.double_capacity()
        parent.fs.assign_state(4, "/extra/parent", "modified_parent_state")
        parent.inner_system.fs.assign_state(4, "/extra/child", "modified_child_state")
        
        # Restore from snapshot
        parent.restore_snapshot(snapshot)
        
        # Verify states restored to original
        assert parent.capacity_tbi == 10000
        assert parent.inner_system.capacity_tbi == 5000
        assert parent.fs.fetch_state(4)["data"] == "parent_custom_state"
        assert parent.inner_system.fs.fetch_state(4)["data"] == "child_custom_state"


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
