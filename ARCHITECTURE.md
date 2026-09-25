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


## MCP system superface

MCP is the enclosing interoperability surface over the resident BRAINK loadout:

```text
external IDE / console / agent / client
                 |
                 v
                MCP
                 |
                 v
       braink://local/orchestrator
        /        |          \
 agent authority IL-LLM      HCI
        \        |          /
              runtime
                 |
                VFS
                 |
          node / compute
```

MCP is a projection and invocation surface. It does not become the owner of BRAINK state,
IL-LLM semantics, VFS identity, model artifacts, agent authority, or node compute.

Model residency is qualified only when all of the following are observed:

1. the declared physical model artifact exists and matches its registered inventory;
2. the model is bound into the BRAINK VFS namespace;
3. the canonical IL-LLM model-registry runtime acknowledges the node/model binding;
4. the node carries an explicit agent-to-model authority map.

A node that cannot satisfy all four conditions is `NOT_READY`. Missing canonical IL-LLM runtime
binding is therefore an observed blocker, not a reason to silently promote another repository.

## Human-centred workstation interaction

The native workstation shell follows `governance/hci/BRAINK_INTERACTION_CONTRACT_R8.json`.
Primary UI surfaces are user-goal surfaces: Home, AI, Tasks and Files. Activity, Admin and
Diagnostics are secondary. Model mounting, VFS state, endpoints, node internals, logs and ledger
details are progressively disclosed through Diagnostics rather than competing with the user's
task on Home.

The interaction contract is based on ISO 9241-110:2020, ISO 9241-210:2019,
ISO 9241-11:2018, ISO 9241-112:2025, ISO/IEC 25010:2023 and ISO/IEC 25019:2023.
This repository does not claim ISO certification or independent conformance assessment.
