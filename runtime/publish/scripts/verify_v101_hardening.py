from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.hardened.yml"

REQUIRED = {
    "cap_drop_all": r"cap_drop:\s*\n\s*- ALL",
    "no_new_privileges": r"no-new-privileges:true",
    "read_only": r"read_only:\s*true",
    "tmpfs": r"tmpfs:",
    "healthcheck": r"healthcheck:",
    "resource_limits": r"(cpus:|mem_limit:)",
    "non_root": r"user:\s*["']?65532:65532",
    "no_default_auth": r"BRAINK_AUTH_TOKEN:\s*\$\{BRAINK_AUTH_TOKEN\?required\}",
}
text = COMPOSE.read_text(encoding="utf-8")
missing = [name for name, pattern in REQUIRED.items() if not re.search(pattern, text)]
if missing:
    print("V101_HARDENING=FAIL")
    print("MISSING=" + ",".join(missing))
    raise SystemExit(1)

print("V101_HARDENING=PASS")
print("CHECKS=" + ",".join(sorted(REQUIRED)))
