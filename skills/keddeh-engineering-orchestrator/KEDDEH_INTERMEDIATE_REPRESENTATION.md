# KEDDEH Intermediate Representation

## Identity

```text
ir://keddeh/system-synthesis
version: 1.0.0
```

## Purpose

The KEDDEH Intermediate Representation (KIR) is the bilateral translation substrate between human requirements, IL-LLM interpretation, software topology, source languages, firmware, hardware descriptions, runtime projections, and evidence.

KIR is not a replacement programming language. It is a canonical semantic and structural model from which target-language projections are generated and against which generated implementations are read back.

## Canonical pipeline

```text
source observation / user requirement
→ IL-LLM anchor and factor extraction
→ KIR semantic graph
→ KIR topology graph
→ KIR interface and state contracts
→ target-language lowering
→ compile / synthesize / deploy / execute
→ evidence normalization
→ bilateral readback into KIR
→ semantic equivalence decision
```

## Required KIR planes

Every non-trivial design shall preserve the following planes:

1. `identity_plane`: canonical identities, names, ownership, lineage.
2. `semantic_plane`: definitions, invariants, meanings, prohibited conflations.
3. `topology_plane`: systems, domains, runtimes, components, code units, providers, edges.
4. `state_plane`: states, transitions, guards, preconditions, postconditions, failures.
5. `data_plane`: schemas, units, representations, memory/storage locations, provenance.
6. `execution_plane`: ISA, privilege, runtime, calling convention, scheduling, timing.
7. `hardware_plane`: registers, buses, interrupts, MMIO, clocks, resets, protocols, physical projections.
8. `policy_plane`: permissions, trust, safety, compatibility, promotion constraints.
9. `evidence_plane`: tests, receipts, hashes, traces, synthesis reports, readbacks.

## KIR object classes

```text
System
Domain
Runtime
Component
CodeUnit
Interface
Schema
StateMachine
Transition
MemoryRegion
Register
Bus
Interrupt
Device
Provider
Adapter
Artifact
Evidence
Decision
Iteration
```

Every object has:

```text
canonical_id
object_class
responsibility
owner
version
source_lineage
invariants
interfaces
state
promotion_state
evidence_refs
```

## Lowering contracts

A target projection must declare:

```text
source KIR identities
target language
target runtime or hardware
compiler/synthesizer/toolchain
representation mappings
unsupported semantics
inserted adapters
optimizations
proof obligations
round-trip readback method
```

Examples:

```text
KIR memory region
→ C/C++ linker section
→ Rust static/allocator region
→ HDL memory block
→ workbook range
→ browser ArrayBuffer
```

```text
KIR state transition
→ C switch/state machine
→ Rust enum + match
→ TypeScript discriminated union
→ SystemVerilog always_ff logic
→ workflow state record
```

## Bilateral semantic equivalence

A generated target is promotable only when readback preserves:

```text
identity
responsibility
preconditions
postconditions
state transitions
failure semantics
data representation constraints
dependency direction
security/trust boundaries
lineage
```

Textual similarity is not equivalence.

The required decision is:

```text
KIR_source
→ lower(target)
→ target_artifact
→ inspect/execute(target_artifact)
→ raise(readback)
→ KIR_observed
→ compare(KIR_source, KIR_observed)
```

The comparison result is one of:

```text
SEMANTIC_EQUIVALENT
SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS
PARTIAL_EQUIVALENCE
TRANSLATION_GAP
INVALID_TARGET
```

## Hardware/software abstraction rule

Hardware is represented first by its software-visible contract, then by progressively lower projections:

```text
capability
→ abstract device contract
→ register/bus/interrupt model
→ firmware or driver interface
→ HDL or physical implementation
→ runtime readback
```

A hardware abstraction can execute on software, simulation, VM, FPGA, ASIC, or physical device backing without losing its canonical identity.

## BIOS and firmware profile

A custom BIOS/firmware request must define at minimum:

```text
processor architecture
reset vector
execution mode
memory discovery
firmware volume/layout
platform initialization phases
device discovery
interrupt/timer facilities
boot handoff protocol
security root and update policy
recovery path
serial/visual debug anchor
```

UEFI, Multiboot2, coreboot, or a custom handoff are target profiles—not mandatory architecture identities.

## Server profile

A server request must define:

```text
protocols
network bindings
request/response schemas
concurrency model
persistence
identity/authentication
rate and resource limits
health/readiness/liveness
observability
failure isolation
recovery and migration
deployment targets
```

## Validation gates

```text
GATE_KIR_01_IDENTITIES_COMPLETE
GATE_KIR_02_SEMANTICS_DEFINED
GATE_KIR_03_TOPOLOGY_VALID
GATE_KIR_04_STATE_TRANSITIONS_TOTAL
GATE_KIR_05_DATA_REPRESENTATIONS_TYPED
GATE_KIR_06_EXECUTION_TARGET_DECLARED
GATE_KIR_07_HARDWARE_CONTRACT_DECLARED_WHERE_APPLICABLE
GATE_KIR_08_LOWERING_MAPPING_COMPLETE
GATE_KIR_09_TARGET_TOOLCHAIN_EXECUTED
GATE_KIR_10_BILATERAL_READBACK_COMPLETE
GATE_KIR_11_SEMANTIC_EQUIVALENCE_RESOLVED
GATE_KIR_12_ARTIFACTS_DURABLY_PRESERVED
```
