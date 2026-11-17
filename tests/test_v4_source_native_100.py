"""Actual original V4 JavaScript 100-pass -> native WebSocket -> IL-LLM disk proof.
Architect A. Keddeh. Node-executed algorithm is not a Chromium test.
"""
from __future__ import annotations
import hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
V4=ROOT/'runtime/learning/v4'

def test_original_v4_controls_are_source_bound_and_100passes_write_real_ledger(tmp_path):
    original=V4/'KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4.html'
    derived=V4/'KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V4_HOST_LINK.html'
    v5=V4/'KEX_BRAINK_CHAT_AI_CONTROL_WRAPPER_V5_SKILL_APEX.html'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='3cf4c7713e2fa4e38cfba840336854b3e488c899c35fd27e7a21e376b910b1d3'
    assert hashlib.sha256(v5.read_bytes()).hexdigest()=='ccbaf267a40b3f55b56da6b7f97c77279bdd583d29d1aa27139d085f5acd117b'
    assert 'function ensureWrapperState(){' not in original.read_text()
    assert '/* BEGIN SOURCE-EXACT V5 WRAPPER FUNCTIONS' in derived.read_text()
    p=subprocess.run([sys.executable,str(V4/'verify_native_v4_100.py'),str(tmp_path)],cwd=ROOT,
                     env={**os.environ,'PYTHONPATH':str(ROOT)},capture_output=True,text=True,timeout=120)
    assert p.returncode==0,f'stdout:{p.stdout}\nstderr:{p.stderr}'
    proof=json.loads((tmp_path/'v4_100_to_illlm_verification.json').read_text())
    assert proof['original_v4_algorithm_passes']==100
    assert proof['native_ledger_events']==101
    assert proof['after_service_restart_readback']['status']=='PASS'
    assert proof['learning_promotion']=='NOT_PROMOTED'
    assert proof['has_real_browser'] is False
    assert proof['external_keddeh_node_admitted'] is False
