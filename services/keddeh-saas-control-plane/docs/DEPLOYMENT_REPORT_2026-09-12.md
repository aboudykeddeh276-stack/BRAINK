# Deployment / Qualification Report — KEDDEH SaaS Control Plane R2.1

## What was amended
R2 had completion inflation in its own surface: the catalogue advertised capabilities broader than the executable implementation, CasePath/ClaimPath descriptor endpoints were described too strongly as adapters, and the candidate did not consume BRAINK's resident IL-LLM ledger/runtime registry.

R2.1 corrects those defects without replacing the working BRAINK mechanisms.

## Authority preserved
- BRAINK resident runtime/evidence code on `main` remains the upstream implementation.
- `runtime/illlm_ledger.py` is consumed directly.
- `runtime/runtime_registry.py` is consumed directly.
- a pre-existing runtime record is never overwritten by the candidate admission path;
- Linux/server execution carrier remains owned by `SERVERS-KEDDEHSYSTEMS`.

## Local observed qualification
Executed against a local reconstruction of the exact amended branch files and resident BRAINK runtime modules:

- pytest: `5 passed in 0.32s`;
- Python compileall: `PASS`;
- BRAINK IL-LLM evidence mirroring: `PASS`;
- local SQLite restart persistence: `PASS`;
- payment idempotency: `PASS`;
- DNTG -> SaaS mutation denial: `PASS`;
- existing RUNNING runtime preservation: `PASS`;
- Docker image build: `UNOBSERVED` because Docker CLI is absent in the current execution environment.

## Linux/server carrier
Canonical server-carrier implementation is staged separately in `aboudykeddeh276-stack/SERVERS-KEDDEHSYSTEMS` PR #3.

Observed static qualification for that carrier:

- full installer `bash -n`: `PASS`;
- validator Python compile: `PASS`.

Not observed:

- authorised target-host install;
- systemd process-active state on the target host;
- local host HTTP readback from that target host;
- restart/rehydration on that host;
- public ingress;
- production promotion.

## GitHub Actions boundary
The amended BRAINK workflow continues to fail before execution. For branch head `b17c3fd65929557c722fe636d0f056c155da2621`, workflow run `34661609404`, job `103465094801` received `runner_id=0`, an empty runner name, and zero steps. Therefore GitHub-hosted CI execution remains `UNOBSERVED`; this is not an application-test failure.

## Completion corrections
The live catalogue now separates:

- `implemented`;
- `descriptor_only`;
- `declared_unbound`.

The machine-readable `evidence/COMPLETION_LEDGER_R2_1.json` records each property's actual state. `fully populated`, `production deployed`, `CasePath adapter implemented`, `ClaimPath adapter implemented`, and `CI passed` are explicitly prohibited summary claims for the current evidence state.

## Current state

`BRAINK_INTEGRATED_LOCALLY / AUTHORITY_PRESERVATION_TESTED / SERVER_CARRIER_STAGED / HOST_EXECUTION_UNOBSERVED / PUBLIC_INGRESS_UNBOUND / PRODUCTION_NOT_PROMOTED`
