from pathlib import Path
import re

p=Path(__file__).with_name("KEDDEH_LINUX_P17_REAL_VM_V73_SLICE1.html")
s=p.read_text()
required=[
 "SLICE1_PAYLOAD", "hostSha256", "KEX_SLICE1_PROOF_BEGIN",
 "KEX_SLICE1_GUEST_SHA256", "KEX_SLICE1_PROOF_END", "sha256sum",
 "serial0_send", "ttyS0", "slice1Identity"
]
missing=[x for x in required if x not in s]
assert not missing, f"missing Slice-1 identity elements: {missing}"
assert "state.slice1Identity='MATCH'" in s, "identity promotion must require digest equality"
assert "state.proof.KEX_SLICE1_GUEST_SHA256===state.slice1HostSha256" in s, "guest/host digest comparison missing"
assert re.search(r"const SLICE1_PAYLOAD=.*transport=serial0", s, re.S), "deterministic serial payload missing"
print("PASS slice1 static identity contract")
