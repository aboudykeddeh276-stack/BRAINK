# BRAINK Zero-Less Governance Standard

This repository enforces explicit zero-less governance for routing and error reporting.

## Zero-Less index spectrum

- Allowed logical indices: `[-3, -2, 1, 2, 3]`
- Index `0` is invalid for governance-mapped runtime state.
- Swift source of truth: `NativeChatBot/Sources/ZeroLessGovernance.swift`

## Explicit route governance

Routes are represented by `BRAINKRouteIdentifier` and mapped to explicit governance identifiers:

- `route:engine:*`
- `route:svc:*`
- `route:sys:*`

No implicit runtime transitions are allowed in governance mappings.

## Error context format

Runtime failures must include complete context:

- `id`
- `sector`
- `cause`
- `stage`
- `message`
- `timestamp`
- `deadRoute` (optional)
- `recoveryRoute` (optional)
- `metadata`

Swift source of truth: `NativeChatBot/Sources/ErrorContext.swift`

## Dead route registry

Known dead/fragile routes are tracked in:

- `NativeChatBot/Sources/DeadRouteRegistry.swift`

Fallback recovery routes are explicit and deterministic.

## Proof packet compatibility

Proof packet generation remains deterministic and local-first. When an external route fails, the runtime records error context and falls back to local deterministic handling.
