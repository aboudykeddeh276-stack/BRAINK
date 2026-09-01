#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "modules" / "kex_wbos"
sys.path.insert(0, str(MODULES))

from capabilities import verify_capability
from illlm_context_translator import ILLLMContextTranslator, TranslationContext
from illlm_delta_engine import DeltaEngine, Fact, default_kex_rules
from illlm_equivalence import EquivalenceStore, EquivalentForm
from illlm_recursive_runtime import ILLLMNode, RecursiveILLLMRuntime, TraversalEdge, seed_primitive_ladder


def main() -> None:
    runtime = RecursiveILLLMRuntime()
    seed_primitive_ladder(runtime)

    math_context = "il-llm://meta/il-llm-of-il-llms/primitive/number/element/language/mathematics"
    if math_context not in runtime.nodes:
        # seed_primitive_ladder uses a deterministic parent chain; find by role to
        # avoid coupling the test to a cosmetic URI path.
        math_context = sorted(runtime.role_index["MATHEMATICS"])[0]

    local = "il-llm://agent/test/math-specialist"
    runtime.register_node(ILLLMNode(
        identity=local,
        role="AGENT_LOCAL",
        parent=math_context,
        semantic_terms=frozenset({"math", "linear", "algebra", "matrix"}),
        observed_state="RESIDENT",
    ))
    matrix = "il-llm://math/linear-algebra/matrix-multiply"
    runtime.register_node(ILLLMNode(
        identity=matrix,
        role="MATHEMATICS",
        parent=math_context,
        semantic_terms=frozenset({"matrix", "multiply", "linear", "algebra"}),
        execution_routes=("RUNTIME_LAUNCH::runtime://math/matrix-multiply",),
        observed_state="RESIDENT",
    ))
    unrelated = "il-llm://casepath/private/admin"
    runtime.register_node(ILLLMNode(
        identity=unrelated,
        role="CASEPATH",
        parent=runtime.META_ROOT,
        semantic_terms=frozenset({"matrix", "private", "admin"}),
        execution_routes=("CASEPATH_DISPATCH::casepath://admin",),
        observed_state="RESIDENT",
    ))
    runtime.add_edge(TraversalEdge(local, matrix, "CONTEXTUAL_RESOLUTION", cost=0.2, executable=True, execution_route="RUNTIME_LAUNCH::runtime://math/matrix-multiply"))

    secret = "test-illlm-capability-secret"
    translator = ILLLMContextTranslator(runtime, secret=secret)
    translated = translator.translate(TranslationContext(
        caller_illlm=local,
        global_context=math_context,
        authority="A.KEDDEH / KEDDEH_SYSTEMS",
        query="matrix multiply linear algebra",
        requested_role="MATHEMATICS",
    ))
    assert translated["status"] == "TRANSLATED", translated
    assert translated["selected"]["identity"] == matrix, translated
    assert unrelated not in [translated["selected"]["identity"]] + [x["identity"] for x in translated.get("alternates", [])]
    ok, cap = verify_capability(secret, translated["capability"], action="RUNTIME_LAUNCH", target="runtime://math/matrix-multiply")
    assert ok, cap
    denied, _ = verify_capability(secret, translated["capability"], action="CASEPATH_DISPATCH", target="casepath://admin")
    assert not denied

    delta = DeltaEngine()
    for rule in default_kex_rules():
        delta.add_rule(rule)
    cold = delta.insert([
        Fact("KEX_RELATION", "math://matrix", "math://linear-algebra"),
        Fact("EXECUTION_ROUTE", "math://matrix", "runtime://math/matrix-multiply"),
    ])
    assert cold["inserted"] == 2
    assert cold["derived"] >= 3, cold
    evaluations_before = delta.total_rule_evaluations
    warm_noop = delta.insert([Fact("EXECUTION_ROUTE", "math://matrix", "runtime://math/matrix-multiply")])
    assert warm_noop["inserted"] == 0 and warm_noop["ruleEvaluations"] == 0, warm_noop
    assert delta.total_rule_evaluations == evaluations_before
    warm_delta = delta.insert([Fact("EXECUTION_ROUTE", "math://vector", "runtime://math/vector")])
    assert warm_delta["inserted"] == 1
    assert warm_delta["ruleEvaluations"] < cold["ruleEvaluations"] + 1, (cold, warm_delta)

    eq = EquivalenceStore()
    eq.register("matrix-multiply", EquivalentForm("math://naive", "triple-loop", 10.0, "VERIFIED", "RUNTIME_LAUNCH::runtime://math/naive"))
    eq.register("matrix-multiply", EquivalentForm("math://blocked", "blocked", 3.0, "VERIFIED", "RUNTIME_LAUNCH::runtime://math/blocked"))
    eq.register("matrix-multiply", EquivalentForm("math://experimental", "unknown-fast", 1.0, "UNVERIFIED", "RUNTIME_LAUNCH::runtime://math/experimental"))
    extracted = eq.extract("matrix-multiply", require_execution=True, allowed_proof_status={"VERIFIED"})
    assert extracted["selected"]["identity"] == "math://blocked", extracted
    assert any(item["identity"] == "math://naive" for item in extracted["alternates"])

    path = runtime.shortest_traversal(local, matrix, executable_only=True)
    assert path["found"] and path["executionRoutes"] == ["RUNTIME_LAUNCH::runtime://math/matrix-multiply"], path

    print({
        "status": "ILLLM_ADVANCED_RUNTIME_PASS",
        "runtimeGeneration": runtime.generation,
        "graphHash": runtime.graph_hash(),
        "translationHash": translated["translationHash"],
        "deltaCold": cold,
        "deltaWarmNoop": warm_noop,
        "deltaWarm": warm_delta,
        "equivalenceSelection": extracted["selected"],
        "contextIsolation": "PASS",
        "capabilityNarrowing": "PASS",
    })


if __name__ == "__main__":
    main()
