# V99 Semantic Knowledge Graph

The codebase is treated as an executable encyclopedia of contextual state transitions. A source word becomes a canonical definition page, a contextual use becomes a word instance, grouped words become expression pages, and an execution becomes a story transition backed by receipts.

This prevents code from behaving as isolated files. Services, words, expressions, code bindings and receipts are backlinked so a function can answer what it means, which definition authorized that meaning, which service executes it, which sector owns it, and which evidence proves its bounded result.

## Direct command

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_semantic_knowledge_graph.py --root . --emit-receipt
python3 -m unittest tests.test_semantic_knowledge_graph -v
```

## Outputs

- `evidence/semantic_knowledge_graph_receipt.json`
- `exports/semantic_knowledge_graph_edges.csv`
- `exports/semantic_knowledge_graph_bindings.csv`
- `runtime_volume/semantic_graph/current_context.json`
- `runtime_volume/semantic_graph/transition_ledger.jsonl`
- `runtime_volume/outbox/semantic_knowledge_graph/*.handoff.json`

## Governance rule

A semantic conformance failure occurs when a code object declares a word but implements weaker behaviour. For example, `VERIFY` cannot mean only file existence; it must read, compare, validate, record the result and emit evidence.
