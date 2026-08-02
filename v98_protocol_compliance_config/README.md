# KEDDEH V98 Protocol Compliance Deployment OS

This directory seeds the V98 protocol, compliance, ISO/reference-pack and deployment-control layer for the KEDDEH Functional Service Spine.

Purpose:

- define the service protocol contract: `recognize -> execute -> verify -> write_receipt -> readback -> handoff`
- populate standards/reference packs for lifecycle, AI governance, information security, secure SDLC, software assurance, supply-chain provenance, SBOM and target-host gates
- enforce the authority rule that humans and coding agents may define or edit, but only the acceptance harness may promote `LOCAL_PASS`
- prepare a self-hosted macOS ARM64 GitHub Actions workflow for the real M3 workstation runner
- preserve certification and provider boundaries until executable receipts exist

Local run:

```bash
cd v98_protocol_compliance_config
python3 -m compileall src tests
python3 src/keddeh_v98_acceptance_harness.py --root . --emit-receipt
python3 -m pytest -q
```

Deployment rule: this pack is evidence-ready configuration, not external ISO certification. External certification, remote provider attestation, launchd installation, and self-hosted M3 runner proof are target-host/provider gates until receipts are produced.
