# BRAINK Linguistic Engine v1

## Purpose

BRAINK Linguistic Engine v1 defines a deterministic, provenance-preserving bridge from bounded numeric state into an English projection using the periodic table as a canonical anchor vocabulary.

The engine does **not** claim that chemistry alone defines natural-language semantics. Atomic number, symbol and element name are canonical anchors. Property words, grammatical roles and memory-array modifiers are versioned linguistic policy.

## Core pipeline

```text
numeric state
  -> atomic-number validation
  -> canonical element anchor
  -> optional typed property relation
  -> memory-array modifier
  -> English projection
  -> semantic root + provenance
```

## Invariants

1. Atomic identity is preserved and reversible from every projection.
2. English projection cannot mutate source numeric state.
3. Element identity and linguistic property policy are separate namespaces.
4. A property term must be explicitly registered before projection.
5. A memory-array modifier may alter degree/expression but never element identity.
6. Zero does not silently map to an element.
7. Values outside 1..118 do not silently fold, wrap or modulo into the periodic table.
8. No human identity field is required or emitted by the engine.
9. Every projection emits a deterministic semantic root over canonical JSON.
10. Property mappings and modifier mappings are versioned policy and therefore auditable/revisable.

## Canonical atomic anchor

```json
{
  "atomic_number": 8,
  "symbol": "O",
  "name": "Oxygen"
}
```

Atomic number is the primary numeric anchor because it is one-to-one within the current periodic table. Symbols and English names are projections of that anchor.

## Memory-array modifiers

The initial modifier contract is:

| Memory class | Degree | Default English family |
| --- | --- | --- |
| `Array(1)` | BASE | no modifier |
| `Array(+1)` | HIGH | strong / high / intense |
| `Array(-1)` | LOW | weak / low / inhibited |
| `Array(.1)` | SOFT | slight / minor / faint |
| `Array(/1)` | NORMALIZED | balanced / even / proportional |
| `Array(+M1)` | META_HIGH | dominant / primary / major |
| `Array(-M1)` | META_LOW | suppressed / reduced / minor |

The first implementation chooses the first term as the deterministic default projection. Future policy versions may select among registered synonyms only if the selection rule is itself deterministic and provenance-bearing.

## Typed relations

Properties are not assumed from an element name. They are explicit relations:

```text
ElementAnchor --[PROPERTY_POLICY_V1:reactive]--> adjective:reactive
```

A property entry declares at minimum:

```json
{
  "property_id": "reactive",
  "pos": "adjective",
  "english": "reactive",
  "policy_version": "PROPERTY_POLICY_V1"
}
```

This prevents `Oxygen` from being treated as semantically identical to `reactive`, `gas`, `essential`, or any other contextual description.

## Example

Input:

```json
{
  "numeric_state": 8,
  "property_id": "reactive",
  "memory_array": "Array(+1)"
}
```

Projection:

```text
strong reactive Oxygen
```

The projection remains linked to numeric state `8`, element `O`, property policy `reactive`, and modifier `Array(+1)`.

## IL-LLM integration

BRAINK/IL-LLM should treat the engine as a bounded projection function, not as global semantic authority.

```text
producer numeric event
  -> CausalID
  -> BRAINK linguistic projection
  -> linguistic ledger
  -> optional downstream parser/renderer
```

The original numeric event remains authoritative for numeric state. The linguistic ledger contains a derived observer projection sharing the same causal identity.

## Natural-language boundary

This layer provides a stable vocabulary anchor and deterministic descriptor composition. It does not, by itself, solve full English syntax, pragmatics, polysemy, discourse, world knowledge, tense, reference resolution, or reasoning.

Those require additional governed layers such as:

```text
anchor ontology
-> relation grammar
-> composition grammar
-> sentence planner
-> discourse/context layer
-> parser/reverse mapper
```

The crucial invariant is that each later layer remains traceable back to the numeric/atomic anchor and cannot silently overwrite producer truth.

## Runtime implementation

`runtime/linguistics/braink_linguistic_engine.py`

Supported operations:

```bash
python -m runtime.linguistics.braink_linguistic_engine --self-test
python -m runtime.linguistics.braink_linguistic_engine --atomic-number 8 --property reactive --memory-array 'Array(+1)'
```

## Promotion states

```text
DEFINED
-> IMPLEMENTED
-> SELF_TESTED
-> IL_LLM_BOUND
-> REVERSE_MAPPING_TESTED
-> COMPOSITION_TESTED
-> RUNTIME_PROVEN
```

The current repository commit establishes `IMPLEMENTED`. Later states require observed execution evidence.
