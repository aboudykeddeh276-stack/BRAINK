# IL-LLM Bilateral Translation Contract

## Identity

```text
contract://keddeh/il-llm-bilateral-translation
version: 1.0.0
```

## Governing role

IL-LLM is the translation layer between observed language, canonical KEDDEH meaning, KIR objects, source-language implementations, runtime behaviour, and evidence readback.

It shall not act as an unconstrained code generator. It performs typed translation with preserved source lineage.

## Bilateral lifecycle

```text
ANCHOR
→ FACTOR
→ TRANSLATE
→ ACT
→ VALIDATE
→ TOKENIZE
→ PRESERVE
→ RETURN
```

### ANCHOR

Resolve canonical words, systems, domains, interfaces, states, units, and source authorities.

### FACTOR

Decompose the request into independent semantic, topology, state, data, execution, hardware, policy, and evidence obligations.

### TRANSLATE

Create or update KIR without prematurely selecting a target language.

### ACT

Select the target language/runtime/hardware projection from the execution contract and language-target matrix.

### VALIDATE

Compile, link, synthesize, simulate, test, deploy, or inspect according to the target class.

### TOKENIZE

Convert observed target results into canonical typed evidence objects rather than free-form success text.

### PRESERVE

Store source, KIR, target artifacts, receipts, hashes, topology deltas, and translation mappings.

### RETURN

Raise observed behaviour back into KIR and compare against the source contract.

## Required translation record

```json
{
  "translation_id": "translation://...",
  "source_identities": [],
  "source_language": "natural-language|C|C++|Rust|Assembly|Python|TypeScript|SystemVerilog|...",
  "source_semantics": [],
  "kir_objects": [],
  "target_language": "...",
  "target_runtime": "...",
  "target_hardware": "...",
  "lowering_rules": [],
  "inserted_adapters": [],
  "known_translation_gaps": [],
  "validation_evidence": [],
  "raised_readback": [],
  "equivalence_state": "SEMANTIC_EQUIVALENT|SEMANTIC_EQUIVALENT_WITH_DECLARED_ADAPTERS|PARTIAL_EQUIVALENCE|TRANSLATION_GAP|INVALID_TARGET",
  "global_stop": false
}
```

## Round-trip invariant

For a source contract `S`, lowering function `L`, target observation `O`, and raising function `R`:

```text
R(O(L(S))) ≈ S
```

The approximation symbol is resolved through explicit semantic obligations. No obligation may disappear silently.

## Language neutrality

The same KIR object may have multiple projections:

```text
interface://storage/read/v1
├── C ABI function
├── Rust trait
├── Go interface
├── TypeScript API client
├── OpenAPI operation
├── SystemVerilog bus transaction
└── workbook formula/trigger contract
```

The projections are equivalent only if their declared state, data, ordering, failure, and evidence semantics match.

## Hardware abstraction

Hardware abstraction is bilateral:

```text
software requirement
→ abstract hardware capability
→ register/bus/interrupt/timing contract
→ firmware/driver/HDL projection
→ simulation or physical execution
→ signal/register/receipt readback
→ canonical hardware capability state
```

A simulation proves the model execution state, not physical hardware execution. A physical receipt may promote the same canonical capability without creating a different identity.

## Translation failure handling

A missing compiler, synthesizer, hardware provider, or execution target removes only the corresponding validation input.

```text
path_a = target-native compile/synthesis/execution
path_b = compatible hosted or simulated execution
path_c = static semantic/model validation with preserved work packet
```

The unresolved proof class remains explicit.

## Prohibited behaviours

```text
generating code before resolving topology and interfaces
selecting a language by habit rather than execution requirements
silently replacing hardware semantics with software semantics
claiming source-to-target equivalence from compilation alone
erasing source terminology during normalization
flattening simulation, emulation, hosted execution, and physical execution
losing units, timing, privilege, memory, or failure semantics
```
