# BRAINK Signal Node

`runtime://braink/signal-node` is a minimal activation membrane, not a replacement orchestrator.

Execution law:

`SIGNAL -> AUTHORITY -> TARGET RESOLUTION -> RESIDENT ACTUATOR -> OBSERVED RECEIPT -> NEXT STATE`

Signal kinds are `POWER`, `SUB_POWER`, `TRIGGER`, `RETRIGGER`, and `POWER_RESET`.

The node deliberately does not own CasePath, ClaimPath, network, registrar, server, workbook, KEX, or other sector semantics. Those mechanics stay in their resident implementations. The node only activates a registered mechanic and cryptographically chains the observed receipt.

Duplicate signal delivery is idempotent. Deliberate `RETRIGGER` is a separate activation. `POWER_RESET` enters reset, invokes the resident reset actuator, then records the target as `ON` after observed return.
