#!/usr/bin/env python3
"""Independent-journal local replication harness for the KEDDEH ToT kernel.

Each of the nine virtual voter coordinates has its own durable journal file.
The harness models message reachability/partitions deterministically. It is a
local multi-replica reference model, not independent-process/site evidence.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable
import json, os
from tot_safety_kernel import VOTERS, GROUPS, Proposal, ToTSafetyKernel, SafetyViolation, is_global_quorum, h, GENESIS_ROOT

SCHEMA="keddeh.tot-replica-journal.v1"

class Replica:
    def __init__(self, voter: str, path: Path):
        if voter not in VOTERS: raise ValueError("UNKNOWN_TOT_VOTER")
        self.voter=voter; self.path=path
        self.term=0; self.voted_for:dict[str,str]={}; self.approvals:dict[str,str]={}
        self.commit_index=0; self.committed_root=GENESIS_ROOT; self.log:list[dict[str,Any]]=[]
        if path.exists(): self._load()
        else: self._persist()
    def _body(self): return {"schema":SCHEMA,"voter":self.voter,"term":self.term,"voted_for":self.voted_for,"approvals":self.approvals,"commit_index":self.commit_index,"committed_root":self.committed_root,"log":self.log}
    def snapshot(self):
        b=self._body(); b["journal_root"]=h(b); return b
    def _persist(self):
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.snapshot(),indent=2,sort_keys=True)+'\n'); os.replace(tmp,self.path)
    def _load(self):
        d=json.loads(self.path.read_text()); root=d.pop('journal_root',None)
        if root!=h(d): raise SafetyViolation("REPLICA_JOURNAL_ROOT_MISMATCH")
        self.term=d['term']; self.voted_for=d['voted_for']; self.approvals=d['approvals']; self.commit_index=d['commit_index']; self.committed_root=d['committed_root']; self.log=d['log']
    def vote_leader(self, *, term:int, candidate:str, candidate_index:int, candidate_root:str) -> bool:
        if term<=self.term: return False
        # Candidate must be at least as up-to-date as this replica's accepted commit head.
        if candidate_index<self.commit_index: return False
        if candidate_index==self.commit_index and candidate_root!=self.committed_root: return False
        prior=self.voted_for.get(str(term))
        if prior and prior!=candidate: return False
        self.term=term; self.voted_for[str(term)]=candidate; self._persist(); return True
    def approve(self, proposal:Proposal) -> bool:
        if proposal.term<self.term: return False
        if proposal.index!=self.commit_index+1 or proposal.previous_root!=self.committed_root: return False
        key=f"{proposal.term}:{proposal.index}"; prior=self.approvals.get(key)
        if prior and prior!=proposal.proposal_root: return False
        self.term=max(self.term,proposal.term); self.approvals[key]=proposal.proposal_root; self._persist(); return True
    def commit_entry(self, entry:dict[str,Any]) -> bool:
        if entry['index']!=self.commit_index+1 or entry['previous_root']!=self.committed_root: return False
        self.log.append(entry); self.commit_index=entry['index']; self.committed_root=entry['entry_root']; self.term=max(self.term,entry['term']); self._persist(); return True
    def catch_up(self, committed_log:list[dict[str,Any]]):
        # Replay only append-compatible canonical committed history.
        self.log=[]; self.commit_index=0; self.committed_root=GENESIS_ROOT
        for e in committed_log:
            if e['index']!=self.commit_index+1 or e['previous_root']!=self.committed_root: raise SafetyViolation("CATCHUP_LOG_NOT_APPEND_COMPATIBLE")
            self.log.append(e); self.commit_index=e['index']; self.committed_root=e['entry_root']; self.term=max(self.term,e['term'])
        self._persist(); return self.snapshot()

class ReplicaHarness:
    def __init__(self, root: str|Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.coordinator=ToTSafetyKernel(self.root/'coordinator.json')
        self.replicas={v:Replica(v,self.root/'voters'/(v.replace(':','__')+'.json')) for v in VOTERS}
    def election(self, *, term:int, candidate:str, reachable:Iterable[str]):
        r=tuple(sorted(set(reachable))); cand=self.replicas[candidate]
        yes=[]
        for voter in r:
            if self.replicas[voter].vote_leader(term=term,candidate=candidate,candidate_index=cand.commit_index,candidate_root=cand.committed_root): yes.append(voter)
        if not is_global_quorum(yes): raise SafetyViolation("REPLICA_ELECTION_QUORUM_NOT_REACHED")
        # Coordinator records only the certificate after independent journals have voted.
        if term<=self.coordinator.term:
            self.coordinator.term=term-1; self.coordinator.leader=None
        self.coordinator.term=term; self.coordinator.leader=candidate; self.coordinator._persist()
        return {"state":"REPLICA_LEADER_ELECTED","candidate":candidate,"term":term,"yes":yes}
    def transition(self, operation:str,payload:dict[str,Any],*,reachable:Iterable[str]):
        if not self.coordinator.leader: raise SafetyViolation("REPLICA_LEADER_REQUIRED")
        proposal=self.coordinator.propose(operation,payload)
        yes=[]
        for voter in sorted(set(reachable)):
            if self.replicas[voter].approve(proposal):
                yes.append(voter); self.coordinator.approve(proposal,voter)
        out=self.coordinator.commit(proposal,yes)
        entry=self.coordinator.log[-1]
        applied=[]
        for voter in yes:
            if self.replicas[voter].commit_entry(entry): applied.append(voter)
        return {"state":"REPLICATED_COMMIT","certificate_voters":yes,"replicas_applied":applied,"commit":out}
    def catch_up(self,voter:str): return self.replicas[voter].catch_up(self.coordinator.log)
    def heads(self): return {v:{"index":r.commit_index,"root":r.committed_root,"term":r.term} for v,r in self.replicas.items()}