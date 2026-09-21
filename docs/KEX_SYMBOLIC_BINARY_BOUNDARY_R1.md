# KEX Symbolic / Binary Boundary R1

## Responsibility split

```text
IL-LLM
  meaning + dictionary + grammar
        ↓
KEX symbolic envelope
  concept_id
  symbol_id
  semantic_root
  dictionary_root
  A/B token stream
        ↓
HTML concept projection
  symbolic attributes only
  no packed carrier bytes
        ↓
explicit BinaryBoundaryAdapter
        ↓
KAB1 byte-constrained wire form
```

IL-LLM defines what a registered symbol means and what grammar role it occupies.
KEX owns representation translation without changing that meaning.

The virtual layer therefore remains symbolic until a byte-constrained carrier is
explicitly requested.

## Existing runtime bindings

- A/B codec: `observer2_runtime/ab_binary_codec.py`
- linguistic projection: `runtime/linguistics/braink_linguistic_engine.py`
- IL-LLM immutable semantic ledger: `runtime/illlm_ledger.py`
- symbolic bridge: `observer2_runtime/kex_symbolic_bridge.py`

`from_linguistic_projection()` accepts the existing linguistic engine projection
only when it carries a semantic root and preserves the source mutation boundary.

## HTML concept law

`project_html()` emits a deterministic HTML concept carrying:

- concept identity;
- IL-LLM symbol identity;
- semantic root;
- dictionary root;
- KEX envelope root;
- symbolic A/B tokens;
- raw semantic bit count;
- typed grammar role and semantic type.

The HTML projection does not invoke the packed wire adapter.

## Binary boundary law

`BinaryBoundaryAdapter.emit()` is the explicit transition into byte-constrained
carrier form.

KAB1 binds:

- wire magic/version/mode;
- original raw semantic bit count;
- packed A/B bit count;
- symbolic envelope root;
- SHA-256 of the exact packed bytes.

Restoration validates the packed-byte hash before decoding and then validates the
restored symbolic envelope root.

## Falsification result

The first tamper test altered only padding bits. The semantic envelope still
restored correctly, which proved that semantic-root verification alone did not
prove exact carrier-byte integrity.

R1 therefore adds a SHA-256 hash over the packed payload. The same mutation is now
rejected with `KEX_BINARY_BOUNDARY_PACKED_HASH_MISMATCH`.

## Compression boundary

A/B is not promoted as a universal compression theorem.

Observed 4096-bit payload ratios using the existing 18-symbol packed form:

| Input | packed/raw |
| --- | ---: |
| all zero | 0.557x |
| all one | 0.557x |
| alternating | 5.000x |
| deterministic random seed 297 | 2.504x |

The executed semantic fixture produced a 1382-byte KAB1 wire from 496 bytes of
canonical semantic JSON, a 2.786x wire expansion including the 78-byte boundary
header.

Therefore the supported engineering statement is:

> A/B is a deterministic symbolic/run-domain codec whose compression behaviour is
> data-dependent. Its architectural value here is the explicit KEX translation
> boundary, not a universal size reduction claim.

## Current evidence

`tests/test_kex_symbolic_bridge.py`: 8/8 local tests passed.

`evidence/KEX_SYMBOLIC_BINARY_BOUNDARY_R1.json` records the exact local source
hashes, tamper falsification, round-trip semantic roots, and compression
characterization.

## Still unproven

- a complete IL-LLM natural-language grammar;
- universal semantic coverage;
- universal compression advantage;
- browser/runtime execution of arbitrary A/B concept streams at scale;
- carrier interoperability beyond the KAB1 adapter;
- performance advantages over conventional byte encodings.

Those require separate executed evidence and are not implied by R1.
