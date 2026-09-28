---
name: braink-process-adapter
description: Invoke BRAINK durable processes through the BRAINK MCP tool surface. Use for identity resolution, signed work-envelope creation, replay-safe consumption, worker lease/fencing, Domain Authority mutation/readback, checkpointing, and successor recovery.
---

# BRAINK Process Adapter

This skill is invocation policy. The MCP server is the actuator.

## Required execution order

For mutating work:

1. `braink_resolve_identity`
2. `braink_create_work_envelope`
3. `braink_consume_work_envelope`
4. `braink_acquire_work_lease` with a bounded TTL and retry budget
5. while work is active, refresh with `braink_heartbeat_work_lease`
6. invoke the sector mutation tool through the governed capability path
7. read back actual sector state
8. `braink_write_checkpoint`
9. recovery workers call `braink_reconcile_work_leases`; retryable stale work becomes `RECOVERABLE`, exhausted work becomes `POISON_PILL_FAILED`
10. inspect `braink_get_lease_failures` for remediation records
11. on replacement/restart, `braink_read_checkpoint` then acquire the next lease epoch

Never report execution because a tool exists. Report the tool result and readback state.

Never treat an unexposed process as impossible. Classify it as `UNBOUND_TOOL_SURFACE` until an adapter is written over the resident mechanic.

Preserve `work_id`, legal and operating identities, lease epoch, lease expiry, heartbeat, retry count/budget, poison-failure disposition, sector mutation ownership, observed result, and receipt/checkpoint lineage.

Lease recovery is part of the BRAINK process fabric: an expired lease with remaining retry budget is re-armed for the next worker; a retry-exhausted lease is retained as `POISON_PILL_FAILED` with a `REMEDIATION_REQUIRED` failure record. Do not erase prior lineage when recovering work.

Do not expose signing keys, database paths, or internal secrets as tool arguments.
