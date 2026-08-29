# V98 Protocols, Conventions and Frameworks

## Naming conventions

- Service identifiers use lowercase snake_case.
- Gate identifiers use `TG-##`.
- Control objectives use `CO-##`.
- Protocols use `P##`.
- Receipts are JSON objects and ledger entries are JSON Lines.

## Functional convention

Every callable service must implement the same operational semantics, even when the concrete implementation differs:

```text
recognize()
execute()
verify()
write_receipt()
readback()
handoff()
```

## Evidence convention

Allowed states:

```text
LOCAL_PASS
LOCAL_FAIL
TARGET_HOST_REQUIRED
PROVIDER_REQUIRED
EXTERNAL_CERTIFICATION_REQUIRED
UNSUPPORTED_IN_THIS_RUNTIME
REFERENCE_ALIGNMENT_ONLY
```

## Authority convention

The architecture owner defines the target. Codex may implement. ChatGPT may audit and design acceptance criteria. Gemini/SIMB may peer-review only after provider gates exist. The self-hosted M3 runner and acceptance harness own local pass promotion.

## Virtual CPU / GPU convention

Virtual CPU is responsible for execution, state transitions, tests, negative-space falsifiers, ledger writes and readbacks.

Virtual GPU is responsible for dashboard rendering, telemetry projection and frame/state display. It does not promote correctness.

## Compliance convention

Standards mappings are alignment references until certification or qualified assessment evidence exists. No ISO, MISRA, DO-178C or external security status may be claimed from labels alone.
