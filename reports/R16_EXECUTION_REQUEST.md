# BRAINK R16 Independent External Observer Execution

This branch exists only to produce an auditable pull-request-triggered execution of `.github/workflows/braink-external-observer-r16.yml` against the unchanged R15 probe semantics.

Expected evidence path:

`PR head commit -> GitHub Actions run -> job -> step logs -> uploaded BRAINK_R16_EXTERNAL_OBSERVER_RECEIPT.json artifact`

No public DNS/TLS/RDAP state is promoted unless the artifact contains direct successful readback.
