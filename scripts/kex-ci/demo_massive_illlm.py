#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
MODULES = BASE / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from hardening import atomic_write_text, canonical_json_bytes  # noqa: E402
from illlm_context_translator import ILLLMContextTranslator, TranslationContext  # noqa: E402
from illlm_definitions import DefinitionGraph, DefinitionObject  # noqa: E402
from illlm_delta_engine import DeltaEngine, Fact, default_kex_rules  # noqa: E402
from illlm_equivalence import EquivalenceStore, EquivalentForm  # noqa: E402
from illlm_higher_order import build_topology  # noqa: E402
from illlm_hydrator import hydrate_recursive_runtime  # noqa: E402
from illlm_recursive_runtime import ILLLMNode, TraversalEdge, _tokens  # noqa: E402

OUT = BASE / "reports" / "kex-wbos" / "illlm-massive-demo.json"


def sha(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def main() -> int:
    started = time.time()

    # 1. Hydrate the historical/global IL-LLM-of-IL-LLMs topology.
    topology = build_topology()
    runtime = hydrate_recursive_runtime(topology)

    # 2. Add a bounded demonstrator context and executable object. This is a
    # local demo mutation of the in-memory graph, not persistent corpus proof.
    maths = "il-llm://demo/mathematics"
    caller = "il-llm://demo/mathematics/agent"
    executable = "il-llm://demo/mathematics/matrix-operation"
    runtime.register_node(ILLLMNode(
        identity=maths,
        role="MATHEMATICS",
        parent=runtime.META_ROOT,
        semantic_terms=_tokens(["mathematics", "matrix", "algebra", "operator"]),
        observed_state="DEMO_RESIDENT",
    ))
    runtime.register_node(ILLLMNode(
        identity=caller,
        role="LOCAL_ILLLM",
        parent=maths,
        semantic_terms=_tokens(["mathematics", "local agent", "matrix"]),
        observed_state="DEMO_RESIDENT",
    ))
    runtime.register_node(ILLLMNode(
        identity=executable,
        role="MATHEMATICAL_OBJECT",
        parent=maths,
        semantic_terms=_tokens(["mathematics", "matrix", "multiply", "execution"]),
        mathematical_state={"arity": 2, "operationClass": "matrix_multiplication"},
        execution_routes=("SOURCE_INGEST::KEX_MATH_MATRIX_MULTIPLY",),
        observed_state="DEMO_RESIDENT",
    ))
    runtime.add_edge(TraversalEdge(maths, executable, "DEFINES_OPERATION", cost=0.2))
    runtime.add_edge(TraversalEdge(caller, executable, "CONTEXTUAL_ACCESS", cost=0.1))

    contextual_plan = runtime.compile_context_plan(
        "mathematics matrix multiply",
        within=maths,
        require_execution=True,
    )

    # 3. Build definitions and definitions-of-definitions as a primary layer.
    definitions = DefinitionGraph()
    d0 = DefinitionObject(
        identity="definition://math/matrix-multiply",
        defines="subject://math/matrix-multiply",
        definition_class="PRIMARY",
        value={"meaning": "binary matrix multiplication"},
        relations=(("LOWERS_TO", executable),),
        executable_routes=("SOURCE_INGEST::KEX_MATH_MATRIX_MULTIPLY",),
    )
    d1 = DefinitionObject(
        identity="definition://math/definition-of-matrix-multiply",
        defines=d0.identity,
        definition_class="HIGHER_ORDER",
        value={"meaning": "definition governing the primary matrix-operation definition"},
        relations=(("DEFINITION_OF", d0.identity), ("PROVEN_BY", "proof://demo/matrix-definition")),
    )
    definitions.register(d0)
    definitions.register(d1)
    definition_chain = definitions.definition_chain("subject://math/matrix-multiply")

    # 4. Demonstrate semi-naive delta propagation. Existing facts are retained;
    # only the inserted frontier and its consequences are evaluated.
    delta = DeltaEngine()
    for rule in default_kex_rules():
        delta.add_rule(rule)
    first_delta = delta.insert([
        Fact("KEX_RELATION", "math://matrix", "definition://math/matrix-multiply"),
        Fact("EXECUTION_ROUTE", "definition://math/matrix-multiply", "runtime://demo/matrix"),
    ])
    repeated_delta = delta.insert([
        Fact("EXECUTION_ROUTE", "definition://math/matrix-multiply", "runtime://demo/matrix"),
    ])
    proof_facts = delta.query("PROOF_REQUIRED")

    # 5. Preserve alternate machine forms and extract one deterministic form by
    # declared cost/proof constraints instead of destroying the alternatives.
    equivalents = EquivalenceStore()
    equivalents.register("eq://matrix/multiply", EquivalentForm(
        identity="form://python/matmul",
        form="python-matmul",
        cost=2.0,
        proof_status="DEFINED",
        executable_route="SOURCE_INGEST::KEX_MATH_MATRIX_MULTIPLY",
    ))
    equivalents.register("eq://matrix/multiply", EquivalentForm(
        identity="form://generic/triple-loop",
        form="generic-triple-loop",
        cost=9.0,
        proof_status="DEFINED",
        executable_route="SOURCE_INGEST::KEX_MATH_MATRIX_MULTIPLY_GENERIC",
    ))
    extracted = equivalents.extract("eq://matrix/multiply", require_execution=True)

    # 6. Translate contextual intent into one narrow capability. This is the
    # intent→authority boundary; it still does not execute the actuator.
    secret = os.getenv("KEX_CAPABILITY_SECRET", "demo-only-capability-secret")
    translator = ILLLMContextTranslator(runtime, secret)
    translation = translator.translate(TranslationContext(
        caller_illlm=caller,
        global_context=maths,
        authority="DEMO",
        query="mathematics matrix multiply",
        requested_role="MATHEMATICAL_OBJECT",
        require_execution=True,
        ttl_seconds=60,
    ))

    checks = {
        "globalTopologyHydrated": len(runtime.nodes) > 3,
        "contextualExecutableResolved": bool((contextual_plan.get("selected") or {}).get("executionRoutes")),
        "definitionOfDefinitionResolved": int(definition_chain.get("depth", 0)) >= 2,
        "deltaDerivedFacts": int(first_delta.get("derived", 0)) >= 1,
        "repeatedFactAvoided": int(repeated_delta.get("inserted", -1)) == 0,
        "proofObligationDerived": len(proof_facts) >= 1,
        "equivalenceExtracted": bool(extracted.get("found")),
        "intentTranslated": translation.get("status") == "TRANSLATED",
        "capabilityNarrowed": (translation.get("typedAction") or {}).get("target") == "KEX_MATH_MATRIX_MULTIPLY",
    }

    report = {
        "schema": "kex.illlm.massive-demo.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "startedAt": started,
        "finishedAt": time.time(),
        "checks": checks,
        "globalRuntime": runtime.snapshot(),
        "contextualPlan": contextual_plan,
        "definitionChain": definition_chain,
        "delta": {
            "first": first_delta,
            "repeated": repeated_delta,
            "proofFacts": [fact.as_tuple() for fact in proof_facts],
        },
        "equivalence": extracted,
        "translation": {
            key: value for key, value in translation.items() if key != "capability"
        },
        "claimBoundary": [
            "This demo proves integrated in-process mechanics only when executed successfully.",
            "The demo capability is not an external actuator receipt.",
            "The synthetic matrix objects are demonstration fixtures, not evidence of the full historical corpus.",
            "Performance claims require the separate scaling benchmark and resident-estate measurement.",
        ],
    }
    report["reportHash"] = sha(report)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUT, json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
