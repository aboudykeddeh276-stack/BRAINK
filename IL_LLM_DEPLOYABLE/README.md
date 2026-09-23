# IL-LLM Deployable — 1.0.0-candidate

Status: isolated integration candidate. This package does not replace the accepted BRAINK runtime and does not claim production qualification until the build/test commands are executed in a suitable runtime and their receipts are retained.

## Contract

`objective -> local evidence retrieval -> pre-action admission -> operation packet -> append-only hash-chained receipt`

The runtime is dependency-free Python 3.12+ and has no network requirement. It indexes bounded text files under the configured root, records SHA-256 evidence identities, refuses empty or evidence-free operations, and writes a hash-linked JSONL ledger.

## Local qualification

```bash
cd IL_LLM_DEPLOYABLE
./build.sh
python3 illlm_runtime.py --root /path/to/corpus --state ./state health
python3 illlm_runtime.py --root /path/to/corpus --state ./state run "your objective"
```

## Container

```bash
docker build -t illlm:1.0.0-candidate .
docker run --rm -v "$PWD/corpus:/data:ro" -v "$PWD/state:/state" illlm:1.0.0-candidate health
```

## Security boundaries

- non-root container user;
- no shell execution from corpus content;
- no dynamic code import from corpus;
- no network client;
- symlinks excluded from inventory;
- resolved paths constrained beneath corpus root;
- per-file ingestion bound at 2 MB;
- evidence and operation packets SHA-256 identified;
- append-only hash-linked ledger detects simple history rewriting/reordering but is not a cryptographic signature or external timestamp authority.

## Required promotion evidence

Production promotion requires retained receipts for: unit tests, package build, container build, health check, deterministic repeatability, malformed/hostile corpus tests, permission-denied behavior, large-corpus resource bounds, ledger corruption detection, upgrade/rollback, platform matrix, dependency/image vulnerability scan, SBOM, and an integration test against the intended BRAINK/IL-LLM execution seam.
