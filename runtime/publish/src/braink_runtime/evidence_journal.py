from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import json, os

class JournalViolation(RuntimeError): pass

def _canon(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def _hash(v): return sha256(_canon(v)).hexdigest()

@dataclass(frozen=True)
class JournalRecord:
    seq: int
    previous_hash: str
    kind: str
    payload: dict
    record_hash: str

class EvidenceJournal:
    """Append-only JSONL evidence ledger with per-record hash chain and fsync."""
    GENESIS = sha256(b'BRAINK-REPORT03-EVIDENCE-GENESIS').hexdigest()
    def __init__(self, path: str | Path): self.path=Path(path)

    def recover(self, *, truncate_partial_tail: bool=False) -> list[JournalRecord]:
        if not self.path.exists(): return []
        data=self.path.read_bytes(); lines=data.splitlines(keepends=True); out=[]; prev=self.GENESIS; good_bytes=0
        for i,line in enumerate(lines):
            complete=line.endswith(b'\n')
            if not complete:
                if truncate_partial_tail:
                    break
                raise JournalViolation('PARTIAL_TAIL_RECORD')
            try: obj=json.loads(line)
            except json.JSONDecodeError as exc: raise JournalViolation(f'INVALID_JSON_AT_SEQ:{i+1}') from exc
            expected={'seq':obj['seq'],'previous_hash':obj['previous_hash'],'kind':obj['kind'],'payload':obj['payload']}
            if obj['seq'] != i+1: raise JournalViolation('SEQUENCE_GAP')
            if obj['previous_hash'] != prev: raise JournalViolation('JOURNAL_CHAIN_DIVERGENCE')
            if _hash(expected) != obj['record_hash']: raise JournalViolation('JOURNAL_HASH_MISMATCH')
            rec=JournalRecord(**obj); out.append(rec); prev=rec.record_hash; good_bytes += len(line)
        if truncate_partial_tail and good_bytes != len(data):
            with self.path.open('r+b') as fh: fh.truncate(good_bytes); fh.flush(); os.fsync(fh.fileno())
        return out

    def append(self, kind: str, payload: dict) -> JournalRecord:
        if not kind: raise JournalViolation('KIND_REQUIRED')
        records=self.recover(truncate_partial_tail=False)
        seq=len(records)+1; prev=records[-1].record_hash if records else self.GENESIS
        body={'seq':seq,'previous_hash':prev,'kind':kind,'payload':payload}
        rec=JournalRecord(record_hash=_hash(body), **body)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd=os.open(self.path, os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        try:
            os.write(fd, _canon(asdict(rec))+b'\n'); os.fsync(fd)
        finally: os.close(fd)
        return rec
