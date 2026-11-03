# Linguistic Core

Covers: `src/braink_runtime/linguistic_core.py`.
**Status: UNIT_TESTED.**

---

## Component identity

`braink:linguistic_core` version `1.0.0`;
`id = sha256(canonical_serialize({"name":"linguistic_core","namespace":"braink","version":"1.0.0"}))`.
Public names: `LinguisticCore`, `LexiconVersion`, `LEXICON_V1`,
`MAX_INPUT_LENGTH = 4096`, `MAX_TOKEN_LENGTH = 128`.

## Purpose

Be the single, narrow, deterministic doorway through which human language enters
the runtime. Everything downstream consumes a structured intent; nothing
downstream ever sees raw text. Determinism here is what makes the rest of the
system replayable: the same sentence, on any machine, at any time, produces the
same intent.

## Inputs

* `text: str`, 1–4096 characters after which a `ValueError` is raised.
* `tokens: list[str]` for `handle_ambiguity`.
* Optionally a `LexiconVersion` at construction time.

## Outputs

* `normalize(text) -> str` — lowercase, stripped, whitespace-collapsed,
  punctuation-free except hyphens.
* `tokenize(text) -> list[str]`.
* `map_intent(text) -> {"intent", "tokens", "confidence", "matched",
  "lexicon_version"}`.
* `validate_token(token) -> bool`.
* `handle_ambiguity(tokens) -> {"candidates", "ranked", "ambiguous",
  "resolved", "lexicon_version"}`.
* `lexicon_version() -> str`.

## Dependencies

Standard library only: `re`, `dataclasses`, `typing`. No I/O, no clock, no
randomness — this is what makes the component a pure function.

## Interfaces

```python
core = LinguisticCore()                 # or LinguisticCore(my_lexicon)
core.normalize("  RUN Diagnostics! ")   # -> "run diagnostics"
core.tokenize("Run   the LEDGER.")      # -> ["run", "the", "ledger"]
core.map_intent("run diagnostics")      # -> {"intent": "EXECUTE", ...}
core.validate_token("execute")          # -> True
core.handle_ambiguity(["run", "stop"])  # -> ambiguous, two candidates
core.lexicon_version()                  # -> "lexicon-1.0.0"
```

## Reconstruction rules

1. **`LexiconVersion`** is a frozen dataclass of `version: str` and
   `terms: dict[str, str]` mapping a lowercase term to an intent constant. It
   exposes `lookup(token)` (returns `""` when absent) and `known_terms()`
   (sorted list). Freezing it makes the lexicon a version, not a mutable state.
2. **`LEXICON_V1`** has version `"lexicon-1.0.0"` and maps:
   `run|execute|start → EXECUTE`, `stop|halt|kill → HALT`,
   `verify|check|validate → VERIFY`, `status|state → STATUS`,
   `restart|reboot|recover → RESTART`.
3. **Input guard** (`_guard_input`) rejects, with `ValueError`: `None`, any
   non-`str`, a string that is empty after `.strip()`, and any string longer than
   `MAX_INPUT_LENGTH`. Every public text method calls the guard first, so the
   failure surface is one function rather than five.
4. **`normalize`** lowercases, strips, replaces runs of `_` with a space,
   replaces every character that is not word-character, whitespace or hyphen with
   a space, then collapses whitespace runs to a single space and strips again.
   Hyphens survive because compound identifiers such as `ledger-chain` are
   meaningful tokens.
5. **`tokenize`** normalises then splits on single spaces, dropping empties.
6. **`validate_token`** returns `False` for `None`, non-strings, the empty
   string and anything containing whitespace; returns `len(token) <= 128`
   otherwise. It never raises — it is a predicate, not a guard.
7. **`map_intent`** tokenises, looks every token up, and keeps the hits in token
   order. With no hits it returns `intent = "UNKNOWN"`, `confidence = 0.0`,
   `matched = []`. Otherwise the intent is the **first** hit (leftmost wins, so
   the mapping is order-deterministic), `matched` lists every token that mapped
   to that same intent, and `confidence` is `round(len(hits)/len(tokens), 4)` —
   the fraction of the utterance the lexicon actually understood.
8. **`handle_ambiguity`** filters the supplied tokens through `validate_token`,
   counts intents, normalises the counts to sum to 1 (subject to 4-decimal
   rounding), ranks by descending score then ascending name for tie-break
   determinism, and reports `ambiguous = len(candidates) > 1` and `resolved` as
   the top candidate (`"UNKNOWN"` when nothing matched). It raises `ValueError`
   for `None` or a non-list.

## Required skill or skillset

`deterministic-intent-mapping`, part of the `language-surface` skillset.

## Conceptual validation method

Show that the output is a pure function of `(lexicon.version, normalised
tokens)`. There is no state mutation, no clock read, no random source and no
I/O in any code path, so replaying the same input at any time yields the same
result. Show that the guards make the domain total: every input either produces
a structured result or raises `ValueError`; nothing returns `None` or a partially
formed dict.

## Practical validation method

`tests/test_linguistic_core.py` — 22 tests covering: lowercase and strip,
whitespace collapse, punctuation removal with hyphen retention, tokenisation,
each of the five intents, `UNKNOWN` fallback, determinism across two spellings of
the same command, `validate_token` at the 128/129 boundary and for whitespace and
`None`, `ValueError` for `None`/empty/oversized/non-string input, ambiguity with
three competing intents, unambiguous multi-token input, no-match ambiguity,
`ValueError` for `None` token list, and a custom lexicon.

## Current validation state

**UNIT_TESTED.** No integration beyond `runtime.process_command`, which is
exercised in `tests/test_end_to_end.py`.

## Evidence generated

`evidence/TEST_RESULTS.json` (per-test names and outcome of the real pytest run).

## Saved representations

`src/braink_runtime/linguistic_core.py`, this document, the
`linguistic_core` entry in `registry/COMPONENT_REGISTRY.json`, and the
`deterministic-intent-mapping` entry in `registry/SKILL_REGISTRY.json`.

## Remaining limitations or gates

* The lexicon is small, flat and English-only; there is no morphology,
  stemming or synonym expansion beyond the hand-listed terms.
* No syntax: negation ("do **not** run"), conjunctions and multi-clause
  utterances are not understood — "stop run" maps to `HALT` purely by position.
* `confidence` measures lexical coverage, not semantic certainty, and must not
  be read as a probability.
* Unicode is normalised only by Python's `\w` class; no NFKC normalisation is
  applied, so visually identical strings with different code points may tokenise
  differently.
