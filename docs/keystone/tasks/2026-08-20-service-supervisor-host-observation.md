# BRAINK Service Supervisor — Slice 1B Host Observation

Status: AUTHORIZED TASK / NOT IMPLEMENTED
Date: 2026-08-20
Parent: Service Supervisor discovery/classification Slice 1A

## Goal

Prove a read-only vertical path from real host/runtime observations into the existing deterministic ServiceObservation classifier without introducing process mutation.

Canonical path:

HOST/RUNTIME → RAW OBSERVATIONS → NORMALIZED EVIDENCE → ServiceObservation → CLASSIFIER → ServiceSnapshot

Bitcoin Core is the first qualification target because it exercises process identity, external-vs-BRAINK ownership, RPC health, chain identity and daemon persistence semantics.

## Preserved invariants

1. Observation does not imply ownership.
2. Ownership does not follow from health.
3. Process presence does not imply service health.
4. RPC success does not by itself prove process identity.
5. UNOBSERVED is distinct from ABSENT.
6. PID equality alone is insufficient identity proof.
7. Shutdown authority requires verified identity plus explicit BRAINK ownership.
8. Slice 1B is read-only: no start, stop, signal, restart, adopt, install or process mutation.
9. Existing BTC, NativeChatBot and historical runtime behavior remains unchanged.
10. Host-process identity is one service-identity realization, not the universal BRAINK service model.

## Vertical slice

### Input
A service observation request naming a service descriptor, initially Bitcoin Core.

### Host observations
Collect read-only evidence where available:
- PID/process presence;
- process start identity/time;
- executable path;
- command line;
- parent PID/relationship;
- listening sockets/endpoints;
- service-manager/launchd evidence when available;
- Bitcoin RPC reachability;
- Bitcoin RPC chain, IBD, verification progress, best block and height.

Missing probes must be represented as UNOBSERVED, not fabricated defaults.

### Normalization
Normalize raw probe results into an immutable observation record with:
- observation_id;
- service_id;
- observed_at;
- observer/source identity;
- raw evidence references/values;
- contradictions;
- evidence classifications.

### Classification
Map normalized evidence into the existing `ServiceObservation` contract. The existing classifier remains the authority for identity/ownership/health/lifecycle classification.

### Output
Return a `ServiceSnapshot` containing:
- service identity result;
- ownership result;
- health result;
- lifecycle result;
- shutdown authority;
- evidence/contradictions;
- raw observation linkage.

## Failure semantics

- Probe unavailable → corresponding field UNOBSERVED.
- PID found but executable/start identity conflicts → IDENTITY_CONFLICT.
- RPC healthy but process identity unverified → health may be observed while identity remains unverified.
- Process present but RPC unavailable → process presence remains observed; service health is degraded/unobserved according to evidence.
- Contradictory observations are retained and fail closed; they are not silently reconciled.

## Acceptance criteria

1. Running observation performs no host mutation.
2. The same normalized evidence deterministically produces the same classification.
3. PID reuse is detectable when start identity differs.
4. Executable substitution is detectable.
5. External healthy Bitcoin Core remains external and has no shutdown authority.
6. A BRAINK-owned record does not gain shutdown authority unless identity is verified.
7. RPC health and process identity are independently represented.
8. Chain/network identity is independently recorded when RPC evidence is available.
9. Missing host capabilities remain UNOBSERVED.
10. Raw evidence and contradictions remain inspectable after classification.
11. Existing Slice 1A tests continue to pass.
12. Existing BTC consensus regression tests continue to pass.
13. New tests prove no process-mutating API is exposed by the observer.
14. No consumer can promote UNKNOWN/EXTERNAL ownership to BRAINK_OWNED from observation alone.
15. No lifecycle mutation is authorized by this slice.

## Required characterization/adversarial tests

- no observation available;
- process absent;
- external healthy bitcoind;
- BRAINK-owned matching bitcoind record;
- reused PID with changed start identity;
- matching PID/start but changed executable;
- process exists / RPC unavailable;
- RPC healthy / process identity unverified;
- chain mismatch;
- contradictory evidence;
- partial probe failure;
- repeated identical observation is deterministic;
- observer surface contains no start/stop/restart/signal mutation.

## Review focus

- accidental mutation through probes;
- shell injection/unsafe command construction;
- PID-only identity assumptions;
- ownership inference from executable name/path;
- ownership inference from RPC success;
- conflation of health and lifecycle;
- swallowed contradictions;
- platform assumptions that prevent later non-process service identities.

## Promotion gate

Slice 1B may be promoted only after:

IMPLEMENTED → CHARACTERIZATION EXECUTED → INHERITED REGRESSION EXECUTED → ADVERSARIAL IDENTITY TESTS PASS → CHANGE REVIEW

A passing CI run proves only the tested host-observation/classification properties. It does not prove generalized BRAINK service supervision or lifecycle control.

## Deferred

Start/stop/restart, adoption, watchdog/restart policy, LaunchAgent installation, forced termination, persistent mining loops, V86 lifecycle mutation, mesh supervision and generalized distributed service control.
