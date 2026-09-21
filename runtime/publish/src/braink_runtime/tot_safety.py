from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Iterable, Sequence

ZERO_ASSESSMENT_RULE = 'ZERO_IS_COMPUTED_ASSESSMENT_ONLY_NOT_ADDRESS_OR_STATE'

class SafetyViolation(RuntimeError):
    pass

def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def _hash(v) -> str:
    return sha256(_canon(v)).hexdigest()

def _reject_zero_token(v: str, field: str):
    if str(v).strip().upper() in {'0', 'ZERO'}:
        raise SafetyViolation(f'ZERO_NOT_PERMITTED_AS_{field}')

@dataclass(frozen=True)
class Transition:
    index: int
    epoch: int
    actor: str
    command: str
    payload: dict
    previous_root: str
    membership_hash: str
    def digest(self) -> str:
        return _hash(asdict(self))

@dataclass(frozen=True)
class Vote:
    voter: str
    epoch: int
    index: int
    transition_digest: str
    membership_hash: str

@dataclass(frozen=True)
class QuorumCertificate:
    epoch: int
    index: int
    transition_digest: str
    membership_hash: str
    voters: tuple[str, ...]
    certificate_hash: str

@dataclass(frozen=True)
class CommitReceipt:
    index: int
    epoch: int
    transition_digest: str
    previous_root: str
    committed_root: str
    membership_hash: str
    quorum_certificate: QuorumCertificate
    receipt_hash: str

class ToTSafetyKernel:
    """Crash-fault/non-Byzantine quorum safety kernel.

    Fixed membership, majority quorum, deterministic log chaining, per-voter
    equivocation lock. This intentionally does NOT claim Byzantine fault tolerance.
    """
    GENESIS = sha256(b'KEX-TOT-GENESIS').hexdigest()

    def __init__(self, members: Iterable[str], *, epoch: int = 1):
        members = tuple(sorted(set(str(m) for m in members)))
        if len(members) < 3:
            raise SafetyViolation('AT_LEAST_THREE_MEMBERS_REQUIRED')
        for m in members:
            _reject_zero_token(m, 'ADDRESS')
        if epoch <= 0:
            raise SafetyViolation('EPOCH_MUST_BE_POSITIVE')
        self.members = members
        self.epoch = epoch
        self.membership_hash = _hash({'members': members, 'epoch': epoch})
        self.log: list[Transition] = []
        self.receipts: list[CommitReceipt] = []
        self.root = self.GENESIS
        self._vote_locks: dict[tuple[int, int, str], str] = {}

    @property
    def quorum(self) -> int:
        return len(self.members) // 2 + 1

    def propose(self, *, actor: str, command: str, payload: dict, epoch: int | None = None) -> Transition:
        _reject_zero_token(actor, 'ADDRESS')
        if actor not in self.members:
            raise SafetyViolation('ACTOR_NOT_MEMBER')
        if not command:
            raise SafetyViolation('COMMAND_REQUIRED')
        ep = self.epoch if epoch is None else epoch
        if ep != self.epoch:
            raise SafetyViolation('STALE_OR_FUTURE_EPOCH')
        return Transition(len(self.log) + 1, ep, actor, command, payload, self.root, self.membership_hash)

    def vote(self, voter: str, transition: Transition) -> Vote:
        if voter not in self.members:
            raise SafetyViolation('VOTER_NOT_MEMBER')
        if transition.epoch != self.epoch or transition.membership_hash != self.membership_hash:
            raise SafetyViolation('STALE_OR_FUTURE_EPOCH')
        digest = transition.digest()
        key = (transition.epoch, transition.index, voter)
        prior = self._vote_locks.get(key)
        if prior is not None and prior != digest:
            raise SafetyViolation('VOTER_EQUIVOCATION')
        self._vote_locks[key] = digest
        return Vote(voter, transition.epoch, transition.index, digest, self.membership_hash)

    def certificate(self, transition: Transition, votes: Iterable[Vote]) -> QuorumCertificate:
        digest = transition.digest()
        valid = sorted({v.voter for v in votes if v.voter in self.members and v.epoch == self.epoch
                        and v.index == transition.index and v.transition_digest == digest
                        and v.membership_hash == self.membership_hash})
        if len(valid) < self.quorum:
            raise SafetyViolation('QUORUM_NOT_REACHED')
        body = {'epoch': self.epoch, 'index': transition.index, 'transition_digest': digest,
                'membership_hash': self.membership_hash, 'voters': valid}
        return QuorumCertificate(certificate_hash=_hash(body), **{**body, 'voters': tuple(valid)})

    def commit(self, t: Transition, votes: Iterable[Vote]) -> CommitReceipt:
        if t.epoch != self.epoch or t.membership_hash != self.membership_hash:
            raise SafetyViolation('STALE_OR_FUTURE_EPOCH')
        if t.index != len(self.log) + 1:
            raise SafetyViolation('NON_CONTIGUOUS_INDEX')
        if t.previous_root != self.root:
            raise SafetyViolation('PREVIOUS_ROOT_MISMATCH')
        qc = self.certificate(t, votes)
        new_root = sha256((self.root + t.digest() + qc.certificate_hash).encode()).hexdigest()
        body = {'index': t.index, 'epoch': t.epoch, 'transition_digest': t.digest(),
                'previous_root': self.root, 'committed_root': new_root,
                'membership_hash': self.membership_hash, 'quorum_certificate': asdict(qc)}
        receipt = CommitReceipt(index=t.index, epoch=t.epoch, transition_digest=t.digest(),
            previous_root=self.root, committed_root=new_root, membership_hash=self.membership_hash,
            quorum_certificate=qc, receipt_hash=_hash(body))
        self.log.append(t); self.receipts.append(receipt); self.root = new_root
        return receipt

    @classmethod
    def verify_receipt(cls, t: Transition, receipt: CommitReceipt, members: Sequence[str]) -> bool:
        members = tuple(sorted(set(members)))
        quorum = len(members) // 2 + 1
        if t.index != receipt.index or t.epoch != receipt.epoch or t.digest() != receipt.transition_digest:
            raise SafetyViolation('RECEIPT_TRANSITION_MISMATCH')
        qc = receipt.quorum_certificate
        expected_membership = _hash({'members': members, 'epoch': t.epoch})
        if receipt.membership_hash != expected_membership or qc.membership_hash != expected_membership:
            raise SafetyViolation('MEMBERSHIP_HASH_MISMATCH')
        voters = tuple(sorted(set(qc.voters)))
        if len(voters) < quorum or any(v not in members for v in voters):
            raise SafetyViolation('INVALID_QUORUM_CERTIFICATE')
        qc_body = {'epoch': qc.epoch, 'index': qc.index, 'transition_digest': qc.transition_digest,
                   'membership_hash': qc.membership_hash, 'voters': list(voters)}
        if _hash(qc_body) != qc.certificate_hash:
            raise SafetyViolation('QUORUM_CERTIFICATE_HASH_MISMATCH')
        if qc.transition_digest != t.digest() or qc.index != t.index or qc.epoch != t.epoch:
            raise SafetyViolation('INVALID_QUORUM_CERTIFICATE')
        expected_root = sha256((receipt.previous_root + t.digest() + qc.certificate_hash).encode()).hexdigest()
        if expected_root != receipt.committed_root:
            raise SafetyViolation('COMMITTED_ROOT_MISMATCH')
        receipt_body = {'index': receipt.index, 'epoch': receipt.epoch,
            'transition_digest': receipt.transition_digest, 'previous_root': receipt.previous_root,
            'committed_root': receipt.committed_root, 'membership_hash': receipt.membership_hash,
            'quorum_certificate': asdict(qc)}
        if _hash(receipt_body) != receipt.receipt_hash:
            raise SafetyViolation('RECEIPT_HASH_MISMATCH')
        return True

    @classmethod
    def verify_chain(cls, members: Sequence[str], transitions: Sequence[Transition], receipts: Sequence[CommitReceipt]) -> str:
        """Verify the whole ordered chain, anchored at GENESIS, and return final root."""
        if len(transitions) != len(receipts):
            raise SafetyViolation('CHAIN_LENGTH_MISMATCH')
        root = cls.GENESIS
        epoch = transitions[0].epoch if transitions else 1
        for expected_index, (t, r) in enumerate(zip(transitions, receipts), start=1):
            if t.index != expected_index or r.index != expected_index:
                raise SafetyViolation('CHAIN_INDEX_GAP')
            if t.epoch != epoch or r.epoch != epoch:
                raise SafetyViolation('CHAIN_EPOCH_CHANGE_UNSUPPORTED')
            if t.previous_root != root or r.previous_root != root:
                raise SafetyViolation('CHAIN_ROOT_DIVERGENCE')
            cls.verify_receipt(t, r, members)
            root = r.committed_root
        return root

    @classmethod
    def recover(cls, members: Sequence[str], transitions: Sequence[Transition], receipts: Sequence[CommitReceipt]) -> 'ToTSafetyKernel':
        cls.verify_chain(members, transitions, receipts)
        k = cls(members, epoch=transitions[0].epoch if transitions else 1)
        for t, r in zip(transitions, receipts):
            k.log.append(t); k.receipts.append(r); k.root = r.committed_root
        return k

    def advance_epoch(self, new_epoch: int, votes: Iterable[str]):
        if new_epoch <= self.epoch: raise SafetyViolation('EPOCH_NOT_ADVANCING')
        valid = set(votes) & set(self.members)
        if len(valid) < self.quorum: raise SafetyViolation('QUORUM_NOT_REACHED')
        self.epoch = new_epoch
        self.membership_hash = _hash({'members': self.members, 'epoch': new_epoch})
        self._vote_locks.clear()

    def reconfigure_membership(self, *_args, **_kwargs):
        raise SafetyViolation('MEMBERSHIP_CHANGE_PROTOCOL_NOT_IMPLEMENTED')

    def replay_root(self) -> str:
        return self.verify_chain(self.members, self.log, self.receipts)
