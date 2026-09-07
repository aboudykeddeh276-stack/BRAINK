# BRAINK Window Propagation Skill

## Purpose
Use the resident BRAINK runtime to collapse signals emitted inside one logical window into a single deterministic propagation frame before those signals cross a wrapper boundary.

## Authority
- State authority remains `braink://local/orchestrator`.
- Originating sectors retain ownership of business semantics.
- This skill owns transport normalisation, ordering, durable replay and proof-root generation only.

## Procedure
1. Collect signals as `{source, sector, kind, payload, sequence}`.
2. Reject an empty set or duplicate sequence numbers.
3. Order by `sequence`, then `sector`, `source`, and `kind`.
4. Compile exactly one frame for a `(work_id, sequence)` pair.
5. Compute the canonical SHA-256 root over work id, frame sequence and ordered signals.
6. Persist the complete frame to the local SQLite WAL ledger.
7. Expose the frame through the local service or bind it to another resident runtime through an adapter.
8. Verify the root before accepting a replayed frame.

## Boundary rule
Do not treat a projection, HTTP endpoint, plugin, GitHub carrier, HTML surface or deployment receipt as proof that a sector's business runtime executed. Those surfaces may transport or evidence a propagation frame, but semantic execution must be proven independently by the owning runtime.

## Runtime
- Python implementation: `runtime/window_propagation.py`
- Local server: `services/window_propagation_server.py`
- Plugin contract: `plugins/window-propagation/plugin.json`
- Default endpoint: `127.0.0.1:18771`
- Default ledger: `state/window-propagation.sqlite3`
