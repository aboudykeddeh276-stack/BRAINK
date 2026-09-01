# IL-LLM Conversation Delta Operating Protocol R1

## Purpose
User steering, corrections, naming clarifications, lineage corrections and conceptual refinements are operational deltas. They must update the active model without replacing the primary engineering task unless the user explicitly changes the task.

## Two-lane rule

### Primary execution lane
Continue the active engineering objective, implementation queue, tests, readback, documentation and promotion gates.

### Conversation delta lane
For each user correction:
1. classify the delta: naming, invariant, lineage, architecture, evidence, priority, authority, or execution constraint;
2. identify the smallest affected definitions/modules/reports;
3. patch those affected objects;
4. record contradictions or superseded claims;
5. re-enter the primary execution lane immediately.

## Non-interruption invariant
A conversational correction MUST NOT become the new primary task merely because it is important. It becomes the primary task only when the user explicitly redirects execution or when continuing would violate a corrected safety/correctness invariant.

## IL-LLM integration
Conversation deltas are first-class learning events:

CURRENT_CONTEXT -> USER_DELTA -> CLASSIFY -> UPDATE_DEFINITIONS -> UPDATE_MIRROR_LANE -> RECOMPUTE_AFFECTED_RELATIONS -> RESUME_EXECUTION

The delta should be represented as machine-addressable evidence with:
- affected identities;
- prior definition/classification;
- replacement definition/classification;
- reason/source;
- affected modules/tests/reports;
- whether runtime execution must be invalidated or repeated.

## Mirror Lane rule
Corrections update observer-relative projections and learning lineage. They do not silently rewrite canonical history. Prior states remain available for provenance and regression analysis.

## Promotion rule
A conversational correction can invalidate a prior claim or test interpretation, but does not by itself prove the replacement implementation. Implementation and execution claims remain receipt-bound.

## Failure condition
The operating process is defective if it repeatedly stops engineering work to explain a correction instead of applying the correction as a bounded semantic delta and continuing the active task.
