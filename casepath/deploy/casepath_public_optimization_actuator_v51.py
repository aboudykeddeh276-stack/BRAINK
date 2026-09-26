#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, json, os, re, shutil, hashlib, time

RELEASE = "CP-PUBLIC-OPT-V51-20260902"
TARGET_FILES = (
    "index.html",
    "app/workspace/index.html",
    "document-centre.html",
    "contact.html",
)

MOJIBAKE = {
    "›¡ï¸": "🛡️",
    "ï¸": "",
    "â†’": "→",
    "â€”": "—",
    "â€“": "–",
    "â€¢": "•",
    "â€™": "’",
    "â€œ": "“",
    "â€": "”",
}

EMPTY_RESOURCE_PHRASES = (
    "use Ask a Question to explore educational information and resources ().",
    "use Ask a Question to explore educational information and resources ().",
)

RUNTIME_PATCH = r'''\n<script id="casepath-public-optimization-v51">\n(() => {\n  "use strict";\n  const RELEASE = "CP-PUBLIC-OPT-V51-20260902";\n\n  const replaceText = (node) => {\n    if (!node || node.nodeType !== Node.TEXT_NODE) return;\n    let s = node.nodeValue || "";\n    const before = s;\n    const replacements = [\n      ["›¡ï¸", "🛡️"],\n      ["ï¸", ""],\n      ["â†’", "→"],\n      ["â€”", "—"],\n      ["â€“", "–"],\n      ["â€¢", "•"],\n      ["â€™", "’"],\n      ["â€œ", "“"],\n      ["â€", "”"],\n      ["resources ().", "resources."],\n      ["resources ()", "resources"]\n    ];\n    for (const [a,b] of replacements) s = s.split(a).join(b);\n    if (s !== before) node.nodeValue = s;\n  };\n\n  const walkText = (root=document.body) => {\n    if (!root) return;\n    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);\n    const nodes = [];\n    while (w.nextNode()) nodes.push(w.currentNode);\n    nodes.forEach(replaceText);\n  };\n\n  const hardenTestCheckout = () => {\n    const all = [...document.querySelectorAll("body *")];\n    const markers = all.filter(el => /stripe\\s*·?\\s*test mode\\s*·?\\s*no real charges/i.test(el.textContent || ""));\n    for (const marker of markers) {\n      let host = marker;\n      for (let i=0; i<6 && host.parentElement; i++, host=host.parentElement) {\n        const txt = host.textContent || "";\n        if (/complete your purchase/i.test(txt) && /pay\\s*\\$?\\d+/i.test(txt)) break;\n      }\n      if (host && host !== document.body) {\n        host.hidden = true;\n        host.setAttribute("aria-hidden","true");\n        host.dataset.casepathSuppressed = "test-checkout";\n      }\n    }\n  };\n\n  const markRelease = () => {\n    document.documentElement.dataset.casepathOptimizationRelease = RELEASE;\n  };\n\n  const apply = () => {\n    walkText();\n    hardenTestCheckout();\n    markRelease();\n  };\n\n  if (document.readyState === "loading") {\n    document.addEventListener("DOMContentLoaded", apply, {once:true});\n  } else {\n    apply();\n  }\n\n  const observer = new MutationObserver((mutations) => {\n    for (const m of mutations) {\n      for (const n of m.addedNodes) {\n        if (n.nodeType === Node.TEXT_NODE) replaceText(n);\n        else if (n.nodeType === Node.ELEMENT_NODE) walkText(n);\n      }\n    }\n    hardenTestCheckout();\n  });\n  if (document.documentElement) observer.observe(document.documentElement, {subtree:true, childList:true});\n})();\n</script>\n'''

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def patch_html(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    patched = text
    for bad, good in MOJIBAKE.items():
        if bad in patched:
            patched = patched.replace(bad, good)
            changes.append(f"encoding:{bad!r}->{good!r}")
    for phrase in EMPTY_RESOURCE_PHRASES:
        if phrase in patched:
            patched = patched.replace(phrase, phrase.replace("resources ().", "resources."))
            changes.append("copy:empty-parentheses")
    if RELEASE not in patched:
        insertion = RUNTIME_PATCH
        if "</body>" in patched:
            patched = patched.replace("</body>", insertion + "\n</body>", 1)
        else:
            patched += "\n" + insertion
        changes.append("runtime:optimization-v51")
    return patched, changes

def validate_text(name: str, text: str) -> dict:
    visible = re.sub(r'<script id="casepath-public-optimization-v51">.*?</script>', '', text, flags=re.S)
    checks = {
        "release_marker": RELEASE in text,
        "no_known_mojibake": not any(x in visible for x in MOJIBAKE),
        "no_empty_resources_parentheses": "resources ()" not in visible,
    }
    if name.endswith("app/workspace/index.html"):
        checks["test_checkout_guard_present"] = "casepathSuppressed" in text and "test-checkout" in text
    return checks

def status(root: Path | None) -> dict:
    if root is None:
        return {"schema":"casepath.public-optimization-status.v51","state":"UNBOUND","release":RELEASE}
    found = {}
    for rel in TARGET_FILES:
        p = root / rel
        found[rel] = {"exists":p.is_file()}
        if p.is_file():
            txt = p.read_text("utf-8", errors="replace")
            found[rel]["sha256"] = sha256_bytes(txt.encode())
            found[rel]["checks"] = validate_text(rel, txt)
    return {"schema":"casepath.public-optimization-status.v51","state":"BOUND","root":str(root),"files":found}

def apply(root: Path) -> dict:
    root = root.resolve()
    existing = [rel for rel in TARGET_FILES if (root / rel).is_file()]
    if not existing:
        raise RuntimeError("No CasePath target files found under bound docroot")
    backup = root / f".casepath-backup-{RELEASE}-{int(time.time())}"
    backup.mkdir(parents=True, exist_ok=False)
    receipts = []
    try:
        for rel in existing:
            p = root / rel
            before = p.read_bytes()
            bkp = backup / rel
            bkp.parent.mkdir(parents=True, exist_ok=True)
            bkp.write_bytes(before)
            text = before.decode("utf-8", errors="replace")
            patched, changes = patch_html(text)
            checks = validate_text(rel, patched)
            if not all(checks.values()):
                raise RuntimeError(f"Validation failed for {rel}: {checks}")
            after = patched.encode("utf-8")
            tmp = p.with_suffix(p.suffix + ".tmp-v51")
            tmp.write_bytes(after)
            os.replace(tmp, p)
            receipts.append({
                "file": rel,
                "before_sha256": sha256_bytes(before),
                "after_sha256": sha256_bytes(after),
                "changes": changes,
                "checks": checks,
            })
        receipt = {
            "schema":"casepath.public-optimization-receipt.v51",
            "release":RELEASE,
            "root":str(root),
            "backup":str(backup),
            "files":receipts,
        }
        (root / "casepath-optimization-v51.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    except Exception:
        for rel in existing:
            bkp = backup / rel
            if bkp.is_file():
                dst = root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bkp, dst)
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("status","deploy"))
    ap.add_argument("--docroot")
    ns = ap.parse_args()
    raw = ns.docroot or os.environ.get("CASEPATH_DOCROOT")
    root = Path(raw) if raw else None
    if ns.command == "status":
        print(json.dumps(status(root), indent=2))
        return
    if root is None:
        raise SystemExit("CASEPATH_DOCROOT is required")
    print(json.dumps(apply(root), indent=2))

if __name__ == "__main__":
    main()
