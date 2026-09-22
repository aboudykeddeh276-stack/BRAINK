#!/usr/bin/env python3
from pathlib import Path
import base64, gzip, hashlib

HERE = Path(__file__).resolve().parent
ENC = HERE / "il_llm_recovered_cells.json.gz.b64"
OUT = HERE / "il_llm_recovered_cells.json"
EXPECTED_SHA256 = "25b59aa77b58d3445f08bee2db2a7f72b60705bf87e306db4ac2354a0fe0eed3"

raw = gzip.decompress(base64.b64decode(ENC.read_bytes()))
actual = hashlib.sha256(raw).hexdigest()
if actual != EXPECTED_SHA256:
    raise SystemExit(f"CORPUS_SHA256_MISMATCH:{actual}")
OUT.write_bytes(raw)
print(f"MATERIALIZED {OUT} {len(raw)} bytes sha256={actual}")
