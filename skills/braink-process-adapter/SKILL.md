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
4. `braink_acquire_work_lease`
5. invoke the sector mutation tool, e.g. `braink_provision_domain_authority`
6. read back actual sector state, e.g. `braink_observe_domain_authority`
7. `braink_write_checkpoint`
8. on replacement/restart, `braink_read_checkpoint` then acquire the next lease epoch

Never report execution because a tool exists. Report the tool result and readback state.

Never treat an unexposed process as impossible. Classify it as `UNBOUND_TOOL_SURFACE` until an adapter is written over the resident mechanic.

Preserve `work_id`, legal and operating identities, lease epoch, sector mutation ownership, observed result, and receipt/checkpoint lineage.

Do not expose signing keys, database paths, or internal secrets as tool arguments.
