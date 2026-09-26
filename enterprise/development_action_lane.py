from __future__ import annotations
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import hashlib,json,os,fcntl


def root(v: Any) -> str:
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()


class DevelopmentActionLane:
    """Evidence recorder only. It cannot sample or mutate an environment."""
    def __init__(self, path: str|Path): self.path=Path(path)
    def record_observer_frame(self, frame: Any, phase: str):
        payload=asdict(frame) if is_dataclass(frame) else dict(frame)
        return self._append({"kind":"OBSERVER_FRAME","phase":phase,"frame":payload})
    def record(self, kind: str, payload: dict[str,Any]): return self._append({"kind":kind,"payload":payload})
    def _append(self,payload):
        self.path.parent.mkdir(parents=True,exist_ok=True); self.path.touch(exist_ok=True)
        with self.path.open('r+',encoding='utf-8') as fh:
            fcntl.flock(fh.fileno(),fcntl.LOCK_EX)
            lines=[x.strip() for x in fh if x.strip()]; prev=json.loads(lines[-1])["record_root"] if lines else None
            rec={"schema":"kex.braink.development-action-lane.v2","sequence":len(lines)+1,"payload":payload,"payload_root":root(payload),"prev_root":prev}
            rec["record_root"]=root(rec)
            fh.seek(0,os.SEEK_END); fh.write(json.dumps(rec,sort_keys=True,separators=(',',':'))+'\n'); fh.flush(); os.fsync(fh.fileno()); fcntl.flock(fh.fileno(),fcntl.LOCK_UN)
        return rec
