#!/usr/bin/env python3
"""KEX deterministic reconstruction experiment R1.

Question:
    What is the smallest sufficient invariant representation from which the
    existing KEX symbolic envelope can be deterministically reconstructed?

This uses the existing observer2_runtime semantic bridge unchanged. It does
not claim universal compression. It measures derivability of representation
fields from a minimal semantic seed and proves equality of semantic/envelope
roots after reconstruction.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from observer2_runtime.kex_symbolic_bridge import (  # noqa: E402
    ILLLMSemanticDictionary,
    SemanticEntry,
    bind_symbol,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def build_reference():
    entry = SemanticEntry(
        symbol_id="illlm:op:activate",
        lexical_form="activate",
        semantic_type="operation",
        grammar_role="verb",
        definition="promote an armed mechanism into activation",
        policy_version="IL_LLM_SYMBOL_DICTIONARY_V1",
    )
    dictionary = ILLLMSemanticDictionary((entry,))
    attrs = {
        "target": "runtime://cpu/core",
        "lane": "R1",
        "revision": 7,
    }

    envelope = bind_symbol(
        dictionary,
        concept_id="concept:cpu.activate",
        symbol_id=entry.symbol_id,
        attributes=attrs,
    )

    # This is deliberately the smallest seed needed by the existing
    # bind_symbol() operation. All other envelope fields are derivable.
    seed = {
        "dictionary_entries": [asdict(entry)],
        "concept_id": "concept:cpu.activate",
        "symbol_id": entry.symbol_id,
        "attributes": attrs,
    }
    return seed, envelope


def reconstruct(seed):
    entries = tuple(SemanticEntry(**row) for row in seed["dictionary_entries"])
    dictionary = ILLLMSemanticDictionary(entries)
    return bind_symbol(
        dictionary,
        concept_id=seed["concept_id"],
        symbol_id=seed["symbol_id"],
        attributes=seed["attributes"],
    )


def main():
    seed, reference = build_reference()
    rebuilt = reconstruct(seed)

    reference_dict = asdict(reference)
    rebuilt_dict = asdict(rebuilt)

    # Full field equality is stronger than comparing only the top-level root.
    equal_fields = reference_dict == rebuilt_dict

    report = {
        "schema": "kex.deterministic-reconstruction.experiment.v1",
        "source_implementation": "observer2_runtime.kex_symbolic_bridge.bind_symbol",
        "reference": {
            "canonical_bytes": len(canonical(reference_dict)),
            "semantic_root": reference.semantic_root,
            "envelope_root": reference.envelope_root,
            "full_envelope_fields": sorted(reference_dict),
        },
        "minimal_seed": {
            "canonical_bytes": len(canonical(seed)),
            "seed_sha256": digest(seed),
            "fields": sorted(seed),
        },
        "reconstruction": {
            "full_field_equality": equal_fields,
            "semantic_root_equal": reference.semantic_root == rebuilt.semantic_root,
            "envelope_root_equal": reference.envelope_root == rebuilt.envelope_root,
            "rebuilt_canonical_bytes": len(canonical(rebuilt_dict)),
        },
        "derivable_fields": sorted(set(reference_dict) - set(seed)),
        "non_derivable_seed_fields": sorted(set(seed) & set(reference_dict)),
        "ratio": {
            "seed_over_reference": len(canonical(seed)) / len(canonical(reference_dict)),
            "reference_over_seed": len(canonical(reference_dict)) / len(canonical(seed)),
        },
        "claim_boundary": {
            "proven": [
                "existing bind_symbol implementation reconstructs an identical envelope from the minimal seed used by this experiment",
                "semantic_root and envelope_root are deterministic for this input",
                "the listed envelope fields are derivable under the existing implementation",
            ],
            "not_proven": [
                "universal compression",
                "reconstruction of the complete KEX machine from this semantic seed",
                "cross-language canonical equivalence",
                "independence from the existing Python implementation",
            ],
        },
    }

    if not equal_fields:
        report["failure"] = {
            "reference": reference_dict,
            "rebuilt": rebuilt_dict,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
