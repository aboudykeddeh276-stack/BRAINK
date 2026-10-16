# KEX Deterministic Reconstruction Experiment R1

## Objective

Determine whether the existing KEX symbolic envelope can be reconstructed exactly from a reduced semantic seed containing only the information required by the existing `bind_symbol()` implementation.

This is the first experiment toward the stronger KEX proposition:

`irreducible invariant/reference set -> deterministic reconstruction -> identical machine/state identity`

## Existing implementation used

The experiment imports the existing `observer2_runtime.kex_symbolic_bridge.bind_symbol` implementation. No replacement codec or synthetic reconstruction algorithm is introduced.

The existing bridge defines the semantic root from the concept, IL-LLM entry, attributes, source projection root and dictionary root, then derives the symbolic envelope, A/B token stream, raw bit count and envelope root.

## Experiment

Reference:

- IL-LLM semantic dictionary entry.
- Concept ID.
- Symbol ID.
- Attributes.

Reduced seed:

- dictionary entry.
- concept ID.
- symbol ID.
- attributes.

Derived fields are removed from the seed:

- lexical form
- semantic type
- grammar role
- meaning
- policy-derived dictionary root
- semantic root
- A/B token representation
- raw bit count
- envelope root

The existing implementation reconstructs those fields.

## Required result

The experiment passes only if:

1. every reference envelope field equals the reconstructed field;
2. semantic roots match;
3. envelope roots match;
4. the reduced seed is smaller than the expanded envelope.

## What this does not establish

It does not establish universal compression. The R5 evidence already records that the A/B codec is run-length dependent and that universal compression was falsified.

It also does not yet establish reconstruction of the complete KEX machine. That is the next expansion: replace the single symbolic envelope with the smallest sufficient set for the complete machine graph, then compare the resulting graph, routes, machine contract, state and execution against the reference.

## Research position

The important measurement is not gzip ratio. It is the amount of information that is genuinely irreducible after removing fields that the existing transformation chain can deterministically derive.

That is the experiment that can distinguish ordinary compression from semantic/address compression.
