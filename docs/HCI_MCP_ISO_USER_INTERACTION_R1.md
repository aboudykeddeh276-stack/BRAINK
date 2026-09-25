# BRAINK HCI / MCP / ISO User Interaction R1

## Problem corrected

The previous dashboard contract promoted infrastructure state into the user's primary interaction surface. Nodes, runtimes, mesh state and process counters are useful diagnostic data, but they are not the user's goal.

R1 separates:

```text
USER INTENT
    ↓
HCI ACTION
    ↓
MCP CAPABILITY BINDING
    ↓
RUNTIME / SERVICE / FILE / TASK MECHANISM
    ↓
READBACK / PROOF
```

from:

```text
DIAGNOSTICS
    ↓
host / mesh / runtime / service internals
```

## Home contract

Primary actions:

- Ask BRAINK
- New task
- Open tasks
- Browse files

Secondary:

- Recent files
- System health

Diagnostics/admin controls are not primary home actions.

## MCP revision

The binding contract targets MCP `2026-07-28`.

MCP is an implementation capability layer, not the navigation hierarchy. User-visible actions are semantic intents. The router maps those intents onto tools/resources and authority scopes while retaining proof requirements.

The current implementation does not claim a complete MCP server. It establishes the product-facing routing contract and capability visibility boundary.

## ISO standards basis

### ISO 9241-210:2019
Current after 2025 review. Used as the human-centred design basis: system design begins from users, tasks and context rather than implementation structure.

### ISO 9241-110:2020
Current after 2025 review. Used for interaction principles and general design recommendations.

### ISO/IEC 25010:2023
Current product-quality model. Used to retain reliability/security/maintainability without allowing those engineering concerns to overwhelm interaction capability.

## Enforced invariants

The runtime tests enforce:

1. maintenance actions cannot be primary;
2. admin actions cannot be primary home actions;
3. destructive operations require confirmation;
4. privileged MCP bindings cannot become direct user controls;
5. normal-user MCP catalogs omit admin/diagnostic bindings;
6. the home surface exposes goal-level intent, not shell/process primitives;
7. system health remains secondary;
8. diagnostics remain available on demand.

## Gateway projection

New public gateway surfaces:

- `GET /home/summary`
- `GET /mcp/workflows`
- `GET /diagnostics/summary`

The legacy `/dashboards/summary` remains for compatibility but is no longer the intended home contract.

Unbound task/file services are explicitly returned as `UNBOUND`. The gateway does not invent data or claim execution merely because the UI has a button.

## Evidence

Local execution:

```text
tests/test_hci_mcp.py
9 passed
```

## Remaining engineering boundary

Still separate:
- actual persistent task provider;
- user file-resource provider;
- full MCP transport/server implementation;
- authenticated admin surface;
- usability testing with representative users;
- accessibility conformance testing;
- measured task completion/error/time-on-task evidence.

Those are not satisfied by changing the layout and therefore remain explicit.
