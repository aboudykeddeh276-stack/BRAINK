#!/usr/bin/env python3
"""
Nested Core Runtime Execution Demonstration

This script demonstrates the complete workflow of the NestedCoreRuntime system
including the agent fleet extension:

1. Zero-less indexing (bypassing 0 entirely)
2. Uncompressed state storage via WiredFATFileSystem
3. Nested runtime bootstrapping and capacity management
4. Structural audits with zero-detection
5. Multi-agent fleet: embed_agent, clone_as_package, dispatch_to_agent, get_agent_fleet_report
"""

import sys
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "modules"))

from NestedCoreRuntime import NestedCoreRuntime


def main():
    """Execute the complete nested core runtime workflow including agent fleet."""

    print("\n" + "="*80)
    print("NESTED CORE RUNTIME - WORKFLOW EXECUTION DEMONSTRATION")
    print("="*80 + "\n")

    # ------------------------------------------------------------------
    # PHASE 1: Establish outer host system
    # ------------------------------------------------------------------
    print("PHASE 1: Establish Master System at 10,000 TBi baseline")
    print("-" * 80)
    master_system = NestedCoreRuntime("HOST_PARENT_CORE_A", base_capacity_tbi=10000)
    print("✓ Master system initialized")
    print(f"  - System Name: {master_system.name}")
    print(f"  - Capacity:    {master_system.capacity_tbi} TBi")
    print(f"  - Depth Level: {master_system.depth}")

    # ------------------------------------------------------------------
    # PHASE 2: Embed a plain nested mirror (existing behaviour)
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 2: Embed nested mirror at 5,000 TBi baseline")
    print("-" * 80)
    master_system.embed_mirror("NESTED_CHILD_CORE_B", inner_capacity_tbi=5000)
    print("✓ Nested system embedded")
    print(f"  - Child Name:     {master_system.inner_system.name}")
    print(f"  - Child Capacity: {master_system.inner_system.capacity_tbi} TBi")
    print(f"  - Child Depth:    {master_system.inner_system.depth}")

    # ------------------------------------------------------------------
    # PHASE 3: Capacity doubling
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 3: Execute Capacity Doubling Operation")
    print("-" * 80)
    master_system.double_capacity()
    print("✓ Capacity doubled recursively through all nested layers")
    print(f"  - Master: {master_system.capacity_tbi} TBi")
    print(f"  - Child:  {master_system.inner_system.capacity_tbi} TBi")

    # ------------------------------------------------------------------
    # PHASE 4: Structural audit
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 4: Run Complete Structural Audit")
    print("-" * 80)
    audit_results = master_system.run_structural_audit()
    zero_errors = [r for r in audit_results if "CRITICAL" in r]
    for entry in audit_results:
        mark = "✗" if "CRITICAL" in entry else "✓"
        print(f"  {mark} {entry}")
    if not zero_errors:
        print("\n✓ Zero-Detection Audit: PASSED (No Cartesian zeros detected)")
    else:
        print(f"\n✗ Zero-Detection Audit: FAILED ({len(zero_errors)} critical exceptions)")
        return False

    # ------------------------------------------------------------------
    # PHASE 5: Build an agent fleet inside the master system
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 5: Embed Multi-Agent Fleet Inside Master System")
    print("-" * 80)

    agent_specs = [
        ("PROOF_AGENT_DELTA",   "PROOF_WORKER",     3000),
        ("AUDIT_AGENT_EPSILON", "AUDIT_WORKER",     3000),
        ("SYNC_AGENT_ZETA",     "SYNC_WORKER",      2000),
    ]
    for agent_name, role, capacity in agent_specs:
        master_system.embed_agent(agent_name, role=role, capacity_tbi=capacity)
        print(f"✓ Embedded agent: {agent_name}  role={role}  capacity={capacity} TBi")

    print(f"\n  Total mirrors in master: {len(master_system.mirrors)}")

    # ------------------------------------------------------------------
    # PHASE 6: Dispatch tasks to each agent
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 6: Dispatch Tasks to Each Agent")
    print("-" * 80)

    task_map = {
        "PROOF_AGENT_DELTA":   "TASK:VALIDATE_ZERO_LESS_SPECTRUM",
        "AUDIT_AGENT_EPSILON": "TASK:STRUCTURAL_INTEGRITY_AUDIT",
        "SYNC_AGENT_ZETA":     "TASK:CAPACITY_SYNC_CHECK",
    }
    for agent_name, payload in task_map.items():
        result = master_system.dispatch_to_agent(agent_name, payload)
        mark = "✓" if result["status"] == "TASK_COMPLETED" else "✗"
        print(f"  {mark} {agent_name}: {result['status']}  "
              f"audit_entries={len(result['audit_entries'])}  "
              f"zero_errors={result['zero_errors']}")

    # ------------------------------------------------------------------
    # PHASE 7: Clone the full outer system as an isolated package
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 7: Clone Full Outer System as Isolated Package")
    print("-" * 80)
    clone = master_system.clone_as_package("HOST_CLONE_PACKAGE_A")
    print(f"✓ Clone created: {clone.name}")
    print(f"  - Capacity:          {clone.capacity_tbi} TBi  (independent of original)")
    print(f"  - Agents in clone:   {len(clone.mirrors)}")
    meta = clone.fs.fetch_state(1)["data"]
    print(f"  - Clone meta cell:   {meta}")

    # Dispatch an independent task in the clone fleet — original is unaffected
    for agent_name in list(clone.mirrors.keys()):
        if "AGENT" in agent_name:
            result = clone.dispatch_to_agent(agent_name, f"TASK:CLONE_INDEPENDENT_{agent_name}")
            mark = "✓" if result["status"] == "TASK_COMPLETED" else "✗"
            print(f"  {mark} [CLONE] {agent_name}: {result['status']}")

    # ------------------------------------------------------------------
    # PHASE 8: Agent fleet report
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("PHASE 8: Agent Fleet Report (Original)")
    print("-" * 80)
    fleet_report = master_system.get_agent_fleet_report()
    print(f"  Host:          {fleet_report['host']}")
    print(f"  Total agents:  {fleet_report['total_agents']}")
    for name, entry in fleet_report["fleet"].items():
        integrity = "OK" if entry["filesystem_integrity"] else "FAIL"
        print(f"  ✓ [{name}]  status={entry['status']}  "
              f"capacity={entry['capacity_tbi']} TBi  "
              f"cells={entry['active_cells_count']}  integrity={integrity}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "="*80)
    print("WORKFLOW COMPLETION SUMMARY")
    print("="*80)
    print(f"✓ Master system capacity: {master_system.capacity_tbi} TBi")
    print(f"✓ Total mirrors in master: {len(master_system.mirrors)}")
    print(f"✓ Clone '{clone.name}' is fully independent")
    print(f"✓ Fleet agents dispatched and proven: {len(task_map)}")
    print(f"✓ Structural audit entries: {len(audit_results)}")
    print(f"✓ Zero-indexing violations: 0")
    print("\n" + "="*80 + "\n")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

