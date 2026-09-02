from pathlib import Path
import hashlib

class DiscoveryAuditor:
    def audit_tree(self,root):
        root=Path(root).resolve(); files=[]; primitives=set()
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in str(p):
                rel=str(p.relative_to(root))
                files.append({"path":str(p.resolve()),"relative":rel,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
                low=rel.lower()
                for token in ("adapter","runtime","ledger","proof","checkpoint","router","service","workflow","audit","reconcile","market","sector","capability","vfs","seed"):
                    if token in low: primitives.add(token)
        return {"root":str(root),"files":files,"file_count":len(files),"primitives":sorted(primitives)}
