# KEDDEH Systems Sector Benchmark Qualification R1

## Purpose

A sector is not production-qualified merely because its own tests pass. Internal tests establish implementation correctness relative to declared contracts; production qualification requires comparison against established computer-science and infrastructure baselines appropriate to the mechanic under test.

## Calibration Baselines

The current KEX/BRAINK architecture is structurally comparable, by mechanic rather than by branding, to established classes including:

- actor supervision and failure containment;
- checkpoint/restart and process rehydration;
- process/state migration;
- authoritative DNS service;
- append-only and evidence-oriented state lineage;
- deterministic state-transition systems;
- orchestration with pre/post observation and actuator readback.

No performance or reliability claim may be promoted from structural similarity alone.

## Mandatory Benchmark Dimensions

Every executable sector must qualify, where applicable, against:

1. repeated-run determinism and variance;
2. single-thread and concurrent throughput;
3. latency distribution, not average latency alone;
4. restart and rehydration correctness;
5. persistence durability and readback;
6. malformed-input and failure-path behaviour;
7. resource consumption under sustained load;
8. state-lineage integrity across faults;
9. external-vantage verification when the mechanic crosses a host/network boundary;
10. comparison with established reference implementations or documented operational expectations.

## Domain / DNS / Registrar Qualification

For the Domain Authority and server descendants, evidence must include:

- repeated authoritative query runs;
- concurrent UDP query handling;
- concurrent TCP query handling;
- registrar write/read persistence;
- zone restart and rehydration;
- restart preservation of SOA/NS/A/AAAA/CNAME/MX/TXT/CAA state;
- authoritative NXDOMAIN with SOA authority section;
- malformed packet handling;
- unavailable/corrupt persistence-store behaviour;
- bind failure behaviour;
- duplicate/collision handling;
- private-interface and, when available, external-vantage readback;
- latency and throughput distributions;
- comparison against established authoritative DNS expectations rather than only self-comparison.

## Observer² Promotion Rule

A benchmark run follows the same evidence law as a mutation:

PRE-FRAME -> RUN -> POST-FRAME -> ENVIRONMENTAL DELTA -> RECEIPT -> COMPARISON -> QUALIFICATION

A process exit code or benchmark harness SUCCESS field is not itself qualification evidence.

## Promotion States

- STRUCTURALLY_IMPLEMENTED
- INTERNALLY_TESTED
- REPEATED_RUN_QUALIFIED
- CONCURRENCY_QUALIFIED
- RESTART_REHYDRATION_QUALIFIED
- PERSISTENCE_QUALIFIED
- FAILURE_PATH_QUALIFIED
- EXTERNAL_COMPARISON_QUALIFIED
- PRODUCTION_QUALIFIED

Promotion must be monotonic and evidence-backed. Missing stages remain explicitly unresolved.

## Repository Rule

Each canonical sector repository must retain benchmark inputs, environment description, raw result receipts, summarized metrics, comparison methodology, and the exact implementation commit tested.
