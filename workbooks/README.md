# Workbook Substrate

Workbooks are a primary KEX/IL-LLM carrier, not a peripheral import format.

They combine several properties that are unusually valuable to this architecture:

```text
human-readable state
+ machine-readable tables
+ formulas
+ dependency graphs
+ named domains
+ validation rules
+ cross-sheet relations
+ ordered state/history
+ portable file identity
```

That makes a workbook capable of carrying both knowledge and computation-adjacent structure in one object.

## IL-LLM role

The intended lowering path is:

```text
workbook
→ sheet / table / cell / formula identity
→ typed KEX object
→ semantic + mathematical relations
→ IL-LLM definition graph
→ executable/runtime relations
→ proof / readback
```

A cell is therefore not merely a value. Depending on the workbook, it may participate simultaneously in:

- a table schema;
- a mathematical expression;
- a dependency graph;
- a semantic/sector definition;
- a state transition;
- a runtime trigger or binding;
- an evidence/proof relation.

## Why this matters

A conventional document pipeline often has to rediscover structure from text. A well-formed workbook exposes much of that structure directly. Formulas already encode directed dependencies; tables and sheets already establish locality; typed cells and validation constrain values; names and ranges can carry stable semantic addresses.

That means workbook-native IL-LLM can reduce semantic reconstruction by preserving structure at ingest rather than flattening it to text and rebuilding it later.

## Current implementation

`modules/kex_wbos/workbook_api.py` discovers and parses resident `.xlsx`/`.xlsm` files and exposes named workbook datasets.

`modules/kex_wbos/workbook_semantics.py` builds bounded static semantic/dependency information from stored cells and formulas, including explicit range objects and strongly connected component/cycle analysis.

`action_extensions.py` contains workbook mutation support used by the action runtime.

`runtime/workbooks/` is the resident mount for activated workbook sources when present.

## Required next integration

Workbook semantics should become a direct IL-LLM hydration source rather than remain a sidecar-only analysis:

1. assign stable identities to workbook/sheet/table/cell/range/formula objects;
2. map formula references to typed traversal edges;
3. map headers/named ranges/tables to definitions and sector identities;
4. publish mathematical state into `illlm_executable_graph`;
5. publish dependency deltas into `illlm_delta_engine` after workbook mutation;
6. invalidate/rebuild only affected semantic regions where safe;
7. retain workbook/source SHA and cell/range provenance on every derived object;
8. attach executable lowerings only where a real runtime/action route exists.

## Claim boundary

Static parsing does not execute Excel formulas, VBA/macros, external links or host automation. Formula text and dependencies can be represented and traversed without claiming Excel-calculated values or macro execution.

Workbook combination modes must also distinguish value-only copy from structure-preserving or macro-aware composition. A copied cell value is not equivalent to a cloned workbook runtime.

## Market relevance

The workbook substrate gives BRAINK/IL-LLM an unusually practical bridge between human engineering work and machine traversal. Existing organisations already encode finance, engineering, operations, research, planning and compliance logic in spreadsheets. Preserving that structure rather than converting every workbook into unstructured text can reduce migration cost and expose executable/semantic relationships that ordinary document retrieval discards.

The market claim remains evidence-bound: the advantage should be quantified through real workbook workloads measuring preserved structure, reconstruction work avoided, query/traversal latency, update cost and correctness.
