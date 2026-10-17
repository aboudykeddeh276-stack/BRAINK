# BRAINK IL-LLM × KEX Semantic Fabric — Implementation Record

Status: IMPLEMENTED CANDIDATE — execution proof pending CI/local test
Date: 2026-08-20
Branch: `engineering/illlm-kex-semantic-fabric-20260820`

## Objective

Correct the flat-runtime failure by making IL-LLM the recursive semantic fabric and KEX the governed compact representation of that fabric, without replacing the existing BTC runtime or NativeChatBot implementation.

## Source-grounded invariants

- Semantic addresses are authoritative identities; VFS/repository/HCI forms are materialisations or projections.
- Traversal follows typed semantic relations rather than assuming a star/root-only topology.
- Observer frames are plural and bounded; an interpretation does not mutate the producer fact.
- Continuations are plural and retain coordinate, observer, logical time, route, return route, evidence cursor and governance scope.
- Evidence is scoped by semantic subject, epoch and session.
- Synthetic evidence is structurally excluded from default proof satisfaction.
- KEX encoding never becomes semantic authority by itself. A governed registry binds KEX identity to immutable semantic identity/digest.
- Default KEX decode depth is one semantic projection. Recursive expansion requires explicit depth.
- Historical events remain resident; newer work uses `SUPERSEDES` rather than destructive replacement.

## Implemented slice

`runtime/illlm_fabric.py` introduces:

- immutable `SemanticObject`;
- typed `Relation`;
- `ObserverFrame`;
- plural `Continuation` with deterministic advance semantics;
- scoped `EvidenceRecord`;
- governed reversible `KEXRegistry`;
- `ILFabric` registration, alias resolution, relation storage, observation, continuation storage, evidence append, bounded KEX encode/decode, traversal and evidence-scope verification;
- a minimal BTC semantic seed proving that `CORE_GBT → REQUIRES_AUTHORITY → Bitcoin Core authority class` is graph-resident rather than a hard-coded authority dictionary.

## Deliberately not changed

- `runtime/btc_consensus.py`
- `runtime/btc_miner_runtime.py`
- `runtime/btc_workload_substrate.py`
- NativeChatBot sources
- existing governance artifacts

This is additive isolation. The existing BTC implementation remains the execution implementation; this slice supplies the semantic/representation fabric it can subsequently inhabit.

## Required conformance properties

1. `decode(encode(S), depth=1)` resolves to `S.identity`.
2. Human aliases of one semantic object resolve to one KEX binding.
3. KEX binding rejects semantic mutation after binding.
4. Depth-one decode does not recursively explode the graph.
5. Explicit deeper decode traverses typed relations.
6. Multiple observer frames do not mutate the source semantic object.
7. Multiple continuations coexist and advance independently.
8. Authority requirements are graph-resident.
9. Synthetic evidence fails default proof qualification.
10. Evidence from a stale epoch/session cannot qualify a newer scope.
11. `SUPERSEDES` preserves the historical object.

These properties are encoded in `tests/test_illlm_fabric.py`.

## Proof boundary

The connector can write source but does not execute repository tests. Therefore this implementation is not promoted to TESTED. The correct state is `IMPLEMENTED_CANDIDATE / EXECUTION_PROOF_PENDING` until `python -m unittest tests.test_illlm_fabric` is observed passing in an execution-capable runtime or CI.

## Next integration slice after proof

Bind one genuine Bitcoin Core `getblocktemplate` receipt into the fabric as one immutable semantic event projected concurrently into BTC, authority, proof, temporal, planning, execution, carrier, memory, governance and HCI observer frames. Preserve the existing BTC runtime as producer/executor; do not replace it with semantic simulation.
