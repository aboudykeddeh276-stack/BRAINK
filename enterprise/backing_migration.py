from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict
import hashlib, json, time

def root(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass
class MigrationReceipt:
    logical: str
    from_backing: str
    to_backing: str
    old_adapter: str
    new_adapter: str
    pre_hash: str | None
    post_hash: str | None
    state: str
    switched: bool
    created_ns: int

class BackingMigrationCoordinator:
    def __init__(self, registry, binder):
        self.registry=registry
        self.binder=binder
        self.receipts=[]
    def migrate(self, logical:str, successor_backing:str)->Dict[str,Any]:
        current=self.binder.bindings.get(logical)
        if not current:
            return {"status":"NO_CURRENT_BINDING","logical":logical}
        before=self.binder.apply(logical,"READ")
        if before.get("status")!="READ":
            return {"status":"SOURCE_READ_FAILED","source":before}
        discovered=self.registry.discover(successor_backing,"WRITE")
        if discovered.get("status")!="RESOLVED":
            return {"status":"SUCCESSOR_ADAPTER_UNRESOLVED","resolution":discovered}
        aid=discovered["adapter_id"]
        written=self.registry.invoke(aid,backing=successor_backing,logical=logical,operation="WRITE",payload=before["value"])
        if written.get("status")!="COMMITTED":
            return {"status":"SUCCESSOR_WRITE_FAILED","write":written}
        check=self.registry.invoke(aid,backing=successor_backing,logical=logical,operation="READ",payload=None)
        if check.get("status")!="READ":
            return {"status":"SUCCESSOR_READBACK_FAILED","readback":check}
        pre=before.get("value_hash") or root(before["value"])
        post=check.get("value_hash") or root(check["value"])
        if pre != post:
            return {"status":"HASH_MISMATCH","pre_hash":pre,"post_hash":post}
        old=current
        bound=self.binder.bind(logical,successor_backing,"READ")
        if bound.get("status")!="BOUND":
            return {"status":"REBIND_FAILED","result":bound}
        final=self.binder.apply(logical,"READ")
        switched=final.get("status")=="READ" and (final.get("value_hash") or root(final["value"]))==post
        receipt=MigrationReceipt(logical,old.backing,successor_backing,old.adapter_id,aid,pre,post,"COMMITTED" if switched else "SWITCH_READBACK_FAILED",switched,time.time_ns())
        self.receipts.append(receipt)
        return {"status":receipt.state,"receipt":asdict(receipt),"final":final}
