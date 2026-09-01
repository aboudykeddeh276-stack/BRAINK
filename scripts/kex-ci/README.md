# KEX Verification, Demonstration and Benchmark Tools

This directory contains local verification tools. It is not the runtime host. Resident liveness belongs to the BRAINK/KEX service supervisors and resident controller.

## Primary commands

### Integrated IL-LLM demo

```bash
python3 scripts/kex-ci/demo_massive_illlm.py
```

Exercises, in one process:

- hydration of the global IL-LLM-of-IL-LLMs topology;
- contextual executable resolution;
- definitions and definitions-of-definitions;
- semi-naive delta fact propagation;
- duplicate-fact avoidance;
- proof-obligation derivation;
- alternate/equivalent representation retention and extraction;
- contextual intent-to-capability translation;
- machine-readable demo report hashing.

Expected report:

`reports/kex-wbos/illlm-massive-demo.json`

A source file being present is not a passing demo. `status: PASS` must come from an executed run.

### IL-LLM phenomenon benchmark

```bash
python3 scripts/kex-ci/benchmark_illlm_phenomenon.py --sizes 1000,5000,10000 --repeats 100
```

Measures separately:

- naive whole-estate scan vs resident contextual indices;
- naive definition scanning vs indexed definition-chain traversal;
- full graph rebuild vs local delta mutation;
- intent-to-capability translation latency;
- empirical scaling exponents across estate sizes.

Expected report:

`reports/kex-wbos/illlm-phenomenon-benchmark.json`

Synthetic benchmark results are engineering evidence for algorithms/data structures, not production throughput claims. Market performance requires repetition on the real resident corpus and target host.

### Higher-order traversal microbenchmark

```bash
python3 scripts/kex-ci/benchmark_illlm_higher_order.py
```

This older benchmark isolates topology construction vs warm traversal/re-entry. It remains useful as a microbenchmark but should not substitute for `benchmark_illlm_phenomenon.py` when discussing the wider IL-LLM claim.

### Runtime hardening

`test_runtime_hardening.py` is the hostile/security/integrity suite for action runtime behavior. Tests must use isolated evidence paths and must never destroy resident ledgers.

### Workbook/API verification

`test_wbos_api.py` exercises source-not-resident → activation → resident workbook data behavior, root-matrix statistics, filters, object lookups and workbook combination.

## Evidence classes

Verification tools should report one of the following rather than silently promoting state:

```text
SOURCE_RESIDENT
STATIC_VALIDATION
LOCAL_PASS
LOCAL_FAIL
TARGET_HOST_REQUIRED
TL2_REQUIRED
EXTERNAL_GATE
PUBLIC_READBACK_REQUIRED
BENCHMARK_REQUIRED
```

## Benchmark methodology

For a claimed IL-LLM acceleration, measure at least:

- median and p95 latency;
- object/fact/edge count;
- candidate-set size;
- definition depth;
- number of rule evaluations;
- graph-build cost;
- delta-update cost;
- memory footprint where available;
- scaling relationship `T(N) ≈ kN^α` over multiple `N` values.

A useful architectural result is not merely one fast measurement. The stronger result is a repeatable difference in scaling behavior between reconstruction-heavy and resident-traversal paths.

## Research donors

The tests and benchmarks intentionally probe mechanics inspired by established systems work:

- differential/incremental computation;
- Rete-style retained pattern work;
- e-graph/equality-saturation representation retention;
- capability/reference-monitor boundaries;
- content addressing;
- event-sourced/replayable evidence;
- supervised resident services.

The test suite must validate the transferred mechanic without claiming identity with the donor system.
