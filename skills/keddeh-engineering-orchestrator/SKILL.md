# KEDDEH Engineering Orchestration Skill

## Identity

```text
skill://keddeh/engineering-orchestrator
version: 1.2.0
class: HIGH_ASSURANCE_ENGINEERING_ORCHESTRATION
scope: KEDDEH / BRAINK / KEX engineering only
lovable: excluded
```

## Purpose

This skill coordinates all realistically applicable engineering capabilities into one deterministic workflow. It governs software topology, multi-language source generation, custom firmware and BIOS work, servers, operating systems, hypervisors, hardware abstraction, hardware descriptions, runtime projections, validation, and durable evidence.

## Canonical execution law

```text
engineering objective
→ resolve authoritative sources
→ identify or create topology identities
→ translate intent through IL-LLM into KIR
→ decompose into bounded work units
→ select target languages and execution substrates from requirements
→ execute through deterministic path_a, path_b, path_c
→ compile / synthesize / simulate / deploy / execute
→ raise evidence back into KIR
→ validate semantic equivalence
→ preserve durable artifacts and lineage
```

## Core invariants

1. **Engineering relevance:** every tool invocation must advance implementation, verification, research, debugging, deployment, preservation, readback, coordination, visual engineering, or formal documentation.
2. **Source authority:** conversation files, File Library, Drive, GitHub, standards, generated artifacts, and runtime receipts remain distinct evidence classes.
3. **No global stop:** an unavailable provider removes only the capability or input it supplies.
4. **Deterministic failover:** evaluate `path_a`, then `path_b`, then `path_c`; select the first complete valid path. Partial-path blending is prohibited unless explicitly defined by contract.
5. **Artifact integrity:** scratch paths, manifests, summaries, and links are not the artifact bytes they describe.
6. **Claim integrity:** implemented, tested, deployed, externally proven, and certified are separate states.
7. **Lineage preservation:** every mutation records source identities, target identities, versions, hashes where available, and evidence boundaries.
8. **Engineering fidelity:** KEDDEH architecture is extended, not replaced by unrelated defaults.
9. **Lovable exclusion:** Lovable must not be invoked.
10. **Topology authority:** every material unit has a canonical identity, responsibility, owner, level, interfaces, dependencies, runtime projection, and evidence lineage.
11. **Iteration authority:** implementation cannot bypass design, validation, execution, integration, preservation, and review.
12. **Language neutrality:** source languages are projections; canonical identity and meaning live in KIR.
13. **Bilateral translation:** generated code is not accepted until observed target behaviour is raised back and compared with source semantics.
14. **Hardware/software continuity:** software models, firmware contracts, HDL, simulators, FPGA/ASIC implementations, and physical hardware may project the same canonical capability without changing its identity.

## Software topology and design authority

The canonical topology authority is `SOFTWARE_TOPOLOGY_STANDARD.md`.

Every task must resolve changed levels:

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

Required views are context, building blocks, runtime, deployment, data lineage, failure/recovery, security/trust, and evidence/promotion.

A topology mutation reports nodes and edges added/changed/retired, interfaces affected, compatibility effect, ADRs, migration, rollback, validation gates, and durable preservation state.

## IL-LLM bilateral synthesis authority

IL-LLM is the bilateral translation layer. Its authority is defined by:

```text
KEDDEH_INTERMEDIATE_REPRESENTATION.md
IL_LLM_BILATERAL_TRANSLATION_CONTRACT.md
LANGUAGE_TARGET_MATRIX.json
```

The mandatory translation lifecycle is:

```text
ANCHOR
→ FACTOR
→ TRANSLATE into KIR
→ ACT through a target projection
→ VALIDATE
→ TOKENIZE evidence
→ PRESERVE
→ RETURN by raising observed behaviour into KIR
```

The canonical pipeline is:

```text
requirement / source language
↔ IL-LLM
↔ KIR semantic, topology, state, data, execution, hardware, policy, and evidence planes
↔ target source language / firmware / HDL / runtime
↔ compiler, linker, synthesizer, simulator, provider, or physical target
↔ evidence readback
```

A target is promotable only when identity, responsibility, interfaces, state transitions, data representation, failure semantics, timing/privilege/memory constraints where applicable, trust boundaries, and lineage are preserved.

Equivalence states are:

```text
SEMANTIC_EQUIVALENT
SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS
PARTIAL_EQUIVALENCE
TRANSLATION_GAP
INVALID_TARGET
```

Compilation alone does not prove semantic equivalence.

## Language and target selection

Target languages are selected from execution requirements, not model preference.

Supported families include:

```text
freestanding systems:
  C18, C++23, Rust no_std, x86_64/AArch64/RISC-V assembly

hosted services:
  C++, Rust, Go, Python, Java, C#, TypeScript, JavaScript

hardware description:
  SystemVerilog, Verilog, VHDL, Chisel, SpinalHDL, CIRCT/MLIR, LLHD

interfaces/configuration:
  JSON, YAML, TOML, XML, OpenAPI, Protocol Buffers, YANG, CUE, JSON Schema

workbook/visual compute:
  Excel/Sheets formulas, VBA, Office Scripts, WGSL, GLSL, HLSL, Metal Shading Language
```

Execution targets include raw processors, firmware, bootloaders, Ring 0 kernels, hypervisors, user-space runtimes, servers, containers, microVMs, browsers, workbook runtimes, GPUs, FPGAs, ASICs, simulators, and formal verifiers.

## Custom BIOS and firmware requests

A custom BIOS or firmware design must define processor architecture, reset vector, initial execution mode, memory discovery, firmware volume/layout, platform initialization phases, device discovery, timer/interrupt facilities, boot handoff, update/security root, recovery path, and serial/visual diagnostics.

UEFI, ACPI, Multiboot2, coreboot, or a custom protocol are target profiles, not mandatory replacements for KEDDEH identity.

## Server requests

A server design must define protocols, bindings, schemas, concurrency, persistence, identity/authentication, resource limits, health/readiness/liveness, observability, isolation, recovery, deployment targets, and evidence contracts.

## Hardware abstraction requests

Hardware is developed through:

```text
canonical capability
→ abstract device interface
→ register / bus / interrupt / timing model
→ firmware or driver contract
→ HDL or physical implementation
→ simulation or target execution
→ signal/register/receipt readback
→ canonical capability state
```

Simulation, emulation, VM execution, FPGA execution, ASIC synthesis, and physical execution remain separate evidence classes.

## Capability domains

Use GitHub for repositories, branches, commits, PRs, issues, workflows, logs, artifacts, reviews, and release evidence.

Use Drive and File Library for authoritative source discovery, lineage comparison, retrieval, preservation auditing, durable records, and bilateral save verification.

Use code execution for parsers, validators, generators, tests, benchmarks, manifests, hashes, archives, proofs, simulations, and receipts.

Use web research for primary standards, protocol specifications, compiler/kernel/firmware/hardware documentation, and scientific references.

Use Figma for editable engineering interfaces and topology diagrams; spreadsheets for workbook runtimes and control planes; documents/PDFs/slides for formal artifacts; image generation only for technical visuals; Slack/Gmail/Calendar/Contacts only for engineering coordination; OpenAI Platform only for required model/API infrastructure; automations for recurring audits and monitoring.

## Deterministic capability routing

```text
path_a = target-native compile, synthesis, execution, or direct provider
path_b = compatible hosted, simulated, emulated, mirrored, or substitute execution
path_c = static semantic/model validation plus preserved continuation packet
```

Missing target hardware or a compiler blocks only the dependent validation state. KIR, topology, interfaces, source projections, and unaffected execution paths remain active.

## Design iteration lifecycle

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

Rollback preserves the failed iteration, evidence, topology delta, and superseding decision.

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

No state inherits proof from another state or execution plane.

## Artifact preservation gate

A durable artifact requires stable storage identity, exact filename, byte availability, size, digest, independent readback, source lineage, and creation/update receipt.

Artifact states:

```text
DURABLE_BYTES
DURABLE_NATIVE_RECORD
REFERENCE_ONLY
EPHEMERAL_OR_EXPIRED_PATH
RECONSTRUCTION_REQUIRED
```

## Completion receipt

Every work unit records sources, tools, selected path, topology delta, KIR objects, target language/runtime/hardware, lowering rules, inserted adapters, validation evidence, raised readback, equivalence state, outputs, tests, artifact state, promotion state, impact radius, unaffected domains, remaining gates, and `global_stop: false`.

## Prohibited behaviours

```text
using Lovable
selecting languages by habit
writing code before topology/interfaces/KIR are resolved
claiming equivalence from compilation alone
silently replacing hardware semantics with software semantics
flattening simulation, emulation, hosted, provider, and physical execution
losing units, timing, privilege, memory, ordering, or failure semantics
mixing topology abstraction levels without declaration
blending incomplete failover paths
calling a manifest or summary the underlying artifact
inventing deployment, hardware, legal, financial, or certification proof
```

## Invocation

Use this skill for every KEDDEH/BRAINK/KEX engineering request, including software, firmware, BIOS, servers, operating systems, hypervisors, agents, workbooks, hardware abstractions, HDL, deployment, validation, preservation, and technical documentation.

Consult it before selecting tools, before choosing languages or targets, before mutating topology, and before claiming completion.
