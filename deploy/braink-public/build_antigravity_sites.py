#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, os, pathlib, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parents[1]
WORK = pathlib.Path(os.environ.get('BRAINK_ANTIGRAVITY_WORK_ROOT', str(ROOT)))
DIST = pathlib.Path(os.environ.get('BRAINK_ANTIGRAVITY_DIST', str(WORK / 'dist')))
READBACK = pathlib.Path(os.environ.get('BRAINK_ANTIGRAVITY_BUILD_READBACK', str(WORK / 'ANTIGRAVITY_SITE_BUILD_READBACK.json')))
ADAPTER_ROOT = REPO / 'adapters' / 'web'
ASSETS = ['braink-web-adapter.js','braink-user-agent.js','braink-runtime-resolver.js','braink-fabric-manifest.json']

WORK.mkdir(parents=True, exist_ok=True)
env=os.environ.copy(); env['BRAINK_ANTIGRAVITY_WORK_ROOT']=str(WORK); env['BRAINK_ANTIGRAVITY_DIST']=str(DIST)
subprocess.run(['python3', str(ROOT / 'build_sites.py')], check=True, env=env)
manifest = json.loads((ROOT / 'BRAINK_PUBLIC_CORPORATE_RELEASE.json').read_text())
readback = {'schema':'kex.braink.antigravity-site-build.v1','domains':{},'overall':True,'dist':str(DIST)}

panel = r'''
<section id="braink-antigravity" style="margin-top:32px;border:1px solid #1d3445;padding:24px;border-radius:18px;background:#0b1721">
  <h2>BRAINK Antigravity</h2>
  <p>Describe the outcome. BRAINK resolves the required resident capability and returns proof with completed work.</p>
  <textarea id="braink-intent" rows="5" style="width:100%;padding:12px;border-radius:10px" placeholder="What do you want BRAINK to do?"></textarea>
  <p><button id="braink-run">Run with BRAINK</button></p>
  <pre id="braink-result" style="white-space:pre-wrap;overflow:auto"></pre>
</section>
<script type="module">
import { mountBRAINKUserAgent } from '/adapters/web/braink-user-agent.js';
const output = document.querySelector('#braink-result');
const agent = mountBRAINKUserAgent({ endpoint:'/braink/dispatch', requireProof:true });
document.querySelector('#braink-run').addEventListener('click', async () => {
  const intent = document.querySelector('#braink-intent').value.trim();
  if (!intent) return;
  output.textContent = 'DISPATCHING';
  try {
    const result = await agent.task(intent, { mode:'agentic', expectedArtifacts:[] });
    output.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    output.textContent = JSON.stringify({status:'BLOCKED', error:String(error)}, null, 2);
  }
});
</script>
'''

for domain, spec in manifest['domains'].items():
    site = DIST / domain
    asset_dir = site / 'adapters' / 'web'
    asset_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in ASSETS:
        src = ADAPTER_ROOT / name
        if not src.is_file(): raise FileNotFoundError(src)
        dst = asset_dir / name; shutil.copy2(src, dst); hashes[name] = hashlib.sha256(dst.read_bytes()).hexdigest()
    index = site / 'index.html'; text = index.read_text()
    if 'id="braink-antigravity"' not in text:
        text = text.replace('</main>', panel + '</main>'); index.write_text(text)
    hashes['index.html'] = hashlib.sha256(index.read_bytes()).hexdigest()
    readback['domains'][domain] = {'site':spec['site'],'runtime':spec['runtime'],'workspace':spec['workspace'],'vfs':spec['vfs'],'assets':hashes,'dispatch_endpoint':'/braink/dispatch','status':'BUILT'}

READBACK.parent.mkdir(parents=True, exist_ok=True)
READBACK.write_text(json.dumps(readback, indent=2))
print(json.dumps(readback, indent=2))
