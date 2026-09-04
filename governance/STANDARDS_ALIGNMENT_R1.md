# BRAINK / KEX Standards Alignment R1

## Purpose

This document maps the estate engineering controls to established external practices. It does not claim certification or compliance. It identifies where BRAINK/KEX controls are aligned, where they extend project-specific semantics, and where independent assessment remains required.

## External reference set

- NIST SP 800-218 Secure Software Development Framework (SSDF), Version 1.1.
- NIST SP 800-218 Rev. 1 draft material may be monitored separately; draft status is not treated as a normative compliance target.
- GitHub Dependency Graph and Dependency Submission API.
- GitHub Actions secure-use guidance.
- SLSA Build requirements / provenance model.

## Mapping

| BRAINK/KEX control | External alignment | Evidence expected | Boundary |
|---|---|---|---|
| Exact source revision | SLSA provenance; reproducible build practice | commit SHA in receipt/provenance | Does not alone prove build integrity |
| Dependency graph fragments | GitHub Dependency Graph / Dependency Submission | machine-readable dependency snapshot/fragment | Project cross-repo edges may require custom representation |
| Explicit workflow permissions | GitHub Actions secure-use guidance | workflow `permissions` block and review | Runtime host permissions remain separate |
| Full-SHA action pinning | GitHub Actions secure-use guidance | action reference pinned to verified commit SHA | Pinning does not make an action inherently trustworthy |
| Evidence receipts | SLSA provenance concepts | signed or digest-bound receipt where implemented | Receipt quality depends on producer/executor integrity |
| Executor capability registry | SLSA build-environment concepts | executor capability declaration and observed execution | Project-specific extension |
| Owner-first dependency evolution | SSDF / supply-chain governance principles | owner repository, exact revision, consumer contract | Project-specific governance mechanism |
| Falsifiable research claims | SSDF risk reduction / engineering discipline | hypothesis, pass/fail condition, observations | Scientific validity still requires appropriate experimental design |
| Persistent state/recovery tests | SSDF resilience and verification practices | crash/restart/recovery evidence | Not a direct SSDF control equivalence |
| Cross-machine qualification | Build/environment integrity concepts | independent host receipts and environment identity | Requires actual independent hosts |
| External interoperability | System/network qualification | external protocol readback | Must use the actual external authority/carrier |

## Required interpretation

The project MUST NOT use an external framework label as a substitute for evidence.

Examples:

```text
"uses GitHub Dependency Graph" != complete dependency governance
"uses SLSA concepts" != SLSA conformance
"follows SSDF" != independent security assessment
"workflow passed" != deployment proof
"artifact exists" != runtime consumption proof
```

## GitHub Dependency Graph implementation target

GitHub's Dependency Submission API accepts dependency snapshots associated with a repository commit and workflow correlator. The estate SHOULD use this capability for dependencies that static manifest analysis cannot discover, including generated/build-time and cross-repository runtime dependencies where they can be represented as supported package URLs or an equivalent detector output.

The estate MUST retain its own richer dependency fragments because GitHub's package-oriented graph is not a replacement for the project's semantic authority/interface graph.

## Build provenance implementation target

For consequential releases, the estate SHOULD evolve receipts toward a provenance envelope containing at least:

```text
source revision
builder/executor identity
build invocation
resolved dependencies
artifact digest
material/input digests
creation timestamp
qualification evidence references
```

Where SLSA-compatible provenance is practical, it SHOULD be emitted in addition to the project-native evidence receipt rather than replacing it.

## Security hardening target

Workflow controls SHOULD progressively adopt:

1. explicit least-privilege `permissions`;
2. full-SHA action pinning;
3. reviewed third-party action source;
4. minimal checkout credentials and `persist-credentials: false` where authenticated git operations are unnecessary;
5. protected environments for deployment authority;
6. isolated runners for sensitive workloads;
7. explicit secret/credential boundaries;
8. artifact digest verification;
9. dependency review before promotion;
10. immutable release references.

## Cross-platform target

Standards alignment is expressed at the semantic capability layer, not by assuming one platform.

```text
capability contract
→ Linux adapter
→ macOS adapter
→ Windows adapter
→ container adapter
→ VM adapter
→ cloud adapter
```

An implementation may only claim cross-platform equivalence where the required capability contract is actually satisfied and observed.

## Review status

Current state:

```text
standards mapping             SPECIFIED
GitHub action SHA pinning     PARTIALLY APPLIED TO NEW QUALIFICATION LANES
Dependency fragments          IMPLEMENTED
Dependency submission         REQUIRES OBSERVED API EXECUTION
Provenance envelope           SPECIFIED / FUTURE IMPLEMENTATION
Cross-machine qualification   DEFINED / EXECUTION REQUIRED
Independent security review   NOT CLAIMED
Certification                 NOT CLAIMED
```

## Principle

External standards provide established engineering constraints and vocabulary. BRAINK/KEX project controls provide additional semantics for identity, authority, ownership, execution-carrier separation, research claims and evidence reconciliation. Neither layer should be represented as replacing the other.
