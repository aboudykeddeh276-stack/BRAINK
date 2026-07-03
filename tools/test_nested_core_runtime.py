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


class TestAgentFleet:
    """Test suite for the agent fleet extension of NestedCoreRuntime."""

    def test_embed_agent_creates_typed_mirror(self):
        """embed_agent creates a mirror with 6 state cells: meta, status, role, constraints, inbox, result."""
        host = NestedCoreRuntime("HOST", 10000)
        agent = host.embed_agent("AGENT_ALPHA", role="PROOF_WORKER", capacity_tbi=2000)

        assert agent.name == "AGENT_ALPHA"
        assert agent.capacity_tbi == 2000
        assert agent.depth == 2

        # Standard bootstrap cells
        assert "AGENT_ALPHA" in agent.fs.fetch_state(1)["data"]
        assert agent.fs.fetch_state(2)["data"] == "BOOTED_STABLE"

        # Agent-typed cells
        assert "AGENT_ROLE:PROOF_WORKER" in agent.fs.fetch_state(3)["data"]
        assert "CONSTRAINT_KEX_LANE" in agent.fs.fetch_state(4)["data"]
        assert "TASK_STATUS:WAITING" in agent.fs.fetch_state(5)["data"]
        assert "RESULT_STATUS:WAITING" in agent.fs.fetch_state(6)["data"]

    def test_embed_agent_registers_in_host_fs(self):
        """embed_agent writes an agent-link cell into the host's zero-less FS."""
        host = NestedCoreRuntime("HOST_FS_TEST", 10000)
        host.embed_agent("AGENT_BETA", role="AUDIT_WORKER", capacity_tbi=1000)

        # Host registers the link at logical index 3 (first mirror slot)
        link_cell = host.fs.fetch_state(3)
        assert "AGENT_MIRROR_IDENTIFIER:AGENT_BETA" in link_cell["data"]
        assert "ROLE:AUDIT_WORKER" in link_cell["data"]

    def test_embed_agent_rejects_duplicate_name(self):
        """embed_agent raises ValueError if agent name already exists."""
        host = NestedCoreRuntime("HOST_DUP", 10000)
        host.embed_agent("AGENT_X", role="WORKER", capacity_tbi=500)
        try:
            host.embed_agent("AGENT_X", role="WORKER_2", capacity_tbi=500)
            assert False, "Should have raised ValueError for duplicate agent"
        except ValueError as e:
            assert "AGENT_X" in str(e)
            assert "already exists" in str(e)

    def test_embed_multiple_agents_unique_indices(self):
        """Multiple agents each receive unique parent FS link indices."""
        host = NestedCoreRuntime("HOST_MULTI_AGENT", 10000)
        host.embed_agent("AGENT_1", role="ROLE_A", capacity_tbi=1000)
        host.embed_agent("AGENT_2", role="ROLE_B", capacity_tbi=2000)
        host.embed_agent("AGENT_3", role="ROLE_C", capacity_tbi=3000)

        assert len(host.mirrors) == 3

        link_3 = host.fs.fetch_state(3)["data"]
        link_4 = host.fs.fetch_state(4)["data"]
        link_5 = host.fs.fetch_state(5)["data"]

        assert "AGENT_1" in link_3
        assert "AGENT_2" in link_4
        assert "AGENT_3" in link_5

    def test_clone_as_package_produces_independent_copy(self):
        """clone_as_package creates a fully independent system with no shared state."""
        original = NestedCoreRuntime("ORIGINAL_HOST", 10000)
        original.embed_agent("AGENT_IN_ORIGINAL", role="ANALYST", capacity_tbi=2000)

        clone = original.clone_as_package("CLONE_HOST")

        # New identity
        assert clone.name == "CLONE_HOST"
        assert "CLONE_HOST" in clone.fs.fetch_state(1)["data"]
        assert "CLONED_FROM:ORIGINAL_HOST" in clone.fs.fetch_state(1)["data"]

        # Structural copy: same capacity, same depth, same agent set
        assert clone.capacity_tbi == original.capacity_tbi
        assert clone.depth == original.depth
        assert "AGENT_IN_ORIGINAL" in clone.mirrors

        # Independence: mutate original, clone is unaffected
        original.double_capacity()
        assert clone.capacity_tbi != original.capacity_tbi

        # Independence: mutate clone, original is unaffected
        clone.embed_agent("CLONE_ONLY_AGENT", role="CLONE_WORKER", capacity_tbi=500)
        assert "CLONE_ONLY_AGENT" not in original.mirrors

    def test_clone_as_package_rejects_same_name(self):
        """clone_as_package raises ValueError if new_name equals source name."""
        host = NestedCoreRuntime("SAME_NAME_HOST", 5000)
        try:
            host.clone_as_package("SAME_NAME_HOST")
            assert False, "Should have raised ValueError for identical name"
        except ValueError as e:
            assert "SAME_NAME_HOST" in str(e)

    def test_clone_filesystem_integrity(self):
        """clone_as_package produces a clone with intact SHA256 hashes."""
        original = NestedCoreRuntime("INTEGRITY_ORIGIN", 8000)
        original.embed_agent("WORKER_A", role="WORKER", capacity_tbi=1000)
        original.embed_agent("WORKER_B", role="WORKER", capacity_tbi=1000)

        clone = original.clone_as_package("INTEGRITY_CLONE")

        assert clone.fs.verify_integrity() is True
        for agent in clone.mirrors.values():
            assert agent.fs.verify_integrity() is True

    def test_dispatch_to_agent_completes_task(self):
        """dispatch_to_agent writes payload, runs audit, writes result, restores status."""
        host = NestedCoreRuntime("DISPATCH_HOST", 10000)
        host.embed_agent("DISPATCH_AGENT", role="PROOF_WORKER", capacity_tbi=2000)

        result = host.dispatch_to_agent("DISPATCH_AGENT", "TASK:VALIDATE_ZERO_LESS_SPECTRUM")

        assert result["agent"] == "DISPATCH_AGENT"
        assert result["task_payload"] == "TASK:VALIDATE_ZERO_LESS_SPECTRUM"
        assert result["status"] == "TASK_COMPLETED"
        assert result["zero_errors"] == 0
        assert len(result["audit_entries"]) > 0
        assert result["integrity_pre_dispatch"] is True
        assert "TASK_COMPLETED" in result["result_cell"]

        # Agent status restored to BOOTED_STABLE after dispatch
        agent = host.mirrors["DISPATCH_AGENT"]
        assert agent.fs.fetch_state(2)["data"] == "BOOTED_STABLE"

        # Task inbox records the payload
        inbox = agent.fs.fetch_state(5)["data"]
        assert "TASK:VALIDATE_ZERO_LESS_SPECTRUM" in inbox

    def test_dispatch_to_agent_raises_on_missing_agent(self):
        """dispatch_to_agent raises KeyError for unknown agent name."""
        host = NestedCoreRuntime("DISPATCH_KEYERROR_HOST", 5000)
        try:
            host.dispatch_to_agent("NONEXISTENT", "TASK:ANYTHING")
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "NONEXISTENT" in str(e)

    def test_dispatch_sequential_tasks_to_same_agent(self):
        """Sequential dispatches to the same agent each complete cleanly."""
        host = NestedCoreRuntime("SEQUENTIAL_HOST", 10000)
        host.embed_agent("SEQ_AGENT", role="SEQUENTIAL_WORKER", capacity_tbi=3000)

        for i in range(1, 4):
            result = host.dispatch_to_agent("SEQ_AGENT", f"TASK:STEP_{i}")
            assert result["status"] == "TASK_COMPLETED"
            assert result["zero_errors"] == 0

        # Final status is stable
        assert host.mirrors["SEQ_AGENT"].fs.fetch_state(2)["data"] == "BOOTED_STABLE"

    def test_dispatch_to_multiple_agents_independently(self):
        """Tasks dispatched to different agents do not interfere with each other."""
        host = NestedCoreRuntime("MULTI_DISPATCH_HOST", 10000)
        host.embed_agent("ALPHA", role="ROLE_ALPHA", capacity_tbi=2000)
        host.embed_agent("BETA", role="ROLE_BETA", capacity_tbi=2000)
        host.embed_agent("GAMMA", role="ROLE_GAMMA", capacity_tbi=2000)

        result_alpha = host.dispatch_to_agent("ALPHA", "TASK:ALPHA_WORK")
        result_beta = host.dispatch_to_agent("BETA", "TASK:BETA_WORK")
        result_gamma = host.dispatch_to_agent("GAMMA", "TASK:GAMMA_WORK")

        for result in (result_alpha, result_beta, result_gamma):
            assert result["status"] == "TASK_COMPLETED"
            assert result["zero_errors"] == 0

        # Each agent's inbox holds its own payload
        assert "TASK:ALPHA_WORK" in host.mirrors["ALPHA"].fs.fetch_state(5)["data"]
        assert "TASK:BETA_WORK" in host.mirrors["BETA"].fs.fetch_state(5)["data"]
        assert "TASK:GAMMA_WORK" in host.mirrors["GAMMA"].fs.fetch_state(5)["data"]

    def test_get_agent_fleet_report_structure(self):
        """get_agent_fleet_report returns a complete hierarchical report."""
        host = NestedCoreRuntime("FLEET_HOST", 10000)
        host.embed_agent("FLEET_AGENT_A", role="ANALYST", capacity_tbi=1000)
        host.embed_agent("FLEET_AGENT_B", role="AUDITOR", capacity_tbi=1500)
        host.dispatch_to_agent("FLEET_AGENT_A", "TASK:FLEET_PROOF")

        report = host.get_agent_fleet_report()

        assert report["host"] == "FLEET_HOST"
        assert report["total_agents"] == 2
        assert "FLEET_AGENT_A" in report["fleet"]
        assert "FLEET_AGENT_B" in report["fleet"]

        agent_a = report["fleet"]["FLEET_AGENT_A"]
        assert "ANALYST" in agent_a["role"]
        assert agent_a["capacity_tbi"] == 1000
        assert agent_a["depth"] == 2
        assert agent_a["status"] == "BOOTED_STABLE"
        assert agent_a["filesystem_integrity"] is True
        assert "TASK_COMPLETED" in agent_a["last_result"]

    def test_full_agent_fleet_clone_and_dispatch(self):
        """
        Integration: build a full fleet, clone the outer system as a package,
        deploy the clone independently, dispatch tasks to all agents in both.
        """
        # Build original fleet
        original = NestedCoreRuntime("FLEET_ORIGINAL", 20000)
        original.embed_agent("PROOF_AGENT", role="PROOF_WORKER", capacity_tbi=4000)
        original.embed_agent("AUDIT_AGENT", role="AUDIT_WORKER", capacity_tbi=4000)
        original.embed_agent("SYNC_AGENT", role="SYNC_WORKER", capacity_tbi=4000)

        # Clone the full outer system as an isolated package
        clone = original.clone_as_package("FLEET_CLONE")

        # Both host and clone have independent agent fleets
        assert len(original.mirrors) == 3
        assert len(clone.mirrors) == 3
        assert clone.name == "FLEET_CLONE"

        # Dispatch to original fleet
        for agent_name in list(original.mirrors.keys()):
            result = original.dispatch_to_agent(agent_name, f"TASK:ORIGINAL_{agent_name}")
            assert result["status"] == "TASK_COMPLETED"

        # Dispatch to clone fleet independently
        for agent_name in list(clone.mirrors.keys()):
            result = clone.dispatch_to_agent(agent_name, f"TASK:CLONE_{agent_name}")
            assert result["status"] == "TASK_COMPLETED"

        # Clone fleet reports are structurally identical but carry clone payloads
        original_report = original.get_agent_fleet_report()
        clone_report = clone.get_agent_fleet_report()

        assert original_report["host"] == "FLEET_ORIGINAL"
        assert clone_report["host"] == "FLEET_CLONE"
        assert original_report["total_agents"] == clone_report["total_agents"]

        # No zero errors anywhere in either tree
        for agent_name in original.mirrors:
            assert original_report["fleet"][agent_name]["filesystem_integrity"] is True
        for agent_name in clone.mirrors:
            assert clone_report["fleet"][agent_name]["filesystem_integrity"] is True

        # Verify structural audit on both full trees is clean
        original_audit = original.run_structural_audit()
        clone_audit = clone.run_structural_audit()
        assert not any("CRITICAL" in e for e in original_audit)
        assert not any("CRITICAL" in e for e in clone_audit)


def run_all_tests():
    """Run all test classes and report results."""
    test_classes = [
        TestKeddehZeroLessMatrix,
        TestWiredFATFileSystem,
        TestNestedCoreRuntime,
        TestIntegrationScenarios,
        TestAgentFleet,
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

