# Mirror Update Lane Development Specification

## Functional contract

Every mirror lane service execution uses the same contract as the main V98 service spine:

```text
recognize -> execute -> verify -> write_receipt -> readback -> handoff
```

## Mirror source rule

A mirror lane update is valid only when every configured source document exists and every required mirror document exists. The lane then records each source document's path, byte length and digest as custody metadata. The digest is a custody control, not functional proof.

## Execution phases

1. Load `config/mirror_update_lane.json`.
2. Verify that the lane configuration rejects manual and agent self-promotion.
3. Verify source research/development/compliance/configuration documents.
4. Verify mirror-lane research and development documents.
5. Write a JSON receipt to `evidence/mirror_update_lane_receipt.json`.
6. Append the receipt to `runtime_volume/proof_bundles.ledger`.
7. Read the ledger back and verify the mirror lane entry exists.
8. Emit `exports/mirror_update_lane_matrix.csv`.
9. Emit an outbox handoff under `runtime_volume/outbox/mirror_update_lane/`.

## Development rule

The mirror lane must not change the authority model. It may mirror, audit, package and hand off. It may not promote a target-host, provider, certification, launchd, public DNS, physical VFS or remote-attestation claim without receipts.
