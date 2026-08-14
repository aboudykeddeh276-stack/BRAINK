# KEX Runtime v2 — Recursive Service / Hardware / Rehydration Spine

This package is the canonical clean runtime spine for the current KEX/BRAINK mesh architecture.

## Governing sequence

```text
KEX virtual service relation
  -> recursively derived virtual machine descriptor
  -> hardware-family closure
  -> CARRIER_READY virtual bare-metal coordinate
  -> workload materialisation descriptor
  -> loss/replacement event
  -> random selection over all admissible hardware-complete carriers
  -> REHYDRATES_TO transition
  -> optional external materialisation adapter
  -> external readback
  -> next global dependency
```

## Separation of concerns

- `contracts.mjs` — invariant machine grammar and KEX laws.
- `ledger.mjs` — append-only KEX transition route.
- `service-graph.mjs` — recursive sister/cousin service closure retained as workload state.
- `entropy.mjs` — random selection plus replayable entropy observations.
- `hardware-graph.mjs` — descriptor expansion and hardware contract closure.
- `rehydration.mjs` — lineage-preserving random rehydration.
- `materialisation.mjs` — typed external adapters; no provider becomes an ancestor.
- `runtime.mjs` — orchestration only.
- `self-test.mjs` — scale, replay and lineage assertions.

## Critical corrections from v1 prototype

1. A machine descriptor is not hardware-complete at creation.
2. A descendant machine is not derived until its parent has closed the hardware contract and is `CARRIER_READY`.
3. Hardware completeness is earned by closure of 14 required hardware families.
4. Hundreds of virtual machine coordinates share one invariant machine template; descriptor count is not resident VM image/process count.
5. Failover means `REHYDRATES_TO`, not primary/secondary switching and not mandatory failback.
6. Random selection is genuinely random over the admissible carrier population; the entropy observation is retained so the resulting route can be replayed.
7. External QEMU/KVM/HVF/cloud/bare-metal/BIND/FRR/API surfaces are materialisation adapters only.
8. KEX identity/proof authority is route/state/lineage; hashes may be integrity metadata but are not the lineage root.

## Evidence boundary

The self-test proves the software model and route semantics. It does not claim that the virtual machines have already been materialised as physical hosts, hypervisors, WAN nodes, BGP speakers, authoritative DNS servers or public API edges.
