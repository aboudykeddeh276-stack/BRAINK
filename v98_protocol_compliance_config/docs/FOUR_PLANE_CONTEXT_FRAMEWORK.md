# V99 Four-Plane Context Framework

The active framework has four coupled but non-collapsible planes:

1. output framework — what a service presents or exports;
2. thinking framework — how propositions are formed and tested;
3. legal perspective — party account, authority, evidence, admissibility, procedure and legal determination kept distinct;
4. software service — schemas, APIs, execution, persistence, UI, security and receipts.

Each plane preserves its own `S=f(I,V,O,E,X,R,L)` context. Legal conclusions cannot be inherited from software tests, polished outputs cannot prove reasoning paths, internal reasoning cannot silently become court fact, and software receipts cannot become legal determinations.

## Direct command

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_four_plane_context_framework.py --root . --emit-receipt
python3 -m unittest tests.test_four_plane_context_framework -v
```

## Outputs

- `evidence/four_plane_context_framework_receipt.json`
- `exports/four_plane_context_framework_matrix.csv`
- `exports/four_plane_cross_plane_guards.csv`
- `runtime_volume/workplans/four_plane_context/*.json`
- `runtime_volume/outbox/four_plane_context_framework/*.handoff.json`

## Boundary

This is a governance and conformance layer. It does not turn reasoning into evidence, software into law, output into truth, or legal perspective into court finding. It preserves the appropriate plane until receipt, authority, procedure and lineage allow a bounded relation.
