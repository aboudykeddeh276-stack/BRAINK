#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 illlm_runtime.py --root . --state /tmp/illlm-build-state health >/tmp/illlm-health.json
rm -rf dist && mkdir -p dist/illlm
cp illlm_runtime.py Dockerfile README.md dist/illlm/
cp -R tests dist/illlm/tests
python3 - <<'PY'
from pathlib import Path
import hashlib, json
root=Path('dist/illlm')
manifest=[]
for p in sorted(root.rglob('*')):
    if p.is_file():
        b=p.read_bytes(); manifest.append({'path':str(p.relative_to(root)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(root/'MANIFEST.sha256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
PY
tar -C dist -czf dist/IL_LLM_DEPLOYABLE_1.0.0-candidate.tar.gz illlm
printf 'BUILD_STATUS=DONE\nARTIFACT=%s\n' "$(pwd)/dist/IL_LLM_DEPLOYABLE_1.0.0-candidate.tar.gz"
