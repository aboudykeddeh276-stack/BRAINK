# KEDDEH Engineering Orchestration Skill

## Identity

```text
skill://keddeh/engineering-orchestrator
version: 1.1.0
class: HIGH_ASSURANCE_ENGINEERING_ORCHESTRATION
scope: KEDDEH / BRAINK / KEX engineering only
lovable: excluded
```

## Purpose

This skill coordinates all realistically applicable engineering capabilities into one deterministic workflow. It does not invoke tools for decoration, unrelated content production, or work outside the KEDDEH engineering domain.

## Canonical execution law

```text
engineering objective
→ resolve authoritative sources
→ identify or create software topology identities
→ decompose into bounded work units
→ map each work unit to the strongest applicable capability
→ execute through deterministic path_a, path_b, path_c
→ validate outputs and topology changes
→ preserve durable artifacts
→ perform independent readback
→ record receipts, hashes, lineage, impact radius, architecture decisions, and unresolved gates
```

## Core invariants

1. **Engineering relevance:** every tool invocation must produce implementation, verification, research evidence, debugging, deployment, preservation, readback, coordination, visual engineering, or formal documentation.
2. **Source authority:** current-conversation files, File Library, Drive, GitHub, standards, and runtime receipts remain distinct evidence classes.
3. **No global stop:** an unavailable provider removes only the data or capability it supplies.
4. **Deterministic failover:** evaluate `path_a`, then `path_b`, then `path_c`; select the first complete valid path. Partial-path blending is prohibited unless explicitly declared by the service contract.
5. **Artifact integrity:** a file is not saved merely because a scratch path, manifest, summary, or link exists.
6. **Claim integrity:** implemented, tested, deployed, externally proven, and certified are separate promotion states.
7. **Lineage preservation:** every mutation records source identities, target identities, commit/revision IDs, hashes where available, and evidence boundaries.
8. **Engineering fidelity:** existing KEDDEH architecture is extended, not replaced by unrelated platform defaults.
9. **Lovable exclusion:** Lovable must not be invoked by this skill.
10. **User authority:** destructive, external, credentialed, legal-authority, financial, or public-production actions remain permission- and evidence-gated.
11. **Topology authority:** every material software unit must have a canonical identity, responsibility, owner, level, interfaces, dependencies, runtime projection, and evidence lineage.
12. **Iteration authority:** implementation cannot bypass design, static validation, execution, integration, preservation, and review states.

## Software topology and design authority

The canonical standard is:

```text
SOFTWARE_TOPOLOGY_STANDARD.md
```

Every material engineering task must determine which topology levels it changes:

```text
L0 ecosystem
L1 system
L2 bounded domain
L3 runtime container
L4 component
L5 code unit
L6 execution transition
L7 deployment projection
```

The task must preserve distinct views for context, building blocks, runtime, deployment, data lineage, failure/recovery, security/trust, and evidence/promotion.

A topology mutation must report:

```text
nodes added or changed
edges added, changed, or retired
interfaces affected
compatibility effect
ADRs introduced or superseded
migration and rollback sequence
validation gates
```

The following files are mandatory skill authorities:

```text
software_topology.schema.json
naming_conventions.json
iteration_lifecycle.json
```

Disconnected files without topology identity are incomplete software design outputs.

## Capability domains

### GitHub

Use for repository inspection, branches, commits, pull requests, issues, workflows, CI logs, artifacts, patches, reviews, and release evidence.

Mandatory outputs where applicable:

```text
repository identity
branch/ref
changed paths
commit SHA
workflow/run/job identity
check conclusion
artifact identity
remaining blockers
```

### Google Drive and File Library

Use for authoritative source discovery, lineage comparison, document retrieval, preservation auditing, durable records, and bilateral save verification.

A Drive-native summary is not equivalent to the raw artifact bytes it describes.

### Code execution

Use for parsers, validators, generators, test harnesses, benchmarks, manifests, hashes, archives, reports, simulations, proofs, and reproducible evidence.

Generated output must distinguish:

```text
logical execution
local execution
CI execution
target-host execution
provider execution
external readback
```

### Web research

Use primary sources for standards, protocols, compiler behaviour, kernel interfaces, hardware specifications, security controls, and scientific references. Clearly separate source-derived facts from inference or architectural interpretation.

### Figma

Use only for editable engineering interfaces, workstation topology, operating-system surfaces, control planes, HCI prototypes, or system diagrams that materially support implementation.

### Spreadsheets

Use for workbook operating systems, control planes, registries, matrices, state ledgers, dependency graphs, test evidence, and capability topology. Preserve formulas, validation rules, sheet naming, and bilateral indexes.

### Documents, PDFs, and slides

Use for formal specifications, white papers, ADRs, technical reports, compliance packs, evidence dossiers, and publication-ready engineering records. PDFs must be visually inspected when diagrams, tables, or figures matter.

### Image generation

Use only for technical diagrams, architecture visualisations, hardware/software topology, UI concepts, or state illustrations. Generated images are design artifacts, not execution proof.

### Slack, Gmail, Calendar, and Contacts

Use only for engineering coordination, task execution, evidence collection, schedules, worker management, and project communication. Do not use them for unrelated social or promotional activity.

### OpenAI Platform

Use only when the engineering requires API keys, model integration, runtime configuration, or OpenAI infrastructure. Follow official platform documentation and preserve configuration boundaries.

### Automations

Use for recurring engineering audits, CI monitoring, repository checks, progress reviews, evidence validation, and condition-based alerts. Automations do not replace direct execution when the user requested an immediate result.

## Deterministic capability routing

```text
path_a = strongest direct execution path
path_b = deterministic substitute preserving required semantics
path_c = bounded degraded or deferred path preserving identity and lineage
```

Examples:

```text
repository source:
  path_a GitHub connector
  path_b durable Drive mirror
  path_c preserved work packet with exact missing inputs

artifact persistence:
  path_a durable raw-byte upload + readback
  path_b repository artifact/release + hash readback
  path_c native record + explicit REFERENCE_ONLY classification

compute:
  path_a target runtime
  path_b CI/hosted runtime
  path_c deterministic local software model
```

## Design iteration lifecycle

Every material change follows:

```text
I0 OBSERVE
→ I1 DEFINE
→ I2 DESIGN
→ I3 IMPLEMENT
→ I4 STATIC_VALIDATE
→ I5 EXECUTE
→ I6 INTEGRATE
→ I7 PROMOTE
→ I8 PRESERVE
→ I9 REVIEW
```

Skipping from design to promotion is prohibited. Rollback preserves the failed iteration, evidence, and superseding decision.

## Promotion ladder

```text
CONCEPTUAL
FORMALISED
IMPLEMENTED
STATICALLY_VALIDATED
LOCALLY_EXECUTED
CI_PASS
TARGET_HOST_PASS
PROVIDER_PASS
DEPLOYED
EXTERNALLY_PROVEN
CERTIFIED_OR_AUTHORITY_CONFIRMED
```

No state may inherit proof from a lower or unrelated state.

## Artifact preservation gate

A durable artifact claim requires:

```text
stable storage identity
exact filename
byte availability
size
SHA-256 or provider digest
independent readback
source lineage
creation/update receipt
```

Classify every artifact as one of:

```text
DURABLE_BYTES
DURABLE_NATIVE_RECORD
REFERENCE_ONLY
EPHEMERAL_OR_EXPIRED_PATH
RECONSTRUCTION_REQUIRED
```

## Completion receipt

Every completed work unit should emit:

```json
{
  "work_unit": "...",
  "engineering_domain": "...",
  "source_identities": [],
  "tools_invoked": [],
  "selected_path": "path_a|path_b|path_c",
  "topology_delta": {
    "nodes_added": [],
    "nodes_changed": [],
    "edges_added": [],
    "edges_changed": [],
    "interfaces_affected": []
  },
  "iteration_state": "I0_OBSERVE|I1_DEFINE|I2_DESIGN|I3_IMPLEMENT|I4_STATIC_VALIDATE|I5_EXECUTE|I6_INTEGRATE|I7_PROMOTE|I8_PRESERVE|I9_REVIEW",
  "outputs": [],
  "tests": [],
  "artifact_state": "DURABLE_BYTES|DURABLE_NATIVE_RECORD|REFERENCE_ONLY|EPHEMERAL_OR_EXPIRED_PATH|RECONSTRUCTION_REQUIRED",
  "promotion_state": "...",
  "impact_radius": [],
  "unaffected_domains": [],
  "remaining_gates": [],
  "global_stop": false
}
```

## Prohibited behaviours

```text
claiming all tools were used when they were not applicable
using Lovable
flattening missing optional evidence into global failure
calling manifests or summaries the underlying artifact
inventing target-host, provider, deployment, legal, financial, or certification proof
replacing KEDDEH architecture with unrelated conventional abstractions
blending incomplete failover paths
creating decorative artifacts without engineering value
creating disconnected modules without topology identity
mixing architecture abstraction levels in one undocumented view
promoting changes without an iteration record and topology delta
```

## Invocation

Use this skill whenever the request concerns KEDDEH/BRAINK/KEX engineering, repository work, research, system design, runtime implementation, testing, deployment, evidence, preservation, worker coordination, or formal technical documentation.

The skill must be consulted before selecting tools, before mutating software topology, and again before claiming completion.
