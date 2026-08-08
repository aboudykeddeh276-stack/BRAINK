# BRAINK^6 Engineering Runtime Skill

## Purpose
Use BRAINK^6 as the executable engineering tool for repository and runtime work. A skill name is never capability proof.

## Invocation invariant
REHYDRATE TASK -> RESOLVE CAPABILITY -> VERIFY KEX SEED -> RUN VALIDATORS -> UNLOCK -> EXECUTE -> VERIFY RESULT -> WRITE RECEIPT -> RETURN TO TASK.

## Mandatory boundaries
- Preserve the authoritative task and outstanding obligations across every subtask.
- NAME != SPECIFICATION != CAPABILITY.
- Never claim execution from source presence, a manifest, a hash, a test name, or a narrative.
- Never promote local/model/CI evidence into host, provider, Bitcoin-network, hardware, profitability, or deployment evidence.
- A discovered skill is subordinate to the task unless the task is explicitly changed.
- Failure is retained as typed negative knowledge and must alter the next relevant execution.

## Engineering loop
1. Rehydrate task identity from task envelope and assigned history.
2. Inspect the target environment and existing implementation before designing replacement code.
3. Build a dependency graph and acceptance predicates.
4. Reconstruct the required capability from its sealed definition.
5. Run capability validators; fail closed on corruption or validation failure.
6. Execute the smallest valid next obligation.
7. Independently test the predicate actually claimed.
8. Record result, evidence class, runtime boundary, failure state, and next action.
9. Propagate discoveries vertically, horizontally, backward, and forward.
10. Return to the authoritative task and continue until its acceptance contract is satisfied or a real external blocker is reached.

## Runtime evidence classes
- SOURCE_PRESENT
- MODEL_LOCAL_EXECUTED
- CONTAINER_EXECUTED
- CI_EXECUTED
- HOST_EXECUTED
- SERVICE_EXECUTED
- NETWORK_ACCEPTED
- HARDWARE_MEASURED
- ECONOMICALLY_REALISED

No evidence class implies a higher class.

## BTC conformance use
BTC is a demanding engineering workload for this skill. Correct behaviour includes: consensus-bound workload construction; no synthetic mainnet fallback; exact predicate boundaries; regtest/mainnet separation; complete-block submission; current-tip checks; explicit live-submit authority; and no profitability claim without measured cost/revenue evidence.
