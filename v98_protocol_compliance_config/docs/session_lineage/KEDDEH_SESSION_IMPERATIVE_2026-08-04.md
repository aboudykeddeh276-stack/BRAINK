# KEDDEH Session Imperative — 2026-08-04

## Status

Canonical conceptual record and implementation lineage for IL-LLM, Active Story, active-word governance, provider inversion, CloudWorkspaceEngine, and deterministic failover.

## Foundational identity

KEDDEH / BRAINK / KEX is a recursive contextual execution substrate. Its fundamental unit is a validated context transition:

```text
Context_n
→ OBSERVE
→ IDENTIFY
→ INTERPRET
→ TRAVERSE
→ VALIDATE
→ PROMOTE
→ PRESERVE
→ Context_n+1
```

`SYSTEM ≡ DOMAIN`. Every surface is a contextual domain executing the same lifecycle while preserving identity, environment, observer, lineage, evidence, and allowed transitions.

## IL-LLM and Active Story

The corpus is IL-LLM source material, not merely documentation. Every source datum is preserved independently and reintegrated bilaterally:

```text
source datum
→ canonical word/value
→ contextual expression
→ sector/service binding
→ runtime use
→ receipt/backlink
→ source-lineage return
→ Mirror Lane amendment
→ reingestion
```

The codebase is an executable encyclopedia:

```text
WORD
→ SOURCE DEFINITION
→ CONTEXTUAL INSTANCE
→ EXPRESSION
→ SECTOR
→ SERVICE
→ CODE HANDLER
→ EXECUTION
→ STORY TRANSITION
→ RECEIPT
→ BACKLINK
```

No word occurrence, context, module field, JSON datum, CSV row, source line, contradiction, unresolved term, or receipt may overwrite another manifestation.

## Active-word governance

Canonical equation:

```text
A_W = f(W,C,E,S,V,O,L,T)
```

- `W`: canonical word identity
- `C`: context
- `E`: expression
- `S`: sector
- `V`: service
- `O`: observer or authority
- `L`: lineage
- `T`: time or state version

Word identity is invariant; active meaning is contextually instantiated.

Primary states:

```text
DEFINED → CONTEXTUALIZED → AUTHORIZED → ROUTED → ACTIVE → OBSERVED → VERIFIED → PRESERVED
```

Bounded failure states:

```text
ACTIVE → DEGRADED → DEFERRED → RECOVERING → REINTEGRATED
```

Unknown terms become provisional active values with preserved expression, context, sector, service, observer, bilateral links, and Mirror Lane translation work.

```text
missing term ≠ missing runtime
untranslated ≠ invalid
```

## Character and null-presence law

A character does not become zero. Zero has no independent character identity in this semantic model. It is dependent notation describing null presence, membership, projection, or resultant of an identified character within a defined relation.

The character, relation, environment, observer, time, evidence, and lineage remain preserved. `NULL_PRESENCE` is a relational state, not deletion.

## Provider inversion

The Mac is not the control plane. A Mac, server, hypervisor, cluster, GitHub-hosted runner, ARC scale set, microVM, browser, remote node, GPU, database, API, model, agent, sensor, storage system, authority, or external provider is a dependency-managed capability provider.

```text
GitHub event
→ GitHub-hosted ignition runtime
→ BRAINK hypervisor/provider resolver
→ workload capability resolution
→ eligible provider selection
→ bounded execution
→ evidence return
→ bilateral reconciliation
```

```text
provider declared
≠ provider available
≠ provider selected
≠ workload executed
≠ result verified
```

A provider absence affects only workloads requiring capabilities uniquely supplied by that provider.

## Universal capability-loss model

```text
component
→ supplied capabilities
→ supplied input data
→ derivable output data
```

When a component is unavailable:

```text
remove only its supplied inputs
→ identify affected outputs
→ preserve unaffected outputs
→ evaluate deterministic failover paths
→ continue, substitute, degrade, defer, or bounded-stop only within the proven impact radius
```

Component availability is not service availability.

## Deterministic failover law

`path_a`, `path_b`, and `path_c` are strict ordered deterministic failover pathways.

```text
evaluate path_a
→ if incomplete, reject with evidence
→ evaluate path_b
→ if incomplete, reject with evidence
→ evaluate path_c
→ select the first complete valid path
```

For output `O` and available input set `I`:

```text
P(O,I) = P_A when R_A ⊆ I
P(O,I) = P_B when R_A ⊄ I and R_B ⊆ I
P(O,I) = P_C when R_A ⊄ I and R_B ⊄ I and R_C ⊆ I
P(O,I) = null-presence for that output otherwise
```

Partial cross-path blending is prohibited. One input from `path_a` plus one from `path_b` does not form a valid result unless a separately declared composite path explicitly authorizes that exact set.

## Output-specific service state

A missing optional output must not flatten the whole service to the worst state.

Example:

```text
native GPU unavailable
→ output.frame derived through path_b using CPU renderer
→ output.hardware-acceleration-proof deferred
→ service state SUBSTITUTED
→ impact radius limited to hardware proof
→ global_stop false
```

The same law applies to Apple-native proof, public reachability, native packaging, external telemetry, server response, agent synthesis, model inference, database queries, and every capability-scoped output.

## CloudWorkspaceEngine and sovereign mesh

CloudWorkspaceEngine is implemented as a persistent service, container, Kubernetes workload, OpenAPI Mesh-Engine Node Registry contract, and persistent FailureLedger.

The deployment surface includes Namespace, ServiceAccount, ConfigMap, Deployment, ClusterIP Service, startup/readiness/liveness probes, PodDisruptionBudget, HPA, NetworkPolicy, security context, resources, and dependency policies.

Readiness governs admission. Liveness detects unrecoverable process failure. Startup protects initialization. Optional and external dependency failures are excluded from liveness to prevent cascading restarts.

FailureLedger persists dependency failures and deferred work, reconciles after service reintegration, and preserves `globalStop=false` for bounded failures.

## Implementation sequence

- V100 — Active Story Lexicon
- V101 — IL-LLM Bilateral Ingestion
- V102 — Active Word Governance
- V103 — Active Word Full Engagement
- V104 — CloudWorkspaceEngine Sovereign Contracts and runtime
- V105 — M3 Host Readiness Contract
- V106 — Hypervisor Provider Resolution and provider-inverted workflows
- V107 — Universal deterministic capability failover using `path_a → path_b → path_c`

## Key implementation surfaces

```text
config/active_story_lexicon.json
config/il_llm_active_story_registry.json
config/il_llm_corpus_manifest.json
config/active_word_governance.json
config/active_word_full_engagement.json
config/hypervisor_provider_registry.json
config/universal_capability_derivation_registry.json
src/keddeh_active_story_runtime.py
src/keddeh_il_llm_runtime.py
src/keddeh_il_llm_bilateral_ingestor.py
src/keddeh_active_word_governance.py
src/keddeh_active_word_full_engagement.py
src/keddeh_hypervisor_provider_resolver.py
src/keddeh_deterministic_failover_runtime.py
services/cloudworkspace_engine/server.py
web/src/failure-ledger.ts
api/mesh-engine-node-registry.openapi.yaml
deploy/cloudworkspace-engine/cloudworkspace-engine.yaml
```

## Bilateral invariant

```text
source → runtime → output → receipt
receipt → output → runtime → source
```

Every derivation is a complete linked point. Runtime findings return through Mirror Lane. Source lineage is amended only after validation and reingested without deleting prior states.

## Evidence boundary

Specified, implemented, validated, operational, provider-proven, deployed, and externally proven are distinct states.

- A manifest is not deployment proof.
- A workflow success is not target-hardware proof.
- A provider declaration is not provider availability.
- A UI state is not runtime execution.
- A hash is byte-integrity evidence, not architecture proof.
- A skipped provider-specific job does not prove that provider executed.

Missing external evidence is an output-specific pending state with a re-entry path, not a global stop.

## Canonical session result

Every component is a dependency-managed source of capabilities and input data. Every service is defined by required output data. Every output has ordered deterministic pathways `path_a`, `path_b`, and `path_c`. The first complete path is selected reproducibly. Partial paths are never silently blended. Only non-derivable outputs are deferred or bounded-stopped. All derivable outputs remain active. All provider observations, selected and rejected paths, input lineage, transitions, receipts, and source relationships are preserved bilaterally.

This record is imperative and must be consulted before modifying provider selection, dependency isolation, IL-LLM ingestion, Active Story semantics, active-word governance, FailureLedger behaviour, service health aggregation, workflow routing, or deterministic failover logic.
