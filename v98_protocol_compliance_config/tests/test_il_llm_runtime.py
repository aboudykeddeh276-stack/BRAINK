from __future__ import annotations
import json, tempfile
from pathlib import Path
from src.keddeh_il_llm_runtime import process_text

def prepare(root: Path) -> None:
    (root/"config").mkdir(parents=True)
    (root/"config"/"active_story_lexicon.json").write_text(json.dumps({"words":[
        {"word":"VERIFY","address":"word://verify","source_definitions":{"computer_science":"compare against a contract"}},
        {"word":"PRESERVE","address":"word://preserve","source_definitions":{"keddeh":"retain identity and lineage"}}
    ]}),encoding="utf-8")
    (root/"config"/"il_llm_active_story_registry.json").write_text(json.dumps({
        "canonicalTransition":["ANCHOR","FACTOR","TRANSLATE","ACT","VALIDATE","TOKENIZE","PRESERVE","RETURN"],
        "canonicalConcepts":{"agent":{"concept":"EXECUTABLE_RESPONSIBILITY_LOOP","role":"worker"}}
    }),encoding="utf-8")

def test_resolves_active_story_and_il_llm_concepts() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        result=process_text(root,"verify agent preserve",observer="test",environment="unit",sector="sector://test",service="service://test",emit_receipt=True)
        assert result["state"] == "CONTEXTUALIZED"
        assert len(result["expression"]["resolved_terms"]) == 3
        assert result["expression"]["source_preserved"] is True
        assert (root/"evidence"/"il_llm_context_receipt.json").exists()

def test_unresolved_terms_are_preserved_and_create_learning_work() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        result=process_text(root,"verify unknownterm",observer="test",environment="unit",sector="sector://test",service="service://test")
        assert result["state"] == "LEARNING_REQUIRED"
        assert result["global_stop"] is False
        assert result["expression"]["unresolved_terms"] == ["unknownterm"]
        packets=list((root/"runtime_volume"/"workplans"/"il_llm_learning").glob("*.json"))
        assert len(packets) == 1

def test_canonical_transition_order_is_preserved() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        result=process_text(root,"verify",observer="test",environment="unit",sector="sector://test",service="service://test")
        assert result["expression"]["transition"] == ["ANCHOR","FACTOR","TRANSLATE","ACT","VALIDATE","TOKENIZE","PRESERVE","RETURN"]
