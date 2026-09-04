# Executor Qualification Standard R1

## Purpose

An executor is an evidence-producing engineering dependency. Its availability and capability are separate from the correctness of the system under test.

## Admission sequence

1. Identify the executor and intended proof level.
2. Probe required capabilities on the actual executor.
3. Record an environment fingerprint from observed runtime properties.
4. Execute a deterministic sentinel before substantive qualification.
5. Execute the governed test or experiment.
6. Persist the receipt and source revision.
7. Reconcile the receipt against the claim's required evidence level.

## Required distinctions

- `AVAILABLE` means the executor passed its declared capability probe.
- `UNAVAILABLE` means the executor cannot currently carry the required proof.
- `BLOCKED` means execution was prevented by a control or infrastructure boundary.
- A failed application test is evidence about the application, but a job that never reaches a workflow step is not.

## Minimum receipt fields

`executor_id`, `kind`, `environment_fingerprint`, capability results, source revision, test/experiment identifier, status, timestamps, artifact digests, and observed failure boundary.

## Security baseline

Qualification workflows use least-privilege permissions, reviewed immutable Action references, explicit source revisions, and deterministic artifact identification. Credentials are never placed in receipts.

## Promotion rule

Executor existence, workflow dispatch, queue state, compilation, or artifact creation never independently promotes a claim. Promotion requires the required proof receipts at or above the claim's declared evidence level.
