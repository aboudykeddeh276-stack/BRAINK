from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Iterable

ZERO_ASSESSMENT_RULE = 'ZERO_IS_COMPUTED_ASSESSMENT_ONLY_NOT_ADDRESS_OR_STATE'

class SafetyViolation(RuntimeError): pass

def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':')).encode()

def _reject_zero_token(v: str, field: str):
    if str(v).strip().upper() in {'0','ZERO'}:
        raise SafetyViolation(f'ZERO_NOT_PERMITTED_AS_{field}')

@dataclass(frozen=True)
class Transition:
    index: int
    epoch: int
    actor: str
    command: str
    payload: dict
    previous_root: str
    def digest(self) -> str:
        return sha256(_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class Vote:
    voter: str
    epoch: int
    transition_digest: str

@dataclass(frozen=True)
class CommitReceipt:
    index: int
    epoch: int
    transition_digest: str
    committed_root: str
    voters: tuple[str, ...]

class ToTSafetyKernel:
    def __init__(self, members: Iterable[str], *, epoch: int = 1):
        members = tuple(sorted(set(members)))
        if len(members) < 3:
            raise SafetyViolation('AT_LEAST_THREE_MEMBERS_REQUIRED')
        for m in members: _reject_zero_token(m, 'ADDRESS')
        if epoch <= 0: raise SafetyViolation('EPOCH_MUST_BE_POSITIVE')
        self.members = members
        self.epoch = epoch
        self.log: list[Transition] = []
        self.receipts: list[CommitReceipt] = []
        self.root = sha256(b'KEX-TOT-GENESIS').hexdigest()
        self._committed_by_index: dict[int, str] = {}

    @property
    def quorum(self) -> int:
        return len(self.members)//2 + 1

    def propose(self, *, actor: str, command: str, payload: dict, epoch: int|None=None) -> Transition:
        _reject_zero_token(actor, 'ADDRESS')
        if not command: raise SafetyViolation('COMMAND_REQUIRED')
        ep = self.epoch if epoch is None else epoch
        if ep != self.epoch: raise SafetyViolation('STALE_OR_FUTURE_EPOCH')
        return Transition(len(self.log)+1, ep, actor, command, payload, self.root)

    def commit(self, t: Transition, votes: Iterable[Vote]) -> CommitReceipt:
        if t.epoch != self.epoch: raise SafetyViolation('STALE_OR_FUTURE_EPOCH')
        if t.index != len(self.log)+1: raise SafetyViolation('NON_CONTIGUOUS_INDEX')
        if t.previous_root != self.root: raise SafetyViolation('PREVIOUS_ROOT_MISMATCH')
        digest=t.digest()
        valid={v.voter for v in votes if v.voter in self.members and v.epoch==self.epoch and v.transition_digest==digest}
        if len(valid) < self.quorum: raise SafetyViolation('QUORUM_NOT_REACHED')
        prior=self._committed_by_index.get(t.index)
        if prior is not None and prior != digest: raise SafetyViolation('CONFLICTING_COMMIT_AT_INDEX')
        self.log.append(t)
        self._committed_by_index[t.index]=digest
        self.root=sha256((self.root+digest).encode()).hexdigest()
        r=CommitReceipt(t.index,t.epoch,digest,self.root,tuple(sorted(valid)))
        self.receipts.append(r)
        return r

    def advance_epoch(self, new_epoch: int, votes: Iterable[str]):
        if new_epoch <= self.epoch: raise SafetyViolation('EPOCH_NOT_ADVANCING')
        valid=set(votes)&set(self.members)
        if len(valid) < self.quorum: raise SafetyViolation('QUORUM_NOT_REACHED')
        self.epoch=new_epoch

    def replay_root(self) -> str:
        root=sha256(b'KEX-TOT-GENESIS').hexdigest()
        for t in self.log:
            root=sha256((root+t.digest()).encode()).hexdigest()
        return root
