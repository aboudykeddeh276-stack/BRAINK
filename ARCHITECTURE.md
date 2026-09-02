# BRAINK Sector Architecture

## Runtime boundary

`braink://local/orchestrator` is the local BRAINK state/orchestration authority. It resolves resident capabilities and invokes the strongest existing mechanic rather than creating parallel wrappers when an implementation already exists.

## Required layers

```text
BRAINK persistent state
├── orchestrator / resident capability resolution
├── Observer²
├── VFS / continuation / checkpoint / rehydration
├── runtime state and proof relations
├── imported KEX evolution/addressing semantics
└── imported IL-LLM traversal mathematics
```

## Projection rule

HTML, GitHub, filesystem, server and other external surfaces are projections/carriers. They do not silently become BRAINK's state owner.

## Integration rule

Cross-sector mechanics are bound by declared dependency and contract. The sector that executes a process is not automatically the authority that owns the process semantics.
