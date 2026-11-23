#!/usr/bin/env python3
"""Verify R87 P11 variant locators against the exact original R4 HTML source.

Usage:
  python tools/verify_p11_identity_source.py /path/to/KEDDEH_BRAINK_S29_QUANTUM_FULL_CHAIN_LEARNING_RUNTIME_R4.html

No source or registry files are modified.
"""
from __future__ import annotations
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/estate/P11_IDENTITY_VARIANT_CORRECTION_R87_20261122.json"

class ScriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.current_id = None
        self.parts = []
        self.by_id = {}
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.current_id = dict(attrs).get("id")
            self.parts = []
    def handle_data(self, data):
        if self.current_id is not None:
            self.parts.append(data)
    def handle_entityref(self, name):
        if self.current_id is not None:
            self.parts.append(f"&{name};")
    def handle_charref(self, name):
        if self.current_id is not None:
            self.parts.append(f"&#{name};")
    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.current_id is not None:
            self.by_id.setdefault(self.current_id, []).append("".join(self.parts))
            self.current_id = None
            self.parts = []

def main(source_path: str) -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = Path(source_path).read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    assert len(source) == m["source"]["bytes"], (len(source), m["source"]["bytes"])
    assert source_hash == m["source"]["sha256"], (source_hash, m["source"]["sha256"])
    parser = ScriptExtractor()
    parser.feed(source.decode("utf-8"))
    verified = []
    for variant in m["variants"]:
        script_id = variant["source_ref"].split("#", 1)[1]
        occurrences = parser.by_id.get(script_id, [])
        ordinal = variant["source_occurrence"] - 1
        assert len(occurrences) == 2, (script_id, len(occurrences))
        payload = occurrences[ordinal].encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        assert len(payload) == variant["bytes"], (variant["variant_id"], len(payload), variant["bytes"])
        assert digest == variant["sha256"], (variant["variant_id"], digest, variant["sha256"])
        obj = json.loads(payload.decode("utf-8"))
        assert obj["plan"] == variant["plan"]
        assert obj["status"] == variant["status"]
        verified.append({"variant_id": variant["variant_id"], "bytes": len(payload), "sha256": digest})
    assert len(verified) == 6
    assert len({v["variant_id"] for v in verified}) == 6
    print(json.dumps({"status":"PASS","source_bytes":len(source),"source_sha256":source_hash,"variants_verified":len(verified),"variants":verified},indent=2))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1]))
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
