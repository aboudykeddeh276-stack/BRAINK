---
name: braink-reflex-loop
description: Use BRAINK as the control owner and tool OpenAI/ChatGPT/Codex through BRAINK's MCP surface, returning model/tool results into BRAINK for validation, persistence, and the next state transition.
---

# BRAINK Reflex Loop

The orchestration direction is:

`BRAINK -> OpenAI Responses API -> BRAINK MCP tools -> OpenAI result -> BRAINK validation -> BRAINK commit/next transition`

BRAINK remains the owner of identity, lineage, state, proof, persistence, approval policy, and continuation.

OpenAI/ChatGPT/Codex is a callable reasoning/tool substrate inside the BRAINK control loop.

## Required behavior

1. Load the current BRAINK receipt/state set before an OpenAI call.
2. Hash the state supplied to the external model.
3. Expose only the BRAINK MCP server and explicitly approved external tools needed for the objective.
4. Keep read-only BRAINK tools callable without approval when appropriate.
5. Keep mutating BRAINK tools approval-gated.
6. Accept OpenAI output as a proposed state delta, never as authoritative BRAINK state.
7. Persist the response ID, tool outputs, proposed-delta digest, and unresolved boundaries in a BRAINK receipt.
8. Validate the delta against BRAINK invariants before commit.
9. Only BRAINK decides whether to commit, reject, retry, call another tool, or begin another reflex cycle.

## Storage invariant

`ENCODED_MEDIUM -> ZEROLESS_GEOMETRY -> CONTROLLER -> LOGICAL_OBJECTS -> VFS_RESOLVER`

VFS is resolver/namespace only.

## External authority invariant

Never promote DNS, registrar/registry, CA/TLS, WAN, deployment, or persistence state from model prose. Require direct adapter/tool evidence and readback.

## Recursion rule

A model invoked by BRAINK may call BRAINK tools through MCP. Tool results return to the model to finish its bounded task, then the complete result returns to BRAINK. This is a reflex cycle, not ownership transfer.

`B_t -> OAI(B_t, MCP_B) -> Delta_candidate -> Validate_B -> B_(t+1)`
