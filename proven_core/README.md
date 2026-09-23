# KEX Proven Core R1

This subtree is deliberately bounded to mechanics that can be executed and verified locally.

It implements:
- distinct logical surfaces and ancestry rather than a flat product registry;
- stable logical identity and canonical keys;
- a single KEX mutation-admission gate;
- stale-delta fencing and explicit rejection of identity renaming;
- append-only hash-chained proof receipts;
- fail-closed public promotion requiring REGISTRAR, DNS, INGRESS, TLS and HTTP_READBACK receipts;
- a local projection that is not silently promoted into external/public execution.

It does **not** claim public DNS, registrar control, TLS, ingress, distributed consensus, hardware independence, production certification, or external business-runtime execution without matching receipts.

## Run

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m kex_proven_core.cli --state-dir .kex-proven-state
```
