# Mirror Update Lane Deployment Runbook

## Local execution

```bash
cd v98_protocol_compliance_config
python3 src/keddeh_mirror_update_lane.py --root . --emit-receipt
python3 -m unittest discover -s tests -v
```

## Workflow execution

The workflow `.github/workflows/v98-mirror-update-lane.yml` runs the mirror lane on the self-hosted macOS ARM64 runner labelled `KEDDEH-M3`.

## Produced evidence

- `evidence/mirror_update_lane_receipt.json`
- `exports/mirror_update_lane_matrix.csv`
- `runtime_volume/proof_bundles.ledger`
- `runtime_volume/outbox/mirror_update_lane/*.handoff.json`

## Promotion states

- `LOCAL_PASS`: source and mirror documents exist, receipt written, ledger readback passed, handoff package created.
- `TARGET_HOST_REQUIRED`: launchd, iostat, M3 physical host, dashboard frame-readback or physical VFS proof is required.
- `PROVIDER_REQUIRED`: external Drive/SIMB/Gemini/OpenAI transport or remote attestation is required.
- `EXTERNAL_CERTIFICATION_REQUIRED`: third-party ISO/MISRA/DO-178C certification or qualified assessment is required.

## Failure behavior

The lane must fail closed when a source document is missing, a mirror document is missing, authority rules allow manual promotion, the ledger entry cannot be read back, or an outbox handoff cannot be emitted.
