#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT = Path.home() / ".braink" / "window-runtime"
ROOT.mkdir(parents=True, exist_ok=True)
COMMANDS = ROOT / "commands.jsonl"

def emit(action, **fields):
    payload = {"action": action, **fields}
    with COMMANDS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps(payload, indent=2))

def usage():
    print("""BRAINK Window Runtime
  open ADDRESS [TITLE] [STATE]
  project ADDRESS STATE [TITLE]
  readdress OLD NEW
  focus ADDRESS
  close ADDRESS
  readback
""")

if len(sys.argv) < 2:
    usage(); raise SystemExit(2)

cmd = sys.argv[1].lower()
if cmd == "open" and len(sys.argv) >= 3:
    emit("OPEN", address=sys.argv[2],
         title=sys.argv[3] if len(sys.argv) > 3 else "BRAINK Visual",
         state=sys.argv[4] if len(sys.argv) > 4 else "ACTIVE")
elif cmd == "project" and len(sys.argv) >= 4:
    emit("PROJECT", address=sys.argv[2], state=sys.argv[3],
         title=sys.argv[4] if len(sys.argv) > 4 else None)
elif cmd == "readdress" and len(sys.argv) == 4:
    emit("READDRESS", from=sys.argv[2], to=sys.argv[3])
elif cmd == "focus" and len(sys.argv) == 3:
    emit("FOCUS", address=sys.argv[2])
elif cmd == "close" and len(sys.argv) == 3:
    emit("CLOSE", address=sys.argv[2])
elif cmd == "readback":
    p = ROOT / "registry.json"
    print(p.read_text() if p.exists() else "[]")
else:
    usage(); raise SystemExit(2)
