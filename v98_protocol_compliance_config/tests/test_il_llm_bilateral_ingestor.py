from __future__ import annotations
import json, tempfile
from pathlib import Path
from src.keddeh_il_llm_bilateral_ingestor import run

def prepare(root: Path) -> None:
    (root/"config").mkdir(parents=True)
    (root/"config"/"il_llm_corpus_manifest.json").write_text(json.dumps({"sources":[
        {"sourceId":"source://words","title":"all_word_complete_values.json"},
        {"sourceId":"source://modules","title":"module_registry_v19.json"},
        {"sourceId":"source://missing","title":"missing.xlsx"}
    ]}),encoding="utf-8")

def test_each_word_and_context_becomes_separate_point_with_reverse_link() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        source=root/"all_word_complete_values.json"
        source.write_text(json.dumps([{"word_id":"WORD_1","identity":"RUN","form":"(- RUN +)","complete":1,"contexts":[{"source":"a.txt","line":1,"line_sample":"run"},{"source":"b.txt","line":2,"line_sample":"run task"}]}]),encoding="utf-8")
        result=run(root,[source],emit_receipt=True)
        assert result["points_preserved"] == 3
        assert result["bilateral_readback"] is True
        reverse=json.loads((root/"runtime_volume"/"il_llm"/"reverse_index.json").read_text())
        assert len(reverse) == 3
        assert sum(1 for item in reverse.values() if item["kind"]=="WORD_CONTEXT") == 2

def test_each_module_field_becomes_separate_point() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        source=root/"module_registry_v19.json"
        source.write_text(json.dumps([{"name":"ILLLMSourceIngestor","input":"source_inputs","output":"inventory","state_transition":"source->inventory","receipt_id":"R1","failure_mode":"ROUTE_TO_CORRECTION","status":"PASS"}]),encoding="utf-8")
        result=run(root,[source])
        assert result["points_preserved"] >= 7
        ledger=(root/"runtime_volume"/"il_llm"/"points.ledger").read_text().splitlines()
        assert any('"kind": "IL_LLM_MODULE"' in line for line in ledger)
        assert any('"kind": "MODULE_FIELD"' in line for line in ledger)

def test_missing_sources_create_nonterminal_mount_packets() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); prepare(root)
        result=run(root,[])
        assert result["global_stop"] is False
        assert len(result["pending_source_mounts"]) == 3
        packets=list((root/"runtime_volume"/"workplans"/"il_llm_source_mount").glob("*.json"))
        assert len(packets) == 3
